"""Filesystem implementation of BookmarkStorageProtocol.

Stores bookmarks as a single JSON file at:
    content/{content_id}/bookmarks/bookmarks.json
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from deeplecture.infrastructure.repositories.path_resolver import validate_segment

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FsBookmarkStorage:
    """Filesystem-backed bookmark storage with thread-safe read-modify-write."""

    NAMESPACE = "bookmarks"
    FILENAME = "bookmarks.json"

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver
        self._lock = threading.Lock()

    def _get_path(self, content_id: str) -> Path:
        """Get path to bookmarks file."""
        validate_segment(content_id, "content_id")
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE, self.FILENAME))

    def load_all(self, content_id: str) -> tuple[list[dict[str, Any]], datetime | None] | None:
        """Load all bookmarks from filesystem.

        Args:
            content_id: Content identifier.

        Returns:
            (items, updated_at) if file exists, None otherwise.
        """
        path = self._get_path(content_id)
        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read bookmarks %s: %s", path, exc)
            return [], None

        items = data if isinstance(data, list) else []

        updated_at: datetime | None
        try:
            st = path.stat()
            updated_at = datetime.fromtimestamp(st.st_mtime, tz=UTC)
        except OSError:
            updated_at = datetime.now(UTC)

        return items, updated_at

    def save_all(self, content_id: str, items: list[dict[str, Any]]) -> datetime:
        """Save all bookmarks atomically with thread safety.

        Uses a lock to prevent read-modify-write races, and
        tempfile + os.replace for atomic filesystem writes.

        Args:
            content_id: Content identifier.
            items: List of bookmark dicts to save.

        Returns:
            Timestamp when saved.
        """
        path = self._get_path(content_id)

        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)

            content = json.dumps(items, ensure_ascii=False, indent=2)

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

        try:
            st = path.stat()
            return datetime.fromtimestamp(st.st_mtime, tz=UTC)
        except OSError:
            return datetime.now(UTC)

    def exists(self, content_id: str) -> bool:
        """Check if bookmarks file exists.

        Args:
            content_id: Content identifier.

        Returns:
            True if bookmarks exist, False otherwise.
        """
        return self._get_path(content_id).exists()
