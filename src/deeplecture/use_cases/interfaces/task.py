"""Task management protocols."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from deeplecture.domain import Task


@runtime_checkable
class TaskContextProtocol(Protocol):
    """
    Context passed to task callables for progress reporting.

    Provides task metadata and methods to report progress/emit events.
    """

    @property
    def task_id(self) -> str:
        """Unique task identifier."""
        ...

    @property
    def content_id(self) -> str:
        """Content identifier this task operates on."""
        ...

    @property
    def task_type(self) -> str:
        """Task type label (for logging/SSE)."""
        ...

    def progress(self, value: int, *, emit_event: bool = True) -> None:
        """
        Report task progress.

        Args:
            value: Progress percentage (0-100)
            emit_event: Whether to broadcast SSE event
        """
        ...

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Emit a custom SSE event.

        Args:
            event_type: Event type name
            data: Event payload
        """
        ...


# Type alias for task callables
TaskFn = Callable[[TaskContextProtocol], Any]


@runtime_checkable
class TaskQueueProtocol(Protocol):
    """
    Task queue management contract.

    Implementations manage in-memory task queues with
    status tracking and event broadcasting.
    """

    def submit(
        self,
        content_id: str,
        task_type: str,
        task: TaskFn,
        *,
        timeout: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Submit a task callable for execution.

        Args:
            content_id: Content identifier
            task_type: Task type label (for logging/SSE)
            task: Callable to execute, receives TaskContext
            timeout: Optional timeout override (uses default if None)
            metadata: Optional task metadata

        Returns:
            Task ID for tracking

        Raises:
            TaskQueueFullError: If queue is full
        """
        ...

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        ...

    def get_tasks_by_content(self, content_id: str) -> Sequence[Task]:
        """Get all tasks for a content ID."""
        ...

    def update_task_progress(
        self,
        task_id: str,
        progress: int,
        emit_event: bool = True,
    ) -> Task | None:
        """
        Update task progress.

        Args:
            task_id: Task identifier
            progress: Progress percentage (0-100)
            emit_event: Whether to broadcast SSE event

        Returns:
            Updated task or None if not found
        """
        ...

    def complete_task(self, task_id: str) -> Task | None:
        """
        Mark task as completed.

        Args:
            task_id: Task identifier

        Returns:
            Completed task or None if not found
        """
        ...

    def fail_task(self, task_id: str, error: str) -> Task | None:
        """
        Mark task as failed.

        Args:
            task_id: Task identifier
            error: Error message

        Returns:
            Failed task or None if not found
        """
        ...


@runtime_checkable
class EventPublisherProtocol(Protocol):
    """SSE event broadcasting contract."""

    def publish(
        self,
        content_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """
        Publish an event to subscribers.

        Args:
            content_id: Content identifier for routing
            event_type: Type of event
            data: Event payload
        """
        ...

    def broadcast(self, content_id: str, event_data: dict[str, Any]) -> None:
        """
        Broadcast event to all subscribers for a content.

        Args:
            content_id: Content identifier
            event_data: Event data to broadcast
        """
        ...
