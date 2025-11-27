from __future__ import annotations

import logging
import queue
import threading
import time
import weakref
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SSEManager:
    """
    In‑memory SSE subscription registry.
    Subscribers receive events through per-connection queues.
    """

    # Cleanup interval in seconds
    CLEANUP_INTERVAL = 60.0

    def __init__(self) -> None:
        self.subscribers: Dict[str, List[weakref.ref[queue.Queue]]] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def subscribe(self, content_id: str) -> queue.Queue:
        # Opportunistically clean up dead queues
        self._maybe_cleanup()

        subscriber_queue: queue.Queue = queue.Queue()
        ref = weakref.ref(subscriber_queue)
        with self._lock:
            self.subscribers.setdefault(content_id, []).append(ref)
            count = len(self.subscribers[content_id])
        logger.info("SSE subscribe: content_id=%s, total_subscribers=%d", content_id, count)
        return subscriber_queue

    def broadcast(self, content_id: str, event_data: Any) -> None:
        with self._lock:
            refs = list(self.subscribers.get(content_id, []))

        logger.info("SSE broadcast: content_id=%s, subscribers=%d, event=%s", content_id, len(refs), event_data.get("event") if isinstance(event_data, dict) else "?")

        dead_refs: List[weakref.ref[queue.Queue]] = []
        for ref in refs:
            q = ref()
            if q is None:
                dead_refs.append(ref)
                continue
            try:
                q.put_nowait(event_data)
            except queue.Full:
                # Drop the message instead of blocking the broadcaster.
                continue
            except Exception:
                dead_refs.append(ref)

        if dead_refs:
            self._prune(content_id, dead_refs)

    def cleanup_dead_queues(self) -> None:
        now = time.monotonic()
        with self._lock:
            for content_id, refs in list(self.subscribers.items()):
                alive = [ref for ref in refs if ref() is not None]
                if alive:
                    self.subscribers[content_id] = alive
                else:
                    self.subscribers.pop(content_id, None)
            self._last_cleanup = now

    def _maybe_cleanup(self) -> None:
        """Run cleanup if enough time has passed since last cleanup."""
        now = time.monotonic()
        if now - self._last_cleanup >= self.CLEANUP_INTERVAL:
            self.cleanup_dead_queues()

    def _prune(self, content_id: str, dead_refs: List[weakref.ref[queue.Queue]]) -> None:
        with self._lock:
            current = self.subscribers.get(content_id, [])
            if not current:
                return
            remaining = [ref for ref in current if ref() is not None and ref not in dead_refs]
            if remaining:
                self.subscribers[content_id] = remaining
            else:
                self.subscribers.pop(content_id, None)
