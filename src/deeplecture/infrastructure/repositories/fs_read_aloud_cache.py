"""Filesystem implementation of ReadAloudCacheProtocol.

Stores MP3 audio segments at:
    content/{content_id}/read_aloud_cache/{sentence_key}.mp3
"""

from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from deeplecture.infrastructure.repositories.path_resolver import validate_segment

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)

# Allowed characters in sentence keys: p0_s1, p12_s5 etc.
_VALID_KEY_CHARS = set("0123456789ps_")


class FsReadAloudCache:
    """Filesystem-backed read-aloud audio cache."""

    _NAMESPACE = "read_aloud_cache"

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver

    def save_audio(self, content_id: str, sentence_key: str, audio_data: bytes) -> None:
        validate_segment(content_id, "content_id")
        self._validate_key(sentence_key)

        path = self._audio_path(content_id, sentence_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio_data)

    def load_audio(self, content_id: str, sentence_key: str) -> bytes | None:
        validate_segment(content_id, "content_id")
        self._validate_key(sentence_key)

        path = self._audio_path(content_id, sentence_key)
        if not path.exists():
            return None

        try:
            return path.read_bytes()
        except OSError as exc:
            logger.warning("Failed to read cached audio %s: %s", path, exc)
            return None

    def clear(self, content_id: str) -> None:
        validate_segment(content_id, "content_id")
        cache_dir = Path(self._paths.build_content_path(content_id, self._NAMESPACE))
        if cache_dir.exists():
            with contextlib.suppress(OSError):
                shutil.rmtree(cache_dir)
                logger.debug("Cleared read-aloud cache for %s", content_id)

    def _audio_path(self, content_id: str, sentence_key: str) -> Path:
        return Path(self._paths.build_content_path(content_id, self._NAMESPACE, f"{sentence_key}.mp3"))

    @staticmethod
    def _validate_key(key: str) -> None:
        """Prevent path traversal via sentence_key."""
        if not key or not all(c in _VALID_KEY_CHARS for c in key):
            msg = f"Invalid sentence key: {key!r}"
            raise ValueError(msg)
