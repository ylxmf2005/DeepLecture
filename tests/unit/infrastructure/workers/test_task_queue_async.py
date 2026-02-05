from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from deeplecture.infrastructure.workers.task_queue import TaskConfig, TaskManager, WorkerPool

if TYPE_CHECKING:
    from collections.abc import Callable


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
        _wait_until(lambda: (manager.get_task(task_id) is not None and manager.get_task(task_id).is_error()))
        assert manager.get_task(task_id).error is not None
        assert "boom" in manager.get_task(task_id).error
    finally:
        pool.shutdown(wait=True)
