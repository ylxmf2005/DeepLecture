"""
Whisper.cpp based ASR implementation.

Implements ASRProtocol for speech-to-text transcription.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import uuid
from pathlib import Path

from deeplecture.domain import Segment
from deeplecture.use_cases.dto.subtitle import ASRTranscriptionResult

logger = logging.getLogger(__name__)

# Pinned whisper.cpp version for supply chain security
WHISPER_CPP_REPO = "https://github.com/ggml-org/whisper.cpp.git"
WHISPER_CPP_COMMIT = "v1.7.3"  # Pinned release tag

# Hugging Face model URLs with SHA256 checksums
WHISPER_MODELS = {
    "tiny": {
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
        "sha256": "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21",
    },
    "base": {
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
        "sha256": "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
    },
    "small": {
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
        "sha256": "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1c71312a85",
    },
    "medium": {
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
        "sha256": "6c14d5adee5f86394037b4e4e8b59f1673b6cee10e3cf0b11bbdbee79c156208",
    },
    "large-v3-turbo": {
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
        "sha256": "4a5d71a659844bb56cff93bf1ca76c0feefc0cf1ff93548e8a64cc52f1691c24",
    },
}


class WhisperASR:
    """
    Whisper.cpp based speech recognition.

    Implements ASRProtocol.

    Features:
    - Auto-downloads whisper.cpp models
    - Hardware acceleration detection (Metal/CUDA)
    - Anti-hallucination settings
    """

    def __init__(
        self,
        *,
        model_name: str = "large-v3-turbo",
        whisper_cpp_dir: Path | None = None,
        auto_download: bool = True,
    ) -> None:
        self._model_name = model_name
        self._whisper_cpp_dir = whisper_cpp_dir or Path("whisper.cpp")
        self._auto_download = auto_download

        self._model_path = self._whisper_cpp_dir / "models" / f"ggml-{model_name}.bin"
        self._whisper_bin = self._whisper_cpp_dir / "build" / "bin" / "whisper-cli"

        self._hw_info = self._detect_hardware()
        self._ready = False

    def _detect_hardware(self) -> dict:
        """Detect hardware acceleration capabilities."""
        import platform

        hw = {
            "platform": platform.system(),
            "machine": platform.machine(),
            "has_metal": False,
            "has_cuda": False,
            "cpu_count": os.cpu_count() or 4,
        }

        # Apple Silicon = Metal
        if hw["platform"] == "Darwin" and hw["machine"] == "arm64":
            hw["has_metal"] = True

        # NVIDIA = CUDA
        try:
            result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
            hw["has_cuda"] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return hw

    def _ensure_ready(self) -> bool:
        """Ensure whisper.cpp and model are available."""
        if self._ready:
            return True

        # Build whisper.cpp if needed
        if not self._whisper_bin.exists():
            if not self._auto_download:
                logger.error("whisper.cpp not found: %s", self._whisper_bin)
                return False
            if not self._build_whisper_cpp():
                return False

        # Download model if needed
        if not self._model_path.exists():
            if not self._auto_download:
                logger.error("Model not found: %s", self._model_path)
                return False
            if not self._download_model():
                return False

        self._ready = True
        return True

    def _build_whisper_cpp(self) -> bool:
        """Clone and build whisper.cpp with pinned version."""
        logger.info("Building whisper.cpp (version %s)...", WHISPER_CPP_COMMIT)

        if not self._whisper_cpp_dir.exists():
            try:
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--branch",
                        WHISPER_CPP_COMMIT,
                        WHISPER_CPP_REPO,
                        str(self._whisper_cpp_dir),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                logger.error("git clone timed out")
                return False
            except subprocess.CalledProcessError as e:
                logger.error("Failed to clone whisper.cpp: %s", e.stderr.decode() if e.stderr else str(e))
                return False

        build_dir = self._whisper_cpp_dir / "build"
        build_dir.mkdir(exist_ok=True)

        try:
            subprocess.run(
                ["cmake", "..", "-DCMAKE_BUILD_TYPE=Release"],
                cwd=str(build_dir),
                check=True,
                capture_output=True,
                timeout=120,
            )
            subprocess.run(
                ["cmake", "--build", ".", "--config", "Release", "-j", str(os.cpu_count() or 4)],
                cwd=str(build_dir),
                check=True,
                capture_output=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            logger.error("cmake build timed out")
            return False
        except subprocess.CalledProcessError as e:
            logger.error("Failed to build whisper.cpp: %s", e.stderr.decode() if e.stderr else str(e))
            return False

        return self._whisper_bin.exists()

    def _download_model(self) -> bool:
        """Download whisper model from Hugging Face with SHA256 verification."""
        if self._model_name not in WHISPER_MODELS:
            logger.error("Unknown model: %s", self._model_name)
            return False

        model_info = WHISPER_MODELS[self._model_name]
        url = model_info["url"]
        expected_sha256 = model_info["sha256"]

        self._model_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading model '%s'...", self._model_name)
        try:
            from urllib.request import urlretrieve

            urlretrieve(url, str(self._model_path))

            # Verify SHA256 checksum
            actual_sha256 = self._compute_sha256(self._model_path)
            if actual_sha256 != expected_sha256:
                logger.error(
                    "Model checksum mismatch: expected %s, got %s",
                    expected_sha256,
                    actual_sha256,
                )
                self._model_path.unlink(missing_ok=True)
                return False

            logger.info("Model '%s' downloaded and verified", self._model_name)
            return True

        except Exception as e:
            logger.error("Failed to download model: %s", e)
            if self._model_path.exists():
                self._model_path.unlink()
            return False

    @staticmethod
    def _compute_sha256(path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def transcribe(self, audio_path: Path, *, language: str = "en") -> ASRTranscriptionResult:
        """
        Transcribe audio file to segments.

        Implements ASRProtocol.
        """
        if not self._ensure_ready():
            raise RuntimeError("WhisperASR not ready")

        audio_path = Path(audio_path).resolve()
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Convert to 16k mono WAV
        tmp_wav = audio_path.parent / f".tmp_{uuid.uuid4().hex}.wav"

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(audio_path), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(tmp_wav)],
                check=True,
                capture_output=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error("Audio conversion timed out")
            raise RuntimeError("Audio conversion timed out") from exc
        except subprocess.CalledProcessError as e:
            logger.error("ffmpeg failed: %s", e.stderr.decode() if e.stderr else str(e))
            raise RuntimeError("Audio conversion failed") from e

        requested_language = (language or "en").strip().lower() or "en"

        try:
            # Run whisper-cli
            output_base = tmp_wav.with_suffix("")
            json_path = output_base.with_suffix(".json")
            cmd = [
                str(self._whisper_bin),
                "-m",
                str(self._model_path),
                "-f",
                str(tmp_wav),
                "-osrt",
                "-of",
                str(output_base),
                "-l",
                requested_language,
                "-t",
                str(min(4, self._hw_info["cpu_count"])),
                "-bs",
                "1",  # beam size = 1 (anti-hallucination)
                "-mc",
                "0",  # max context = 0 (anti-hallucination)
            ]

            if requested_language == "auto":
                cmd.append("-oj")

            # Enable flash attention for GPU
            if self._hw_info["has_metal"] or self._hw_info["has_cuda"]:
                cmd.append("-fa")

            subprocess.run(cmd, check=True, capture_output=True, timeout=3600)

            # Parse SRT output
            srt_path = output_base.with_suffix(".srt")
            if not srt_path.exists():
                raise RuntimeError("SRT output not found")

            segments = self._parse_srt(srt_path.read_text(encoding="utf-8"))
            resolved_language = requested_language
            if requested_language == "auto":
                resolved_language = self._parse_resolved_language(json_path)

            # Cleanup
            srt_path.unlink(missing_ok=True)
            json_path.unlink(missing_ok=True)
            return ASRTranscriptionResult(segments=segments, resolved_language=resolved_language)

        except subprocess.TimeoutExpired as exc:
            logger.error("Whisper transcription timed out")
            raise RuntimeError("Transcription timed out") from exc
        finally:
            tmp_wav.unlink(missing_ok=True)

    def _parse_resolved_language(self, json_path: Path) -> str:
        """Extract the resolved language code from whisper JSON output."""
        if not json_path.exists():
            raise RuntimeError("Whisper JSON output not found for auto-detect")

        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to parse Whisper JSON output") from exc

        language = payload.get("result", {}).get("language")
        resolved = str(language or "").strip().lower()
        if not resolved:
            raise RuntimeError("Whisper auto-detect did not return a language")
        return resolved

    def _parse_srt(self, content: str) -> list[Segment]:
        """Parse SRT content to Segment list."""
        import re

        segments = []
        pattern = re.compile(
            r"(\d+)\n" r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n" r"(.+?)(?=\n\n|\n*$)",
            re.DOTALL,
        )

        for match in pattern.finditer(content):
            start = self._parse_time(match.group(2))
            end = self._parse_time(match.group(3))
            text = match.group(4).strip()
            segments.append(Segment(start=start, end=end, text=text))

        return segments

    def _parse_time(self, time_str: str) -> float:
        """Parse SRT time to seconds."""
        parts = time_str.replace(",", ":").split(":")
        h, m, s, ms = map(int, parts)
        return h * 3600 + m * 60 + s + ms / 1000
