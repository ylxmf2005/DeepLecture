"""Task entity - Async job tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in (TaskStatus.READY, TaskStatus.ERROR)


@dataclass
class Task:
    """
    Task entity for async job tracking.

    Represents the state of background operations like subtitle generation,
    translation, and other async processes.
    """

    id: str
    type: str
    content_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status.is_terminal()

    def is_pending(self) -> bool:
        """Check if task is waiting to be processed."""
        return self.status == TaskStatus.PENDING

    def is_processing(self) -> bool:
        """Check if task is currently being processed."""
        return self.status == TaskStatus.PROCESSING

    def is_ready(self) -> bool:
        """Check if task completed successfully."""
        return self.status == TaskStatus.READY

    def is_error(self) -> bool:
        """Check if task failed."""
        return self.status == TaskStatus.ERROR
