"""
Event Publisher Implementation.

SSE-based real-time event broadcasting.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import logging
import queue
import threading
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Thread-safe event publisher for SSE broadcasting.

    Features:
    - Per-content event channels
    - Multiple subscribers per channel
    - Non-blocking publish
    - Automatic cleanup on disconnect
    """

    def __init__(self, max_queue_size: int = 100) -> None:
        """
        Initialize event publisher.

        Args:
            max_queue_size: Max events per subscriber queue
        """
        self._subscribers: dict[str, list[queue.Queue[dict[str, Any]]]] = defaultdict(list)
        self._lock = threading.RLock()
        self._max_queue_size = max_queue_size

    # =========================================================================
    # PUBLIC API - EventPublisherProtocol Implementation
    # =========================================================================

    def publish(
        self,
        content_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """
        Publish an event to all subscribers.

        Args:
            content_id: Content identifier for routing
            event_type: Type of event
            data: Event payload
        """
        event = dict(data)
        # Reserved keys must win over caller-provided data.
        event["event"] = event_type
        event["content_id"] = content_id
        self.broadcast(content_id, event)

    def broadcast(self, content_id: str, event_data: dict[str, Any]) -> None:
        """
        Broadcast event to all subscribers for a content.

        Args:
            content_id: Content identifier
            event_data: Event data to broadcast
        """
        with self._lock:
            subscribers = self._subscribers.get(content_id, [])
            if not subscribers:
                return

            # Non-blocking put to all subscriber queues
            for q in subscribers:
                try:
                    q.put_nowait(event_data)
                except queue.Full:
                    logger.warning("Subscriber queue full for %s, event dropped", content_id)

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    def subscribe(self, content_id: str) -> queue.Queue[dict[str, Any]]:
        """
        Subscribe to events for a content.

        Args:
            content_id: Content identifier

        Returns:
            Queue that will receive events
        """
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=self._max_queue_size)

        with self._lock:
            self._subscribers[content_id].append(q)

        logger.debug("New subscriber for %s (total: %d)", content_id, len(self._subscribers[content_id]))
        return q

    def unsubscribe(self, content_id: str, q: queue.Queue[dict[str, Any]]) -> None:
        """
        Unsubscribe from events.

        Args:
            content_id: Content identifier
            q: Queue to remove
        """
        with self._lock:
            subscribers = self._subscribers.get(content_id, [])
            with contextlib.suppress(ValueError):
                subscribers.remove(q)
                logger.debug("Subscriber removed for %s", content_id)

            # Cleanup empty channels
            if not subscribers and content_id in self._subscribers:
                del self._subscribers[content_id]

    def subscriber_count(self, content_id: str) -> int:
        """Get number of subscribers for a content."""
        with self._lock:
            return len(self._subscribers.get(content_id, []))

    # =========================================================================
    # SSE STREAM GENERATION
    # =========================================================================

    def stream(
        self,
        content_id: str,
        *,
        timeout: float = 30.0,
        send_initial: bool = True,
        max_idle_keepalives: int = 60,
        initial_events_factory: Callable[[], Iterable[dict[str, Any]]] | None = None,
        retry_ms: int | None = None,
    ) -> Iterator[str]:
        """
        Generate SSE stream for a content.

        Handles client disconnection gracefully by detecting GeneratorExit
        and cleaning up subscriptions.

        Args:
            content_id: Content identifier
            timeout: Seconds to wait for each event
            send_initial: Whether to send initial connection event
            max_idle_keepalives: Max consecutive keepalives before closing
                                 (prevents zombie connections)
            initial_events_factory: Optional callable that returns initial events to send
                                    AFTER subscribing (to avoid race conditions)
            retry_ms: If set, emit a `retry:` frame at the start of the stream

        Yields:
            SSE formatted strings
        """
        q = self.subscribe(content_id)
        idle_count = 0
        counter = itertools.count(1)

        try:
            # Send retry frame for browser auto-reconnect
            if retry_ms is not None:
                yield f"retry: {retry_ms}\n\n"

            # Send initial connection event
            if send_initial:
                yield self._format_sse({"event": "connected", "content_id": content_id}, event_id=next(counter))

            # Send initial events from factory (called AFTER subscribe to avoid race)
            if initial_events_factory is not None:
                for event in initial_events_factory():
                    yield self._format_sse(event, event_id=next(counter))

            # Stream events
            while True:
                try:
                    event = q.get(timeout=timeout)
                    idle_count = 0  # Reset on real event
                    yield self._format_sse(event, event_id=next(counter))
                except queue.Empty:
                    idle_count += 1
                    # Prevent zombie connections after prolonged idle
                    if idle_count >= max_idle_keepalives:
                        logger.info("Closing idle SSE stream for %s after %d keepalives", content_id, idle_count)
                        break
                    # Send keepalive (no id: for comments)
                    yield ": keepalive\n\n"

        except GeneratorExit:
            # Client disconnected - Flask closes the generator
            logger.debug("SSE client disconnected for %s", content_id)
        finally:
            self.unsubscribe(content_id, q)
            logger.debug("SSE stream cleanup completed for %s", content_id)

    def _format_sse(self, data: dict[str, Any], *, event_id: int | None = None) -> str:
        """Format data as SSE message.

        Note: We intentionally omit the SSE `event:` field so that all messages
        arrive via EventSource.onmessage. The event type is included in the JSON
        payload's "event" field for client-side routing.
        """
        json_data = json.dumps(data, ensure_ascii=False)
        prefix = f"id: {event_id}\n" if event_id is not None else ""
        return f"{prefix}data: {json_data}\n\n"


# Singleton for convenience
_default_publisher: EventPublisher | None = None


def get_event_publisher() -> EventPublisher:
    """Get or create default event publisher."""
    global _default_publisher
    if _default_publisher is None:
        _default_publisher = EventPublisher()
    return _default_publisher
