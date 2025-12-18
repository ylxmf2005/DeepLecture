"""Event publishing protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventPublisherProtocol(Protocol):
    """
    Event publishing contract.

    Used for real-time event broadcasting (e.g., SSE).
    """

    def publish(
        self,
        content_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """
        Publish an event.

        Args:
            content_id: Content identifier for routing
            event_type: Type of event (e.g., "progress", "completed", "failed")
            data: Event payload
        """
        ...

    def broadcast(self, content_id: str, event_data: dict[str, Any]) -> None:
        """
        Broadcast an event to all listeners for a content.

        Args:
            content_id: Content identifier
            event_data: Event data including event type
        """
        ...
