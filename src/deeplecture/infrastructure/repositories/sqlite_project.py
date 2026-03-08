"""SQLite implementation of ProjectStorageProtocol."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING

from deeplecture.domain.entities.project import Project

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class SQLiteProjectStorage:
    """SQLite-based project persistence, sharing the same metadata.db."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    color TEXT DEFAULT '',
                    icon TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get(self, project_id: str) -> Project | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_entity(row)

    def save(self, project: Project) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO projects (
                    id, name, description, color, icon, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.name,
                    project.description,
                    project.color,
                    project.icon,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
            conn.commit()

    def delete(self, project_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self) -> list[Project]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
            return [self._row_to_entity(row) for row in rows]

    def count_content(self, project_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM content_metadata WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            return row["cnt"] if row else 0

    def clear_content_project(self, project_id: str) -> int:
        """Set project_id = NULL on all content belonging to the given project."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE content_metadata SET project_id = NULL WHERE project_id = ?",
                (project_id,),
            )
            conn.commit()
            return cursor.rowcount

    def update_content_project(self, content_id: str, project_id: str | None) -> bool:
        """Set project_id on a single content item. Returns True if row was found."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE content_metadata SET project_id = ? WHERE id = ?",
                (project_id, content_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_entity(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            color=row["color"] or "",
            icon=row["icon"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
