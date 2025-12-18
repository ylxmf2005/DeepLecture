"""Note storage protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class NoteStorageProtocol(Protocol):
    """
    Contract for note storage.

    Implementations: FileSystemNoteStorage (in repository layer)
    """

    def load(self, content_id: str) -> tuple[str, datetime | None] | None:
        """
        Load note content and modification time.

        Args:
            content_id: Content identifier

        Returns:
            (content, updated_at) if note exists, None otherwise
        """
        ...

    def save(self, content_id: str, content: str) -> datetime:
        """
        Save note content.

        Args:
            content_id: Content identifier
            content: Note content to save

        Returns:
            Modification timestamp
        """
        ...

    def exists(self, content_id: str) -> bool:
        """
        Check if note exists.

        Args:
            content_id: Content identifier

        Returns:
            True if note exists, False otherwise
        """
        ...
