"""Event publishing protocol."""

from __future__ import annotations

from typing import Any, Protocol


class EventPublisherProtocol(Protocol):
    """Protocol for event publishing (SSE, WebSocket, etc.)."""

    def publish(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        content_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """Publish an event.

        Args:
            event_type: Type of event.
            data: Event data.
            content_id: Optional content identifier for filtering.
            task_id: Optional task identifier for filtering.
        """
        ...

    def subscribe(
        self,
        callback: Any,
        *,
        event_types: list[str] | None = None,
        content_id: str | None = None,
    ) -> str:
        """Subscribe to events.

        Args:
            callback: Callback function to invoke.
            event_types: Optional filter by event types.
            content_id: Optional filter by content.

        Returns:
            Subscription ID for unsubscribing.
        """
        ...

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events.

        Args:
            subscription_id: Subscription ID to remove.

        Returns:
            True if unsubscribed, False if not found.
        """
        ...
