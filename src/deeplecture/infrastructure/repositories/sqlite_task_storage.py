"""SQLite-based task state persistence.

Provides durable storage for task state, enabling crash recovery
and restart reconciliation. Follows the same patterns as sqlite_metadata.py.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from typing import Any

UTC = getattr(datetime, "UTC", timezone.utc)


class SQLiteTaskStorage:
    """
    SQLite-backed task state persistence.

    Stores current task state snapshots (not event log).
    Used for:
    - Crash recovery: mark inflight tasks as error on startup
    - SSE reconnect: provide accurate snapshots after restart
    - TTL cleanup: remove old terminal tasks
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            # Enable WAL for concurrent read/write from multiple threads
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_content_id ON tasks(content_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save(self, task: dict[str, Any]) -> None:
        """Upsert a task state snapshot."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                    (id, type, content_id, status, progress, error, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["id"],
                    task["type"],
                    task["content_id"],
                    task["status"],
                    task.get("progress", 0),
                    task.get("error"),
                    task.get("metadata_json", "{}"),
                    task["created_at"],
                    task["updated_at"],
                ),
            )
            conn.commit()

    def get(self, task_id: str) -> dict[str, Any] | None:
        """Get a task by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            return dict(row)

    def list_by_content(self, content_id: str) -> list[dict[str, Any]]:
        """List all tasks for a content ID."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE content_id = ? ORDER BY created_at DESC",
                (content_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_inflight_as_error(self, error_message: str) -> int:
        """
        Mark all pending/processing tasks as error.

        Called on startup to reconcile tasks that were interrupted
        by a server crash or restart.

        Returns:
            Number of affected rows.
        """
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE tasks
                SET status = 'error', error = ?, updated_at = ?
                WHERE status IN ('pending', 'processing')
                """,
                (error_message, now),
            )
            conn.commit()
            return cursor.rowcount

    def delete_expired_terminal(self, ttl_seconds: int) -> int:
        """
        Delete terminal tasks (ready/error) older than TTL.

        Returns:
            Number of deleted rows.
        """
        now = datetime.now(UTC)
        with self._connect() as conn:
            # SQLite datetime comparison with ISO format
            # We compute the cutoff time and compare as strings
            cutoff = datetime.fromtimestamp(now.timestamp() - ttl_seconds, tz=UTC).isoformat().replace("+00:00", "Z")
            cursor = conn.execute(
                """
                DELETE FROM tasks
                WHERE status IN ('ready', 'error')
                AND updated_at < ?
                """,
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount
