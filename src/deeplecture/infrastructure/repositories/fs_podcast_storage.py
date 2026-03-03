"""Filesystem implementation of PodcastStorageProtocol.

Stores podcast data per content/language combination at:
    content/{content_id}/podcast/{language}.json   (manifest: dialogue + timestamps)
    content/{content_id}/podcast/{language}.m4a     (merged audio)
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deeplecture.infrastructure.repositories.path_resolver import validate_segment

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FsPodcastStorage:
    """Filesystem-backed podcast storage."""

    NAMESPACE = "podcast"

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver

    def _get_json_path(self, content_id: str, language: str) -> Path:
        """Get path to podcast manifest file."""
        validate_segment(content_id, "content_id")
        validate_segment(language, "language")
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE, f"{language}.json"))

    def _get_audio_path(self, content_id: str, language: str) -> Path:
        """Get path to podcast audio file."""
        validate_segment(content_id, "content_id")
        validate_segment(language, "language")
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE, f"{language}.m4a"))

    def _get_dir(self, content_id: str) -> Path:
        """Get podcast directory path."""
        validate_segment(content_id, "content_id")
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE))

    def get_audio_path(self, content_id: str, language: str) -> str:
        """Get the filesystem path for the podcast audio file."""
        return str(self._get_audio_path(content_id, language))

    def load(self, content_id: str, language: str | None = None) -> tuple[dict[str, Any], datetime] | None:
        """Load podcast manifest from filesystem.

        Args:
            content_id: Content identifier.
            language: Language filter (optional). If None, loads first available.

        Returns:
            Tuple of (podcast_data, updated_at) if exists, None otherwise.
        """
        if language:
            path = self._get_json_path(content_id, language)
            if not path.exists():
                return None
            return self._load_file(path)

        # No language specified - find first available
        podcast_dir = self._get_dir(content_id)
        if not podcast_dir.exists():
            return None

        for file_path in podcast_dir.glob("*.json"):
            result = self._load_file(file_path)
            if result:
                return result
        return None

    def _load_file(self, path: Path) -> tuple[dict[str, Any], datetime] | None:
        """Load a single podcast manifest file."""
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read podcast %s: %s", path, exc)
            return None

        updated_at: datetime
        try:
            st = path.stat()
            updated_at = datetime.fromtimestamp(st.st_mtime, tz=UTC)
        except OSError:
            updated_at = datetime.now(UTC)

        return data, updated_at

    def save(self, content_id: str, language: str, data: dict[str, Any]) -> datetime:
        """Save podcast manifest to filesystem.

        Uses atomic write (tempfile + os.replace) for safety.
        Audio file is written separately by the use case.

        Args:
            content_id: Content identifier.
            language: Podcast language.
            data: Podcast manifest data.

        Returns:
            Timestamp when saved.
        """
        path = self._get_json_path(content_id, language)
        path.parent.mkdir(parents=True, exist_ok=True)

        content = json.dumps(data, ensure_ascii=False, indent=2)

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                delete=False,
            ) as f:
                tmp_path = f.name
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        finally:
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)

        # Use filesystem mtime as the source of truth.
        try:
            st = path.stat()
            return datetime.fromtimestamp(st.st_mtime, tz=UTC)
        except OSError:
            return datetime.now(UTC)

    def exists(self, content_id: str, language: str | None = None) -> bool:
        """Check if podcast exists.

        Args:
            content_id: Content identifier.
            language: Language filter (optional).

        Returns:
            True if podcast exists, False otherwise.
        """
        if language:
            return self._get_json_path(content_id, language).exists()

        podcast_dir = self._get_dir(content_id)
        if not podcast_dir.exists():
            return False
        return any(podcast_dir.glob("*.json"))
