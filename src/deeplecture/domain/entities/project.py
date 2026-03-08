"""Domain entity for project (folder-based content organization)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

UTC = getattr(datetime, "UTC", timezone.utc)


def _coerce_datetime(value: datetime | str, *, name: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    raise TypeError(f"{name} must be datetime or ISO-8601 str, got {type(value)!r}")


@dataclass(slots=True)
class Project:
    """A named folder that groups related content items."""

    id: str
    name: str
    description: str = ""
    color: str = ""
    icon: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", _coerce_datetime(self.created_at, name="created_at"))
        object.__setattr__(self, "updated_at", _coerce_datetime(self.updated_at, name="updated_at"))
