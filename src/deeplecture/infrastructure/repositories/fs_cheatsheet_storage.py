"""Filesystem implementation of CheatsheetStorageProtocol.

Stores a single Markdown file per content item at:
    content/{content_id}/cheatsheet/cheatsheet.md
"""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from deeplecture.infrastructure.repositories.path_resolver import validate_segment

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FsCheatsheetStorage:
    """Filesystem-backed cheatsheet storage."""

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver

    def load(self, content_id: str) -> tuple[str, datetime | None] | None:
        """Load cheatsheet content from filesystem.

        Args:
            content_id: Content identifier.

        Returns:
            Tuple of (content, updated_at) if exists, None otherwise.
        """
        validate_segment(content_id, "content_id")
        path = Path(self._paths.build_cheatsheet_path(content_id))

        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read cheatsheet %s: %s", path, exc)
            return None

        updated_at: datetime | None
        try:
            st = path.stat()
            updated_at = datetime.fromtimestamp(st.st_mtime, tz=UTC)
        except OSError:
            updated_at = None

        return content, updated_at

    def save(self, content_id: str, content: str) -> datetime:
        """Save cheatsheet content to filesystem.

        Uses atomic write (tempfile + os.replace) for safety.

        Args:
            content_id: Content identifier.
            content: Markdown content to save.

        Returns:
            Timestamp when saved.
        """
        validate_segment(content_id, "content_id")
        path = Path(self._paths.build_cheatsheet_path(content_id))
        path.parent.mkdir(parents=True, exist_ok=True)

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

    def exists(self, content_id: str) -> bool:
        """Check if cheatsheet exists.

        Args:
            content_id: Content identifier.

        Returns:
            True if cheatsheet exists, False otherwise.
        """
        validate_segment(content_id, "content_id")
        path = Path(self._paths.build_cheatsheet_path(content_id))
        return path.exists()
