from __future__ import annotations

import datetime
import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from deeplecture.infra.sse_manager import SSEManager


@dataclass
class Task:
    """In-memory task representation."""

    id: str
    type: str
    content_id: str
    status: str  # pending, processing, ready, error
    progress: int = 0
    result_path: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class TaskManager:
    """
    Pure in-memory task coordinator that emits SSE events.
    No database persistence - tasks exist only in memory.
    """

    MAX_QUEUE_SIZE = 1000

    def __init__(self, sse_manager: Optional[SSEManager] = None) -> None:
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.RLock()
        self.task_queue: queue.Queue[str] = queue.Queue(maxsize=self.MAX_QUEUE_SIZE)
        self._sse = sse_manager

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def submit_task(
        self, content_id: str, task_type: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        task_id = self._generate_task_id(task_type, content_id)
        now = self._now_iso()

        task = Task(
            id=task_id,
            type=task_type,
            content_id=content_id,
            status="pending",
            progress=0,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._tasks[task_id] = task

        try:
            self.task_queue.put_nowait(task_id)
        except queue.Full:
            self.fail_task(task_id, "Task queue is full. Please try again later.")
            raise RuntimeError(f"Task queue is full (max {self.MAX_QUEUE_SIZE}). Cannot submit task.")

        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_tasks_by_content(self, content_id: str) -> List[Task]:
        with self._lock:
            return [t for t in self._tasks.values() if t.content_id == content_id]

    def update_task_progress(self, task_id: str, progress: int, emit_event: bool = True) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if task.status in ("ready", "error"):
                return task

            task.progress = progress
            if task.status == "pending":
                task.status = "processing"
            task.updated_at = self._now_iso()
            content_id = task.content_id
            snapshot = self._serialize_task(task)

        if emit_event:
            self._broadcast(content_id, {"event": "progress", "task": snapshot})
        return task

    def complete_task(self, task_id: str, result_path: str) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            task.status = "ready"
            task.progress = 100
            task.result_path = result_path
            task.updated_at = self._now_iso()
            content_id = task.content_id
            snapshot = self._serialize_task(task)

        self._broadcast(content_id, {"event": "completed", "task": snapshot})
        return task

    def fail_task(self, task_id: str, error: str) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            task.status = "error"
            task.error = error
            task.updated_at = self._now_iso()
            content_id = task.content_id
            snapshot = self._serialize_task(task)

        self._broadcast(content_id, {"event": "failed", "task": snapshot})
        return task

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _broadcast(self, content_id: str, event_data: Dict[str, Any]) -> None:
        if self._sse:
            self._sse.broadcast(content_id, event_data)

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
    def _serialize_task(task: Task) -> Dict[str, Any]:
        return {
            "id": task.id,
            "type": task.type,
            "content_id": task.content_id,
            "status": task.status,
            "progress": task.progress,
            "result_path": task.result_path,
            "error": task.error,
            "metadata": task.metadata,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
