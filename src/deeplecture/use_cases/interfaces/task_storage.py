"""Task storage protocol for persistent task state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from deeplecture.domain import Task


@runtime_checkable
class TaskStorageProtocol(Protocol):
    """
    Persistent storage for task state.

    Enables task state to survive across process restarts and
    be shared across multiple worker processes.
    """

    def save(self, task: Task) -> None:
        """
        Save or update a task.

        Args:
            task: Task entity to persist
        """
        ...

    def get(self, task_id: str) -> Task | None:
        """
        Get task by ID.

        Args:
            task_id: Unique task identifier

        Returns:
            Task entity or None if not found
        """
        ...

    def get_by_content(self, content_id: str) -> Sequence[Task]:
        """
        Get all tasks for a content ID.

        Args:
            content_id: Content identifier

        Returns:
            List of tasks associated with the content
        """
        ...

    def get_active_tasks(self) -> Sequence[Task]:
        """
        Get all non-terminal tasks (pending or processing).

        Returns:
            List of active tasks
        """
        ...

    def delete(self, task_id: str) -> bool:
        """
        Delete a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            True if deleted, False if not found
        """
        ...

    def cleanup_expired(self, ttl_seconds: int) -> int:
        """
        Remove terminal tasks older than TTL.

        Args:
            ttl_seconds: Time-to-live in seconds for completed/failed tasks

        Returns:
            Number of tasks deleted
        """
        ...
