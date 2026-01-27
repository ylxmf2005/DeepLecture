"""Cheatsheet service for API layer.

This service acts as a thin adapter between the Flask API routes and the
Clean Architecture storage layer. It delegates to FsCheatsheetStorage for
actual file operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pathlib import Path

from deeplecture.config.config import get_settings
from deeplecture.infrastructure.repositories import FsCheatsheetStorage, PathResolver

if TYPE_CHECKING:
    from deeplecture.workers.task_manager import TaskManager
    from deeplecture.services.content_service import ContentService

logger = logging.getLogger(__name__)


def _get_default_path_resolver() -> PathResolver:
    """Create PathResolver with settings-based paths."""
    settings = get_settings()
    data_dir = Path(settings.app.data_dir).expanduser().resolve()
    return PathResolver(
        content_dir=data_dir / "content",
        temp_dir=data_dir / "temp",
        upload_dir=data_dir / "uploads",
    )


@dataclass
class CheatsheetDTO:
    """Simple DTO for cheatsheet content."""

    content: str
    updated_at: str | None


class CheatsheetService:
    """
    Service adapter for cheatsheet operations.

    Delegates to FsCheatsheetStorage (Clean Architecture repository) for
    actual file I/O. This service exists to maintain API layer compatibility
    while the codebase migrates to Clean Architecture.
    """

    def __init__(
        self,
        *,
        task_manager: TaskManager | None = None,
        content_service: ContentService | None = None,
    ) -> None:
        self._task_manager = task_manager
        self._content_service = content_service
        # Use the Clean Architecture storage layer
        self._path_resolver = _get_default_path_resolver()
        self._storage = FsCheatsheetStorage(self._path_resolver)

    def get_cheatsheet_path(self, content_id: str) -> str:
        """Get the path to the cheatsheet file."""
        return self._path_resolver.build_cheatsheet_path(content_id)

    def get_cheatsheet(self, content_id: str) -> CheatsheetDTO:
        """Get cheatsheet content for a video.

        Delegates to FsCheatsheetStorage.load() for actual file I/O.
        """
        result = self._storage.load(content_id)
        if result is None:
            return CheatsheetDTO(content="", updated_at=None)

        content, updated_at = result
        return CheatsheetDTO(
            content=content,
            updated_at=updated_at.isoformat() if updated_at else None,
        )

    def save_cheatsheet(self, content_id: str, content: str) -> CheatsheetDTO:
        """Save cheatsheet content.

        Delegates to FsCheatsheetStorage.save() for atomic file writes.
        """
        updated_at = self._storage.save(content_id, content)
        return CheatsheetDTO(
            content=content,
            updated_at=updated_at.isoformat(),
        )
