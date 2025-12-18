"""
TTS Service implementations.

Provides EdgeTTS and FishAudioTTS adapters that implement TTSProtocol.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import tempfile
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path

_TTS_FILTER_PATTERN = re.compile(r"[()*\-`]+")


def _filter_tts_text(text: str) -> str:
    """Normalize text before sending to TTS backend."""
    s = text.replace("\r", " ")
    s = s.replace("_", " ")
    s = _TTS_FILTER_PATTERN.sub("", s)
    return " ".join(s.split())


class EdgeTTS:
    """
    TTS implementation using Microsoft Edge TTS (free, no API key required).

    Outputs MP3 format audio.
    """

    file_extension: str = ".mp3"

    def __init__(self, *, voice: str = "zh-CN-XiaoxiaoNeural") -> None:
        """
        Initialize EdgeTTS.

        Args:
            voice: Voice identifier (e.g., 'zh-CN-XiaoxiaoNeural', 'en-US-AriaNeural')
        """
        try:
            import edge_tts  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("edge-tts is not installed. Install with: pip install edge-tts") from exc

        self._edge_tts = edge_tts
        self._voice = voice
        logger.debug("Initialized EdgeTTS with voice=%s", voice)

    def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        """
        Synthesize text to MP3 audio bytes.

        Args:
            text: Text to synthesize
            voice: Optional voice override

        Returns:
            MP3 audio bytes, or empty bytes if text is empty
        """
        clean_text = _filter_tts_text(text)
        if not clean_text:
            return b""

        actual_voice = voice or self._voice
        communicate = self._edge_tts.Communicate(clean_text, actual_voice)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            communicate.save_sync(tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            with contextlib.suppress(OSError):
                os.remove(tmp_path)

    def synthesize_to_file(self, text: str, output_path: Path, *, voice: str | None = None) -> None:
        """Synthesize text and save to file."""
        audio_bytes = self.synthesize(text, voice=voice)
        if audio_bytes:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_bytes)


class FishAudioTTS:
    """
    TTS implementation using Fish Audio API.

    Requires FISH_API_KEY environment variable or explicit api_key.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.fish.audio",
        model: str = "s1",
        reference_id: str | None = None,
        audio_format: str = "wav",
        latency: str = "balanced",
        speed: float = 1.0,
    ) -> None:
        """
        Initialize FishAudioTTS.

        Args:
            api_key: Fish Audio API key (or set FISH_API_KEY env var)
            base_url: API base URL
            model: Model name (e.g., 's1')
            reference_id: Voice reference ID
            audio_format: Output format ('wav', 'mp3', 'opus')
            latency: Latency mode ('normal', 'balanced')
            speed: Speech speed (0.5-2.0)
        """
        try:
            from fishaudio import FishAudio  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "Fish Audio SDK not installed. Install with: pip install 'fish-audio-sdk>=1.0.0,<2.0.0'"
            ) from exc

        resolved_key = api_key or os.getenv("FISH_API_KEY", "")
        if not resolved_key:
            logger.warning("No Fish Audio API key found. Set FISH_API_KEY env var or pass api_key.")

        self._client = FishAudio(api_key=resolved_key or None, base_url=base_url)
        self._model = model
        self._reference_id = reference_id
        self._audio_format = audio_format
        self._latency = latency
        self._speed = max(0.5, min(2.0, speed))

        # Set file extension based on format
        fmt = audio_format.lower()
        if fmt == "mp3":
            self.file_extension = ".mp3"
        elif fmt == "opus":
            self.file_extension = ".opus"
        else:
            self.file_extension = ".wav"

        logger.debug("Initialized FishAudioTTS with model=%s, format=%s", model, audio_format)

    def synthesize(self, text: str, *, voice: str | None = None) -> bytes:
        """
        Synthesize text to audio bytes.

        Args:
            text: Text to synthesize
            voice: Optional reference_id override

        Returns:
            Audio bytes in configured format, or empty bytes if text is empty
        """
        clean_text = _filter_tts_text(text)
        if not clean_text:
            return b""

        ref_id = voice or self._reference_id
        return self._client.tts.convert(
            text=clean_text,
            reference_id=ref_id,
            format=self._audio_format,
            latency=self._latency,
            speed=self._speed,
            model=self._model,
        )

    def synthesize_to_file(self, text: str, output_path: Path, *, voice: str | None = None) -> None:
        """Synthesize text and save to file."""
        audio_bytes = self.synthesize(text, voice=voice)
        if audio_bytes:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_bytes)
