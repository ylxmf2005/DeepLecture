from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from deeplecture.infrastructure.workers.task_queue import TaskConfig, TaskManager, WorkerPool

if TYPE_CHECKING:
    from collections.abc import Callable


def _make_config(**overrides: Any) -> TaskConfig:
    defaults: dict[str, Any] = {
        "workers": 1,
        "queue_max_size": 10,
        "default_timeout_seconds": 5.0,
        "completed_task_ttl_seconds": 60,
        "cleanup_interval_seconds": 60,
    }
    defaults.update(overrides)
    return TaskConfig(**defaults)


def _wait_until(predicate: Callable[[], bool], *, timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for condition")


def test_worker_pool_awaits_async_tasks() -> None:
    manager = TaskManager(
        TaskConfig(
            workers=1,
            queue_max_size=10,
            default_timeout_seconds=5.0,
            completed_task_ttl_seconds=60,
            cleanup_interval_seconds=60,
        )
    )
    pool = WorkerPool(manager)
    pool.start()

    ran: list[str] = []

    async def task(ctx: object) -> None:
        await asyncio.sleep(0.02)
        ran.append("ok")

    try:
        task_id = manager.submit(content_id="c1", task_type="t1", task=task)
        _wait_until(lambda: (manager.get_task(task_id) is not None and manager.get_task(task_id).is_ready()))
        assert ran == ["ok"]
    finally:
        pool.shutdown(wait=True)


def test_worker_pool_marks_async_exceptions_as_failed() -> None:
    manager = TaskManager(
        TaskConfig(
            workers=1,
            queue_max_size=10,
            default_timeout_seconds=5.0,
            completed_task_ttl_seconds=60,
            cleanup_interval_seconds=60,
        )
    )
    pool = WorkerPool(manager)
    pool.start()

    async def task(ctx: object) -> None:
        await asyncio.sleep(0)
        raise ValueError("boom")

    try:
        task_id = manager.submit(content_id="c1", task_type="t1", task=task)
        _wait_until(lambda: (manager.get_task(task_id) is not None and manager.get_task(task_id).is_error()))  # type: ignore[union-attr]
        assert manager.get_task(task_id).error is not None  # type: ignore[union-attr]
        assert "boom" in manager.get_task(task_id).error  # type: ignore[operator,union-attr]
    finally:
        pool.shutdown(wait=True)


# =============================================================================
# PERSISTENCE INTEGRATION TESTS
# =============================================================================


class TestTaskManagerPersistence:
    """Test TaskManager write-through to SQLiteTaskStorage."""

    def test_submit_persists_to_storage(self, tmp_path) -> None:
        from deeplecture.infrastructure.repositories.sqlite_task_storage import SQLiteTaskStorage

        storage = SQLiteTaskStorage(tmp_path / "tasks.db")
        manager = TaskManager(_make_config(), task_storage=storage)

        def noop(_ctx):
            pass

        task_id = manager.submit(content_id="c1", task_type="subtitle_generation", task=noop)
        row = storage.get(task_id)
        assert row is not None
        assert row["type"] == "subtitle_generation"
        assert row["status"] in ("pending", "processing")

    def test_complete_persists_terminal_state(self, tmp_path) -> None:
        from deeplecture.infrastructure.repositories.sqlite_task_storage import SQLiteTaskStorage

        storage = SQLiteTaskStorage(tmp_path / "tasks.db")
        manager = TaskManager(_make_config(), task_storage=storage)

        def noop(_ctx):
            pass

        task_id = manager.submit(content_id="c1", task_type="t1", task=noop)
        manager.complete_task(task_id)

        row = storage.get(task_id)
        assert row is not None
        assert row["status"] == "ready"
        assert row["progress"] == 100

    def test_fail_persists_error(self, tmp_path) -> None:
        from deeplecture.infrastructure.repositories.sqlite_task_storage import SQLiteTaskStorage

        storage = SQLiteTaskStorage(tmp_path / "tasks.db")
        manager = TaskManager(_make_config(), task_storage=storage)

        def noop(_ctx):
            pass

        task_id = manager.submit(content_id="c1", task_type="t1", task=noop)
        manager.fail_task(task_id, "something broke")

        row = storage.get(task_id)
        assert row is not None
        assert row["status"] == "error"
        assert "something broke" in row["error"]

    def test_startup_reconciliation_via_storage(self, tmp_path) -> None:
        from deeplecture.infrastructure.repositories.sqlite_task_storage import SQLiteTaskStorage

        storage = SQLiteTaskStorage(tmp_path / "tasks.db")

        # Simulate pre-existing inflight tasks from a crashed server
        storage.save(
            {
                "id": "old_task",
                "type": "subtitle_generation",
                "content_id": "c1",
                "status": "processing",
                "progress": 50,
                "error": None,
                "metadata_json": "{}",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:05Z",
            }
        )

        # Creating a new TaskManager should reconcile inflight tasks
        _manager = TaskManager(_make_config(), task_storage=storage)

        row = storage.get("old_task")
        assert row["status"] == "error"
        assert "restart" in row["error"].lower()

    def test_no_storage_works_as_before(self) -> None:
        """TaskManager without storage should work identically to before."""
        manager = TaskManager(_make_config())

        def noop(_ctx):
            pass

        task_id = manager.submit(content_id="c1", task_type="t1", task=noop)
        task = manager.get_task(task_id)
        assert task is not None
        assert task.status.value == "pending"
