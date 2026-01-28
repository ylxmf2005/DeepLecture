"""Filesystem implementation of QuizStorageProtocol.

Stores quiz items as JSON per content/language combination at:
    content/{content_id}/quiz/{language}.json
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


class FsQuizStorage:
    """Filesystem-backed quiz storage."""

    NAMESPACE = "quiz"

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver

    def _get_path(self, content_id: str, language: str) -> Path:
        """Get path to quiz file."""
        validate_segment(content_id, "content_id")
        validate_segment(language, "language")
        filename = f"{language}.json"
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE, filename))

    def _get_dir(self, content_id: str) -> Path:
        """Get quiz directory path."""
        validate_segment(content_id, "content_id")
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE))

    def load(self, content_id: str, language: str | None = None) -> tuple[dict[str, Any], datetime] | None:
        """Load quiz data from filesystem.

        Args:
            content_id: Content identifier.
            language: Language filter (optional). If None, loads first available.

        Returns:
            Tuple of (quiz_data, updated_at) if exists, None otherwise.
        """
        if language:
            path = self._get_path(content_id, language)
            if not path.exists():
                return None
            return self._load_file(path)

        # No language specified - find first available
        quiz_dir = self._get_dir(content_id)
        if not quiz_dir.exists():
            return None

        for file_path in quiz_dir.glob("*.json"):
            result = self._load_file(file_path)
            if result:
                return result
        return None

    def _load_file(self, path: Path) -> tuple[dict[str, Any], datetime] | None:
        """Load a single quiz file."""
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read quiz %s: %s", path, exc)
            return None

        updated_at: datetime
        try:
            st = path.stat()
            updated_at = datetime.fromtimestamp(st.st_mtime, tz=UTC)
        except OSError:
            updated_at = datetime.now(UTC)

        return data, updated_at

    def save(self, content_id: str, language: str, data: dict[str, Any]) -> datetime:
        """Save quiz data to filesystem.

        Uses atomic write (tempfile + os.replace) for safety.

        Args:
            content_id: Content identifier.
            language: Quiz language.
            data: Quiz data to save (items, stats, etc.).

        Returns:
            Timestamp when saved.
        """
        path = self._get_path(content_id, language)
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
        """Check if quiz exists.

        Args:
            content_id: Content identifier.
            language: Language filter (optional).

        Returns:
            True if quiz exists, False otherwise.
        """
        if language:
            return self._get_path(content_id, language).exists()

        quiz_dir = self._get_dir(content_id)
        if not quiz_dir.exists():
            return False
        return any(quiz_dir.glob("*.json"))
