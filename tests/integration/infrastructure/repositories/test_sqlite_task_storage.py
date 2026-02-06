"""SQLiteTaskStorage integration tests.

Tests persistence, startup reconciliation, and TTL cleanup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from deeplecture.infrastructure.repositories.sqlite_task_storage import SQLiteTaskStorage

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteTaskStorage:
    """Create a fresh SQLiteTaskStorage for each test."""
    return SQLiteTaskStorage(tmp_path / "tasks.db")


def _make_task_row(
    task_id: str = "test_task_1",
    task_type: str = "subtitle_generation",
    content_id: str = "content_abc",
    status: str = "processing",
    progress: int = 50,
    error: str | None = None,
    metadata_json: str | None = None,
) -> dict:
    """Helper to build a task dict for save()."""
    return {
        "id": task_id,
        "type": task_type,
        "content_id": content_id,
        "status": status,
        "progress": progress,
        "error": error,
        "metadata_json": metadata_json or "{}",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:05Z",
    }


class TestSaveAndGet:
    """Test basic CRUD operations."""

    def test_save_and_get_roundtrip(self, storage: SQLiteTaskStorage) -> None:
        row = _make_task_row()
        storage.save(row)
        result = storage.get(row["id"])
        assert result is not None
        assert result["id"] == row["id"]
        assert result["type"] == "subtitle_generation"
        assert result["status"] == "processing"
        assert result["progress"] == 50

    def test_get_nonexistent_returns_none(self, storage: SQLiteTaskStorage) -> None:
        assert storage.get("nonexistent") is None

    def test_save_upserts_on_conflict(self, storage: SQLiteTaskStorage) -> None:
        row = _make_task_row(status="processing", progress=50)
        storage.save(row)

        row["status"] = "ready"
        row["progress"] = 100
        storage.save(row)

        result = storage.get(row["id"])
        assert result["status"] == "ready"
        assert result["progress"] == 100

    def test_list_by_content(self, storage: SQLiteTaskStorage) -> None:
        storage.save(_make_task_row(task_id="t1", content_id="c1"))
        storage.save(_make_task_row(task_id="t2", content_id="c1"))
        storage.save(_make_task_row(task_id="t3", content_id="c2"))

        results = storage.list_by_content("c1")
        assert len(results) == 2
        assert {r["id"] for r in results} == {"t1", "t2"}


class TestStartupReconciliation:
    """Test mark_inflight_as_error for crash recovery."""

    def test_marks_pending_and_processing_as_error(self, storage: SQLiteTaskStorage) -> None:
        storage.save(_make_task_row(task_id="t_pending", status="pending"))
        storage.save(_make_task_row(task_id="t_processing", status="processing"))
        storage.save(_make_task_row(task_id="t_ready", status="ready"))
        storage.save(_make_task_row(task_id="t_error", status="error"))

        affected = storage.mark_inflight_as_error("Server restart")
        assert affected == 2

        assert storage.get("t_pending")["status"] == "error"
        assert storage.get("t_processing")["status"] == "error"
        assert storage.get("t_ready")["status"] == "ready"
        assert storage.get("t_error")["status"] == "error"

    def test_marks_include_error_message(self, storage: SQLiteTaskStorage) -> None:
        storage.save(_make_task_row(task_id="t1", status="processing"))
        storage.mark_inflight_as_error("Task interrupted by server restart")
        result = storage.get("t1")
        assert "server restart" in result["error"].lower()

    def test_returns_zero_when_nothing_inflight(self, storage: SQLiteTaskStorage) -> None:
        storage.save(_make_task_row(task_id="t1", status="ready"))
        assert storage.mark_inflight_as_error("restart") == 0


class TestTTLCleanup:
    """Test expired terminal task cleanup."""

    def test_deletes_expired_terminal_tasks(self, storage: SQLiteTaskStorage) -> None:
        from datetime import datetime, timezone

        # Create a task with old updated_at timestamp
        old_task = _make_task_row(task_id="old", status="ready")
        old_task["updated_at"] = "2020-01-01T00:00:00Z"
        storage.save(old_task)

        # Create a recent task with current timestamp
        recent_task = _make_task_row(task_id="recent", status="ready")
        recent_task["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        storage.save(recent_task)

        deleted = storage.delete_expired_terminal(ttl_seconds=60)
        assert deleted >= 1
        assert storage.get("old") is None
        assert storage.get("recent") is not None

    def test_does_not_delete_active_tasks(self, storage: SQLiteTaskStorage) -> None:
        old_active = _make_task_row(task_id="active", status="processing")
        old_active["updated_at"] = "2020-01-01T00:00:00Z"
        storage.save(old_active)

        deleted = storage.delete_expired_terminal(ttl_seconds=60)
        assert deleted == 0
        assert storage.get("active") is not None
