"""Task-related errors."""

from __future__ import annotations

from deeplecture.domain.errors.base import DomainError


class TaskError(DomainError):
    """Base class for task-related errors."""


class TaskNotFoundError(TaskError):
    """Raised when task is not found."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class TaskQueueFullError(TaskError):
    """Raised when task queue is full."""
