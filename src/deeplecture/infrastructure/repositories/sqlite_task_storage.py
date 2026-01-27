"""SQLite implementation of TaskStorageProtocol."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from deeplecture.domain import Task, TaskStatus

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

UTC = getattr(datetime, "UTC", timezone.utc)


class SQLiteTaskStorage:
    """
    SQLite-based task state persistence.

    Enables task state to survive process restarts and be shared
    across multiple worker processes via the shared database file.

    Uses WAL mode for better concurrent read/write performance.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_content_id ON tasks(content_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    def save(self, task: Task) -> None:
        """Save or update a task."""
        metadata_json = json.dumps(task.metadata) if task.metadata else "{}"
        status_value = task.status.value if hasattr(task.status, "value") else str(task.status)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    id, type, content_id, status, progress,
                    error, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.type,
                    task.content_id,
                    status_value,
                    task.progress,
                    task.error,
                    metadata_json,
                    task.created_at,
                    task.updated_at,
                ),
            )
            conn.commit()

    def get(self, task_id: str) -> Task | None:
        """Get task by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_entity(row)

    def get_by_content(self, content_id: str) -> Sequence[Task]:
        """Get all tasks for a content ID."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE content_id = ? ORDER BY created_at DESC",
                (content_id,),
            ).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def get_active_tasks(self) -> Sequence[Task]:
        """Get all non-terminal tasks (pending or processing)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status IN (?, ?) ORDER BY created_at ASC",
                (TaskStatus.PENDING.value, TaskStatus.PROCESSING.value),
            ).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def delete(self, task_id: str) -> bool:
        """Delete a task by ID."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_expired(self, ttl_seconds: int) -> int:
        """Remove terminal tasks older than TTL."""
        cutoff = datetime.now(UTC)
        deleted_count = 0

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, updated_at FROM tasks WHERE status IN (?, ?)",
                (TaskStatus.READY.value, TaskStatus.ERROR.value),
            ).fetchall()

            expired_ids: list[str] = []
            for row in rows:
                try:
                    updated_str = row["updated_at"]
                    if updated_str.endswith("Z"):
                        updated_str = updated_str[:-1] + "+00:00"
                    updated = datetime.fromisoformat(updated_str)
                    age = (cutoff - updated).total_seconds()
                    if age > ttl_seconds:
                        expired_ids.append(row["id"])
                except (ValueError, TypeError):
                    expired_ids.append(row["id"])

            if expired_ids:
                placeholders = ",".join("?" * len(expired_ids))
                cursor = conn.execute(f"DELETE FROM tasks WHERE id IN ({placeholders})", expired_ids)
                conn.commit()
                deleted_count = cursor.rowcount

        return deleted_count

    def _row_to_entity(self, row: sqlite3.Row) -> Task:
        """Convert database row to Task entity."""
        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                metadata = {}

        return Task(
            id=row["id"],
            type=row["type"],
            content_id=row["content_id"],
            status=TaskStatus(row["status"]),
            progress=row["progress"],
            error=row["error"],
            metadata=metadata,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
