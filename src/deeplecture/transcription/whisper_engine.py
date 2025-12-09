from __future__ import annotations

import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Callable, Optional, Protocol
from urllib.request import urlretrieve

from deeplecture.app_context import get_app_context
from deeplecture.config.config import load_config

# Hugging Face model URLs for whisper.cpp GGML models
WHISPER_CPP_MODEL_URLS = {
    "tiny": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    "base": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "small": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "medium": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    "large-v2": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v2.bin",
    "large-v3": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
    "large-v3-turbo": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
}


def _download_whisper_model(model_name: str, target_path: Path, logger: logging.Logger) -> bool:
    """Download a whisper.cpp GGML model from Hugging Face."""
    if model_name not in WHISPER_CPP_MODEL_URLS:
        logger.error("Unknown model: %s. Available: %s", model_name, list(WHISPER_CPP_MODEL_URLS.keys()))
        return False

    url = WHISPER_CPP_MODEL_URLS[model_name]
    target_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading whisper.cpp model '%s' from %s ...", model_name, url)
    try:
        # Download with progress
        def _progress(block_num: int, block_size: int, total_size: int) -> None:
            if total_size > 0:
                percent = min(100, block_num * block_size * 100 // total_size)
                if block_num % 100 == 0:  # Log every 100 blocks
                    logger.info("Download progress: %d%%", percent)

        urlretrieve(url, str(target_path), reporthook=_progress)
        logger.info("Model downloaded successfully: %s", target_path)
        return True
    except Exception as e:
        logger.error("Failed to download model: %s", e)
        if target_path.exists():
            target_path.unlink()
        return False


def _build_whisper_cpp(whisper_cpp_dir: Path, logger: logging.Logger) -> bool:
    """Clone and build whisper.cpp if not present."""
    if not whisper_cpp_dir.exists():
        logger.info("Cloning whisper.cpp repository...")
        try:
            subprocess.run(
                ["git", "clone", "https://github.com/ggml-org/whisper.cpp.git", str(whisper_cpp_dir)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Failed to clone whisper.cpp: %s", e.stderr.decode() if e.stderr else str(e))
            return False
        except FileNotFoundError:
            logger.error("git not found. Please install git to auto-setup whisper.cpp")
            return False

    build_dir = whisper_cpp_dir / "build"
    whisper_bin = build_dir / "bin" / "whisper-cli"

    if whisper_bin.exists():
        logger.info("whisper.cpp binary already exists: %s", whisper_bin)
        return True

    logger.info("Building whisper.cpp...")
    try:
        # Create build directory
        build_dir.mkdir(exist_ok=True)

        # Run cmake
        subprocess.run(
            ["cmake", "..", "-DCMAKE_BUILD_TYPE=Release"],
            cwd=str(build_dir),
            check=True,
            capture_output=True,
        )

        # Build with parallel jobs
        cpu_count = os.cpu_count() or 4
        subprocess.run(
            ["cmake", "--build", ".", "--config", "Release", "-j", str(cpu_count)],
            cwd=str(build_dir),
            check=True,
            capture_output=True,
        )

        if whisper_bin.exists():
            logger.info("whisper.cpp built successfully: %s", whisper_bin)
            return True
        else:
            logger.error("Build completed but binary not found at %s", whisper_bin)
            return False

    except subprocess.CalledProcessError as e:
        logger.error("Failed to build whisper.cpp: %s", e.stderr.decode() if e.stderr else str(e))
        return False
    except FileNotFoundError as e:
        logger.error("cmake not found. Please install cmake to build whisper.cpp: %s", e)
        return False


class SubtitleEngine(Protocol):
    """
    Abstraction for generating subtitles from a video.

    Implementations should return True on success. Returning False signals a
    fallback was used or generation failed.
    """

    def generate_subtitles(
        self,
        video_path: str,
        output_path: str,
        language: str = "en",
    ) -> bool:  # pragma: no cover - interface
        ...


def _default_mock_subtitles(_: str, output_path: str) -> None:
    """
    Very small placeholder content for environments without a real engine.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sample_subtitles = """1
00:00:01,000 --> 00:00:05,000
Welcome to this video lecture.

2
00:00:06,000 --> 00:00:10,000
This is a placeholder subtitle for testing.
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(sample_subtitles)


ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_SUBTITLE_EXT = {".srt"}


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_path(path: str, allowed_ext: set[str], *, must_exist: bool = True) -> Path:
    resolved = Path(path).resolve()
    if allowed_ext and resolved.suffix.lower() not in allowed_ext:
        raise ValueError(f"Invalid file extension: {resolved.suffix}")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    ctx = get_app_context()
    ctx.init_paths()
    allowed_roots = {Path(ctx.content_dir).resolve(), Path(ctx.temp_dir).resolve()}
    if not any(_is_under(resolved, root) for root in allowed_roots):
        raise ValueError("Path outside allowed directories")
    return resolved


class WhisperCppEngine(SubtitleEngine):
    """
    whisper.cpp-based subtitle generator driven by YAML config.

    This implementation shells out to the whisper.cpp `whisper-cli` binary.
    If anything goes wrong (missing binary/model, ffmpeg failure, etc.), it
    returns False so the caller can decide how to fallback.

    Auto-detects hardware and applies optimal acceleration:
    - Apple Silicon: Metal GPU + Flash Attention
    - NVIDIA GPU: CUDA acceleration
    - CPU: Multi-threading optimization

    Supports automatic download of models and building whisper.cpp if not present.
    """

    def __init__(
        self,
        *,
        model_name: str = "large-v3-turbo",
        model_path: str = "",
        whisper_bin: str = "",
        whisper_cpp_dir: str = "whisper.cpp",
        auto_download: bool = True,
        threads: Optional[int] = None,
        flash_attn: bool = True,
        beam_size: int = 1,  # Default to 1 for minimal hallucination
        best_of: int = 1,    # Consistent with beam_size=1
        max_context: int = 0,  # 0 = disable context conditioning (anti-hallucination), -1 = use all context
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._model_name = model_name
        self._whisper_cpp_dir = Path(whisper_cpp_dir)
        self._auto_download = auto_download
        self._threads = threads
        self._flash_attn = flash_attn
        self._beam_size = beam_size
        self._best_of = best_of
        self._max_context = max_context

        # Resolve model path and whisper binary
        self._model_path = model_path or str(self._whisper_cpp_dir / "models" / f"ggml-{model_name}.bin")
        self._whisper_bin = whisper_bin or str(self._whisper_cpp_dir / "build" / "bin" / "whisper-cli")

        self._hw_info = self._detect_hardware()
        self._setup_done = False

    def _detect_hardware(self) -> dict:
        """Detect available hardware acceleration."""
        import platform

        hw = {
            "platform": platform.system(),
            "machine": platform.machine(),
            "has_metal": False,
            "has_cuda": False,
            "cpu_count": os.cpu_count() or 4,
        }

        # Detect Apple Silicon (Metal support)
        if hw["platform"] == "Darwin" and hw["machine"] == "arm64":
            hw["has_metal"] = True

        # Detect CUDA (check if nvidia-smi exists)
        try:
            result = subprocess.run(
                ["nvidia-smi"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                hw["has_cuda"] = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        self._logger.info(
            "Hardware detected: platform=%s, machine=%s, metal=%s, cuda=%s, cpus=%d",
            hw["platform"], hw["machine"], hw["has_metal"], hw["has_cuda"], hw["cpu_count"]
        )
        return hw

    def _ensure_setup(self) -> bool:
        """Ensure whisper.cpp is built and model is downloaded."""
        if self._setup_done:
            return True

        # Check if binary exists, if not try to build
        if not os.path.exists(self._whisper_bin):
            if self._auto_download:
                self._logger.info("whisper.cpp binary not found, attempting to build...")
                if not _build_whisper_cpp(self._whisper_cpp_dir, self._logger):
                    return False
                # Update path after build
                self._whisper_bin = str(self._whisper_cpp_dir / "build" / "bin" / "whisper-cli")
            else:
                self._logger.error("whisper.cpp binary not found at %s", self._whisper_bin)
                return False

        # Check if model exists, if not try to download
        if not os.path.exists(self._model_path):
            if self._auto_download:
                self._logger.info("Model not found, attempting to download '%s'...", self._model_name)
                if not _download_whisper_model(self._model_name, Path(self._model_path), self._logger):
                    return False
            else:
                self._logger.error("Model not found at %s", self._model_path)
                return False

        self._setup_done = True
        return True

    def _build_optimal_args(self, language: str) -> list:
        """Build optimal CLI arguments based on detected hardware."""
        args = []

        # Thread count: use all cores for CPU, fewer if GPU accelerated
        threads = self._threads
        if threads is None:
            if self._hw_info["has_metal"] or self._hw_info["has_cuda"]:
                # GPU does heavy lifting, fewer CPU threads needed
                threads = min(4, self._hw_info["cpu_count"])
            else:
                # CPU-only: use most cores
                threads = max(1, self._hw_info["cpu_count"] - 1)
        args.extend(["-t", str(threads)])

        # Flash Attention: enable for Metal/CUDA if supported
        if self._flash_attn and (self._hw_info["has_metal"] or self._hw_info["has_cuda"]):
            args.append("-fa")
            self._logger.info("Flash Attention enabled for GPU acceleration")

        # Beam search parameters
        args.extend(["-bs", str(self._beam_size)])
        args.extend(["-bo", str(self._best_of)])

        # Max context: 0 = no context conditioning (equivalent to condition_on_previous_text=False)
        # This is the most important anti-hallucination parameter
        args.extend(["-mc", str(self._max_context)])

        # Language
        args.extend(["-l", language])

        return args

    def generate_subtitles(
        self,
        video_path: str,
        output_path: str,
        language: str = "en",
    ) -> bool:
        try:
            video_resolved = _validate_path(video_path, ALLOWED_VIDEO_EXT)
            output_resolved = _validate_path(output_path, ALLOWED_SUBTITLE_EXT, must_exist=False)
        except (ValueError, FileNotFoundError) as exc:
            self._logger.error("Invalid path for whisper.cpp: %s", exc)
            return False

        # Ensure target directory exists
        os.makedirs(output_resolved.parent, exist_ok=True)

        # Auto-setup: download model and build whisper.cpp if needed
        if not self._ensure_setup():
            self._logger.error("Failed to setup whisper.cpp (model download or build failed)")
            return False

        # Convert input into a 16‑bit mono WAV, as required by whisper.cpp.
        # We deliberately keep the conversion minimal and let ffmpeg pick sane defaults.
        tmp_wav = output_resolved.parent.joinpath(f".tmp_{uuid.uuid4().hex}.wav")

        try:
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(video_resolved),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(tmp_wav),
            ]
            self._logger.info("Running ffmpeg for whisper.cpp: %s", " ".join(ffmpeg_cmd))
            subprocess.run(
                ffmpeg_cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            self._logger.error(
                "Failed to convert input to WAV for whisper.cpp: %s",
                exc,
                exc_info=True,
            )
            # Best effort cleanup
            try:
                if tmp_wav.exists():
                    tmp_wav.unlink()
            except Exception:
                pass
            return False

        # Run whisper.cpp CLI to generate SRT output.
        base_prefix = output_resolved.with_suffix("")
        srt_path = base_prefix.with_suffix(".srt")

        try:
            cmd = [
                self._whisper_bin,
                "-m",
                self._model_path,
                "-f",
                str(tmp_wav),
                "-osrt",
                "-of",
                str(base_prefix),
            ]
            # Apply hardware-optimized parameters
            cmd.extend(self._build_optimal_args(language))
            self._logger.info("Running whisper.cpp: %s", " ".join(cmd))
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            self._logger.error(
                "whisper.cpp transcription failed: %s",
                exc,
                exc_info=True,
            )
            return False
        finally:
            # Always try to remove the temporary WAV file.
            try:
                if tmp_wav.exists():
                    tmp_wav.unlink()
            except Exception:
                pass

        # Some whisper.cpp builds may choose different extensions; we expect
        # `<base_prefix>.srt`. If that file is missing, treat it as failure.
        if not srt_path.exists():
            self._logger.error(
                "whisper.cpp completed but SRT file not found at %s",
                srt_path,
            )
            return False

        # Ensure the final output path matches the caller expectation.
        if srt_path != output_resolved:
            try:
                srt_path.replace(output_resolved)
            except Exception as exc:
                self._logger.error(
                    "Failed to move generated SRT from %s to %s: %s",
                    srt_path,
                    output_resolved,
                    exc,
                )
                return False

        return True


class WhisperEngine(SubtitleEngine):
    """
    High-level subtitle engine that selects an implementation based on config.

    - subtitle.use_mock: force MockSubtitleEngine
    - subtitle.engine: "whisper_cpp" (default), "faster_whisper", or "mock"
    """

    def __init__(
        self,
        *,
        fallback: Optional[Callable[[str, str], None]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        High‑level engine wrapper.

        NOTE: we deliberately do *not* fall back to mock subtitles on failure
        in production. Callers rely on the boolean return value to decide
        whether subtitles really exist. Tests that need a dummy engine should
        use MockSubtitleEngine directly instead of this fallback.
        """
        self._logger = logger or logging.getLogger(__name__)
        # Keep the attribute to remain backwards compatible with the signature,
        # but do not use it in generate_subtitles. Mock behaviour should be
        # requested explicitly via the config (subtitle.engine=mock).
        self._fallback = fallback
        self._delegate: SubtitleEngine = self._build_delegate()

    def _build_delegate(self) -> SubtitleEngine:
        cfg = load_config() or {}
        subtitle_cfg = (cfg.get("subtitle") or {}) if isinstance(cfg, dict) else {}

        use_mock = bool(subtitle_cfg.get("use_mock", False))
        engine_name = str(subtitle_cfg.get("engine", "whisper_cpp")).lower()

        if use_mock or engine_name == "mock":
            self._logger.info("Using MockSubtitleEngine for subtitles")
            return MockSubtitleEngine()

        if engine_name == "whisper_cpp":
            whisper_cfg = subtitle_cfg.get("whisper_cpp") or {}
            model_name = str(whisper_cfg.get("model_name", "large-v3-turbo")).strip()
            model_path = str(whisper_cfg.get("model_path", "")).strip()
            whisper_bin = str(whisper_cfg.get("whisper_bin", "")).strip()
            whisper_cpp_dir = str(whisper_cfg.get("whisper_cpp_dir", "whisper.cpp")).strip()
            auto_download = whisper_cfg.get("auto_download", True)
            threads = whisper_cfg.get("threads")  # None = auto-detect
            flash_attn = whisper_cfg.get("flash_attn", True)
            # Anti-hallucination defaults: beam_size=1, max_context=0 (disable context conditioning)
            beam_size = whisper_cfg.get("beam_size", 1)
            best_of = whisper_cfg.get("best_of", 1)
            max_context = whisper_cfg.get("max_context", 0)  # 0 = condition_on_previous_text=False
            self._logger.info(
                "Using WhisperCppEngine (model=%s, dir=%s, auto_download=%s, max_context=%d)",
                model_name,
                whisper_cpp_dir,
                auto_download,
                max_context,
            )
            return WhisperCppEngine(
                model_name=model_name,
                model_path=model_path,
                whisper_bin=whisper_bin,
                whisper_cpp_dir=whisper_cpp_dir,
                auto_download=auto_download,
                threads=threads,
                flash_attn=flash_attn,
                beam_size=beam_size,
                best_of=best_of,
                max_context=max_context,
                logger=self._logger,
            )

        if engine_name == "faster_whisper":
            from deeplecture.transcription.faster_whisper_engine import FasterWhisperEngine

            faster_cfg = subtitle_cfg.get("faster_whisper") or {}
            model_size = str(faster_cfg.get("model_size", "medium")).strip()
            device = str(faster_cfg.get("device", "auto")).strip()
            compute_type = str(faster_cfg.get("compute_type", "auto")).strip()
            download_root = str(faster_cfg.get("download_root", "")).strip() or None

            self._logger.info(
                "Using FasterWhisperEngine (model=%s, device=%s, compute=%s)",
                model_size, device, compute_type
            )
            return FasterWhisperEngine(
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                download_root=download_root,
                logger=self._logger,
            )

        # Default fallback
        self._logger.warning("Unknown engine '%s', using MockSubtitleEngine", engine_name)
        return MockSubtitleEngine()

    def generate_subtitles(
        self,
        video_path: str,
        output_path: str,
        language: str = "en",
    ) -> bool:
        ok = False
        try:
            ok = self._delegate.generate_subtitles(
                video_path=video_path,
                output_path=output_path,
                language=language,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.error(
                "Subtitle engine delegate failed for %s: %s",
                video_path,
                exc,
                exc_info=True,
            )
            ok = False

        if ok:
            return True

        # Delegate reported failure; do not generate mock subtitles here.
        # Callers are expected to treat False as a hard failure and surface
        # the error to users instead of pretending generation succeeded.
        self._logger.warning(
            "Subtitle generation failed for %s; no subtitles were generated",
            video_path,
        )
        return False


class MockSubtitleEngine(SubtitleEngine):
    """
    Simple engine for tests that writes a predictable subtitle payload.
    """

    def __init__(self, content: str = "dummy subtitle") -> None:
        self._content = content

    def generate_subtitles(
        self,
        video_path: str,
        output_path: str,
        language: str = "en",
    ) -> bool:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self._content)
        return True


_default_engine: Optional[SubtitleEngine] = None


def get_default_subtitle_engine() -> SubtitleEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = WhisperEngine()
    return _default_engine
