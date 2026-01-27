"""Cheatsheet service for API layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from deeplecture.config.config import get_settings
from deeplecture.storage.path_resolver import get_default_path_resolver

if TYPE_CHECKING:
    from deeplecture.workers.task_manager import TaskManager
    from deeplecture.services.content_service import ContentService

logger = logging.getLogger(__name__)


@dataclass
class CheatsheetDTO:
    """Simple DTO for cheatsheet content."""

    content: str
    updated_at: str | None


class CheatsheetService:
    """
    Service for cheatsheet operations.

    Provides a simple interface for the API layer to interact with
    cheatsheet functionality.
    """

    def __init__(
        self,
        *,
        task_manager: TaskManager | None = None,
        content_service: ContentService | None = None,
    ) -> None:
        self._task_manager = task_manager
        self._content_service = content_service
        self._path_resolver = get_default_path_resolver()
        self._settings = get_settings()

    def get_cheatsheet_path(self, content_id: str) -> str:
        """Get the path to the cheatsheet file."""
        cheatsheet_dir = self._path_resolver.ensure_content_dir(content_id, "cheatsheet")
        return f"{cheatsheet_dir}/cheatsheet.md"

    def get_cheatsheet(self, content_id: str) -> CheatsheetDTO:
        """Get cheatsheet content for a video."""
        import os
        from datetime import datetime

        path = self.get_cheatsheet_path(content_id)
        if not os.path.exists(path):
            return CheatsheetDTO(content="", updated_at=None)

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            stat = os.stat(path)
            updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
            return CheatsheetDTO(content=content, updated_at=updated_at)
        except Exception as exc:
            logger.warning("Failed to read cheatsheet %s: %s", path, exc)
            return CheatsheetDTO(content="", updated_at=None)

    def save_cheatsheet(self, content_id: str, content: str) -> CheatsheetDTO:
        """Save cheatsheet content."""
        import os
        from datetime import datetime

        path = self.get_cheatsheet_path(content_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        stat = os.stat(path)
        updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
        return CheatsheetDTO(content=content, updated_at=updated_at)
