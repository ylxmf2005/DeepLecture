"""Task management protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from deeplecture.domain.entities.task import Task


class TaskContextProtocol(Protocol):
    """Protocol for task execution context."""

    @property
    def task_id(self) -> str:
        """Current task ID."""
        ...

    @property
    def content_id(self) -> str:
        """Content ID being processed."""
        ...

    def update_progress(self, progress: float, message: str | None = None) -> None:
        """Update task progress.

        Args:
            progress: Progress value (0.0 to 1.0).
            message: Optional status message.
        """
        ...

    def is_cancelled(self) -> bool:
        """Check if task has been cancelled.

        Returns:
            True if cancelled.
        """
        ...


class TaskQueueProtocol(Protocol):
    """Protocol for task queue management."""

    def submit(
        self,
        task_type: str,
        content_id: str,
        *,
        params: dict[str, Any] | None = None,
        priority: int = 0,
    ) -> str:
        """Submit a new task.

        Args:
            task_type: Type of task to execute.
            content_id: Content identifier.
            params: Optional task parameters.
            priority: Task priority (higher = more urgent).

        Returns:
            Task ID.
        """
        ...

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID.

        Args:
            task_id: Task identifier.

        Returns:
            Task if exists, None otherwise.
        """
        ...

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task.

        Args:
            task_id: Task identifier.

        Returns:
            True if cancelled, False if not found or already completed.
        """
        ...

    def register_handler(
        self,
        task_type: str,
        handler: Callable[[TaskContextProtocol], Any],
    ) -> None:
        """Register a task handler.

        Args:
            task_type: Type of task to handle.
            handler: Handler function.
        """
        ...
