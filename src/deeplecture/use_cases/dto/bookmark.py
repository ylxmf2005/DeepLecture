"""Bookmark DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

# =============================================================================
# Internal DTOs
# =============================================================================


@dataclass
class BookmarkItem:
    """Single video bookmark.

    Represents a user-created timestamp marker with optional note.
    """

    id: str  # UUID v4
    timestamp: float  # Seconds into the video
    title: str  # Auto-filled from subtitle, editable
    note: str  # Plain text note
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "title": self.title,
            "note": self.note,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BookmarkItem:
        """Create from dictionary."""
        from datetime import datetime, timezone

        def _parse_dt(value: str | None) -> datetime:
            if not value:
                return datetime.now(timezone.utc)
            try:
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                return datetime.now(timezone.utc)

        return cls(
            id=data.get("id", ""),
            timestamp=float(data.get("timestamp", 0)),
            title=data.get("title", ""),
            note=data.get("note", ""),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
        )


# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class CreateBookmarkRequest:
    """Request to create a new bookmark."""

    content_id: str
    timestamp: float
    title: str = ""
    note: str = ""


@dataclass
class UpdateBookmarkRequest:
    """Request to update an existing bookmark."""

    content_id: str
    bookmark_id: str
    title: str | None = None
    note: str | None = None
    timestamp: float | None = None


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class BookmarkListResult:
    """Result of bookmark list retrieval."""

    content_id: str
    bookmarks: list[BookmarkItem]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "bookmarks": [b.to_dict() for b in self.bookmarks],
            "count": len(self.bookmarks),
        }
