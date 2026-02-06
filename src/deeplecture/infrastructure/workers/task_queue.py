"""
Task execution infrastructure.

In-process task queue with thread pool workers.
No external dependencies (Redis/RQ removed).
"""

from __future__ import annotations

import concurrent.futures
import datetime
import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deeplecture.domain import Task
    from deeplecture.infrastructure.repositories.sqlite_task_storage import SQLiteTaskStorage
    from deeplecture.use_cases.interfaces.task import EventPublisherProtocol, TaskFn

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TaskConfig:
    """Task system configuration (injected from settings)."""

    workers: int
    queue_max_size: int
    default_timeout_seconds: float
    completed_task_ttl_seconds: int
    cleanup_interval_seconds: int


@dataclass
class _QueueItem:
    """Internal queue item wrapping task callable."""

    task_id: str
    content_id: str
    task_type: str
    callable: TaskFn
    timeout: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskContext:
    """
    Context passed to task callables for progress reporting.

    Implements TaskContextProtocol.
    """

    def __init__(
        self,
        task_id: str,
        content_id: str,
        task_type: str,
        manager: TaskManager,
    ) -> None:
        self._task_id = task_id
        self._content_id = content_id
        self._task_type = task_type
        self._manager = manager

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def content_id(self) -> str:
        return self._content_id

    @property
    def task_type(self) -> str:
        return self._task_type

    def progress(self, value: int, *, emit_event: bool = True) -> None:
        """Report task progress (0-100)."""
        self._manager.update_task_progress(self._task_id, value, emit_event=emit_event)

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit a custom SSE event."""
        payload = dict(data)
        # Reserved keys must win over caller-provided data.
        payload["event"] = event_type
        payload["task_id"] = self._task_id
        self._manager._broadcast(self._content_id, payload)


class TaskManager:
    """
    In-memory task coordinator with SSE event broadcasting.

    Key design:
    - Directly accepts TaskFn callables, no registry pattern
    - Supports per-task timeout with thread pool execution
    - Automatic cleanup of expired completed/failed tasks
    """

    def __init__(
        self,
        config: TaskConfig,
        event_publisher: EventPublisherProtocol | None = None,
        task_storage: SQLiteTaskStorage | None = None,
    ) -> None:
        self._config = config
        self._event_publisher = event_publisher
        self._storage = task_storage

        # Task state storage
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()

        # Work queue
        self._queue: queue.Queue[_QueueItem] = queue.Queue(maxsize=self._config.queue_max_size)

        # Cleanup tracking
        self._last_cleanup = time.monotonic()

        # Startup reconciliation: mark any persisted inflight tasks as error
        if self._storage:
            affected = self._storage.mark_inflight_as_error("Task interrupted by server restart")
            if affected:
                logger.info("Startup reconciliation: marked %d inflight tasks as error", affected)

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
            timeout: Timeout in seconds (uses config default if None)
            metadata: Optional task metadata

        Returns:
            Task ID for tracking

        Raises:
            RuntimeError: If queue is full
        """
        from deeplecture.domain import Task as TaskEntity
        from deeplecture.domain import TaskStatus

        task_id = self._generate_task_id(task_type, content_id)
        now = self._now_iso()

        task_entity = TaskEntity(
            id=task_id,
            type=task_type,
            content_id=content_id,
            status=TaskStatus.PENDING,
            progress=0,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._tasks[task_id] = task_entity
            snapshot = self._serialize_task(task_entity)

        # Persist to durable storage
        self._persist_snapshot(snapshot)

        # Create queue item
        item = _QueueItem(
            task_id=task_id,
            content_id=content_id,
            task_type=task_type,
            callable=task,
            timeout=timeout,
            metadata=metadata or {},
        )

        try:
            self._queue.put_nowait(item)
        except queue.Full as err:
            self._fail_task_internal(task_id, "Task queue is full")
            raise RuntimeError(f"Task queue is full (max {self._config.queue_max_size})") from err

        # Emit start event
        self._broadcast(content_id, {"event": "started", "task": snapshot})

        return task_id

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        self._maybe_cleanup()
        with self._lock:
            return self._tasks.get(task_id)

    def get_tasks_by_content(self, content_id: str) -> list[Task]:
        """Get all tasks for a content ID."""
        self._maybe_cleanup()
        with self._lock:
            return [t for t in self._tasks.values() if t.content_id == content_id]

    def update_task_progress(
        self,
        task_id: str,
        progress: int,
        emit_event: bool = True,
    ) -> Task | None:
        """Update task progress."""
        from deeplecture.domain import TaskStatus

        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.is_terminal():
                return task

            old_status = task.status
            task.progress = max(0, min(100, progress))
            if task.is_pending():
                task.status = TaskStatus.PROCESSING
            task.updated_at = self._now_iso()
            snapshot = self._serialize_task(task)
            content_id = task.content_id
            status_changed = task.status != old_status

        # Persist on status transitions (not every progress tick)
        if status_changed:
            self._persist_snapshot(snapshot)

        if emit_event:
            self._broadcast(content_id, {"event": "progress", "task": snapshot})
        return task

    def complete_task(self, task_id: str) -> Task | None:
        """Mark task as completed."""
        from deeplecture.domain import TaskStatus

        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if task.is_terminal():
                return task

            task.status = TaskStatus.READY
            task.progress = 100
            task.updated_at = self._now_iso()
            snapshot = self._serialize_task(task)
            content_id = task.content_id

        self._persist_snapshot(snapshot)
        self._broadcast(content_id, {"event": "completed", "task": snapshot})
        return task

    def fail_task(self, task_id: str, error: str) -> Task | None:
        """Mark task as failed."""
        return self._fail_task_internal(task_id, error)

    def _fail_task_internal(self, task_id: str, error: str) -> Task | None:
        """Internal fail implementation."""
        from deeplecture.domain import TaskStatus

        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if task.is_terminal():
                return task

            task.status = TaskStatus.ERROR
            task.error = error
            task.updated_at = self._now_iso()
            snapshot = self._serialize_task(task)
            content_id = task.content_id

        self._persist_snapshot(snapshot)
        self._broadcast(content_id, {"event": "failed", "task": snapshot})
        return task

    def _broadcast(self, content_id: str, event_data: dict[str, Any]) -> None:
        """Broadcast SSE event if publisher is configured."""
        if self._event_publisher:
            self._event_publisher.broadcast(content_id, event_data)

    def _persist_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Write task snapshot to durable storage if configured.

        Accepts an already-captured snapshot dict (built inside the lock)
        so that persistence operates on immutable data, avoiding races
        with concurrent mutations to the live Task entity.
        """
        if not self._storage:
            return
        import json as _json

        try:
            self._storage.save(
                {
                    "id": snapshot["id"],
                    "type": snapshot["type"],
                    "content_id": snapshot["content_id"],
                    "status": snapshot["status"],
                    "progress": snapshot["progress"],
                    "error": snapshot.get("error"),
                    "metadata_json": _json.dumps(snapshot.get("metadata") or {}),
                    "created_at": snapshot.get("created_at"),
                    "updated_at": snapshot.get("updated_at"),
                }
            )
        except Exception:
            logger.exception("Failed to persist task snapshot %s", snapshot.get("id"))

    @property
    def queue(self) -> queue.Queue[_QueueItem]:
        """Expose queue for WorkerPool."""
        return self._queue

    @property
    def config(self) -> TaskConfig:
        """Expose config for WorkerPool."""
        return self._config

    @staticmethod
    def _generate_task_id(task_type: str, content_id: str) -> str:
        timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        unique = uuid.uuid4().hex[:8]
        return f"{task_type}_{content_id}_{timestamp}_{unique}"

    @staticmethod
    def _now_iso() -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        return now.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _serialize_task(task: Task) -> dict[str, Any]:
        return {
            "id": task.id,
            "type": task.type,
            "content_id": task.content_id,
            "status": task.status.value if hasattr(task.status, "value") else task.status,
            "progress": task.progress,
            "error": task.error,
            "metadata": task.metadata,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def _maybe_cleanup(self) -> None:
        """Run cleanup if interval elapsed."""
        now = time.monotonic()
        if now - self._last_cleanup < self._config.cleanup_interval_seconds:
            return
        self._cleanup_expired_tasks()

    def _cleanup_expired_tasks(self) -> None:
        """Remove completed/failed tasks older than TTL."""
        now = time.monotonic()
        current_time = datetime.datetime.now(datetime.timezone.utc)
        expired_ids: list[str] = []

        with self._lock:
            self._last_cleanup = now

            for task_id, task in self._tasks.items():
                if not task.is_terminal():
                    continue

                try:
                    updated = datetime.datetime.fromisoformat(task.updated_at.replace("Z", "+00:00"))
                    age = (current_time - updated).total_seconds()
                    if age > self._config.completed_task_ttl_seconds:
                        expired_ids.append(task_id)
                except (ValueError, TypeError):
                    expired_ids.append(task_id)

            for task_id in expired_ids:
                del self._tasks[task_id]

        if expired_ids:
            logger.info("TaskManager cleanup: removed %d expired tasks", len(expired_ids))

        # Also clean expired tasks from durable storage
        if self._storage:
            self._storage.delete_expired_terminal(self._config.completed_task_ttl_seconds)


class WorkerPool:
    """
    Thread pool for executing task callables.

    Uses ThreadPoolExecutor with centralized timeout monitoring.
    Avoids thread-per-task overhead by using a single timeout monitor thread.
    """

    def __init__(self, task_manager: TaskManager) -> None:
        self._manager = task_manager
        self._config = task_manager.config
        self._shutdown = threading.Event()
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._consumer_thread: threading.Thread | None = None
        self._timeout_thread: threading.Thread | None = None
        self._started = False

        # Thread-safe tracking of pending futures with deadlines
        self._pending_futures: dict[str, tuple[concurrent.futures.Future, float, _QueueItem]] = {}
        self._futures_lock = threading.Lock()

    def start(self) -> None:
        """Start the worker pool."""
        if self._started:
            logger.warning("WorkerPool already started")
            return

        logger.info("Starting WorkerPool with %d workers", self._config.workers)

        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._config.workers,
            thread_name_prefix="task-worker",
        )

        self._consumer_thread = threading.Thread(
            target=self._consume_loop,
            name="task-queue-consumer",
            daemon=True,
        )
        self._consumer_thread.start()

        # Single timeout monitor thread (avoids thread-per-task overhead)
        self._timeout_thread = threading.Thread(
            target=self._timeout_monitor_loop,
            name="task-timeout-monitor",
            daemon=True,
        )
        self._timeout_thread.start()

        self._started = True

    def _consume_loop(self) -> None:
        """Consume queue items and dispatch to executor."""
        logger.info("Task queue consumer started")

        while not self._shutdown.is_set():
            try:
                item = self._manager.queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if self._executor is None:
                continue

            # Submit to executor
            future = self._executor.submit(self._execute_task, item)

            # Register with timeout monitor
            timeout = item.timeout or self._config.default_timeout_seconds
            deadline = time.monotonic() + timeout

            with self._futures_lock:
                self._pending_futures[item.task_id] = (future, deadline, item)

            # Add completion callback to clean up
            future.add_done_callback(lambda f, task_id=item.task_id: self._on_future_done(task_id))

        logger.info("Task queue consumer stopped")

    def _on_future_done(self, task_id: str) -> None:
        """Remove completed future from tracking."""
        with self._futures_lock:
            self._pending_futures.pop(task_id, None)

    def _timeout_monitor_loop(self) -> None:
        """Single thread to monitor all pending futures for timeout."""
        logger.info("Timeout monitor started")
        check_interval = 1.0  # Check every second

        while not self._shutdown.is_set():
            now = time.monotonic()
            timed_out: list[tuple[str, concurrent.futures.Future, _QueueItem]] = []

            with self._futures_lock:
                for task_id, (future, deadline, item) in list(self._pending_futures.items()):
                    if now >= deadline and not future.done():
                        timed_out.append((task_id, future, item))
                        del self._pending_futures[task_id]

            # Process timeouts outside lock
            for task_id, future, item in timed_out:
                future.cancel()
                timeout = item.timeout or self._config.default_timeout_seconds
                error_msg = f"Task timed out after {timeout}s"
                logger.error("Task %s timed out", task_id)
                self._manager.fail_task(task_id, error_msg)

            time.sleep(check_interval)

        logger.info("Timeout monitor stopped")

    def _execute_task(self, item: _QueueItem) -> None:
        """Execute task callable."""
        thread_name = threading.current_thread().name
        logger.info("[%s] Executing task %s (%s)", thread_name, item.task_id, item.task_type)

        ctx = TaskContext(
            task_id=item.task_id,
            content_id=item.content_id,
            task_type=item.task_type,
            manager=self._manager,
        )

        # Mark as processing
        self._manager.update_task_progress(item.task_id, 1, emit_event=False)

        try:
            item.callable(ctx)
            self._manager.complete_task(item.task_id)
            logger.info("[%s] Task %s completed", thread_name, item.task_id)
        except Exception as exc:
            logger.error("[%s] Task %s failed: %s", thread_name, item.task_id, exc, exc_info=True)
            self._manager.fail_task(item.task_id, str(exc))
        finally:
            self._manager.queue.task_done()

    def shutdown(self, wait: bool = True, timeout: float = 5.0) -> None:
        """Shutdown the worker pool."""
        logger.info("Shutting down WorkerPool...")
        self._shutdown.set()

        if self._executor:
            self._executor.shutdown(wait=wait, cancel_futures=not wait)

        if wait:
            if self._consumer_thread:
                self._consumer_thread.join(timeout=timeout)
            if self._timeout_thread:
                self._timeout_thread.join(timeout=timeout)

        logger.info("WorkerPool shutdown complete")

    @property
    def is_running(self) -> bool:
        """Check if pool is running."""
        return self._started and not self._shutdown.is_set()
