"""SQLite implementation of MetadataStorageProtocol."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Final

from deeplecture.domain import ContentMetadata, ContentType

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

UTC = getattr(datetime, "UTC", timezone.utc)

_OPTIONAL_COLUMNS: Final[dict[str, str]] = {
    "video_file": "TEXT",
    "pdf_page_count": "INTEGER",
    "timeline_path": "TEXT",
    "video_job_id": "TEXT",
    "timeline_job_id": "TEXT",
    "enhance_translate_status": "TEXT DEFAULT 'none'",
    "enhance_translate_job_id": "TEXT",
    "project_id": "TEXT",
}


class SQLiteMetadataStorage:
    """
    SQLite-based content metadata storage.

    Implements MetadataStorageProtocol.
    Uses simple sqlite3 instead of SQLAlchemy for clarity.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        """
        Best-effort schema evolution for additive columns.

        Without this, existing DBs created before new fields were introduced
        will fail at INSERT/SELECT when code expects the new columns.

        Security: Column names are validated against a whitelist to prevent
        SQL injection via dynamic ALTER TABLE statements.
        """
        existing = {row[1] for row in conn.execute("PRAGMA table_info(content_metadata)").fetchall()}
        for name, sql_type in _OPTIONAL_COLUMNS.items():
            if name not in existing:
                # Whitelist validation: only allow known column names
                if name not in _OPTIONAL_COLUMNS:
                    raise ValueError(f"Unknown column name: {name}")
                # Whitelist validation: only allow known SQL types
                allowed_types = {"TEXT", "INTEGER"}
                base_type = sql_type.split()[0].upper()
                if base_type not in allowed_types:
                    raise ValueError(f"Invalid SQL type: {sql_type}")
                # Safe to use f-string since name/type are from hardcoded whitelist
                conn.execute(f"ALTER TABLE content_metadata ADD COLUMN {name} {sql_type}")

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_metadata (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    video_file TEXT,
                    pdf_page_count INTEGER,
                    timeline_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'local',
                    source_url TEXT,
                    video_status TEXT NOT NULL DEFAULT 'none',
                    subtitle_status TEXT NOT NULL DEFAULT 'none',
                    enhance_translate_status TEXT NOT NULL DEFAULT 'none',
                    timeline_status TEXT NOT NULL DEFAULT 'none',
                    notes_status TEXT NOT NULL DEFAULT 'none',
                    video_job_id TEXT,
                    subtitle_job_id TEXT,
                    enhance_translate_job_id TEXT,
                    timeline_job_id TEXT
                )
            """)
            self._ensure_columns(conn)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get(self, content_id: str) -> ContentMetadata | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM content_metadata WHERE id = ?", (content_id,)).fetchone()

            if row is None:
                return None

            return self._row_to_entity(row)

    def save(self, metadata: ContentMetadata) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO content_metadata (
                    id, type, original_filename, source_file,
                    video_file, pdf_page_count, timeline_path,
                    created_at, updated_at, source_type, source_url,
                    video_status, subtitle_status, enhance_translate_status,
                    timeline_status, notes_status,
                    video_job_id, subtitle_job_id, enhance_translate_job_id, timeline_job_id,
                    project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.id,
                    metadata.type.value,
                    metadata.original_filename,
                    metadata.source_file,
                    metadata.video_file,
                    metadata.pdf_page_count,
                    metadata.timeline_path,
                    metadata.created_at.isoformat(),
                    metadata.updated_at.isoformat(),
                    metadata.source_type,
                    metadata.source_url,
                    metadata.video_status,
                    metadata.subtitle_status,
                    metadata.enhance_translate_status,
                    metadata.timeline_status,
                    metadata.notes_status,
                    metadata.video_job_id,
                    metadata.subtitle_job_id,
                    metadata.enhance_translate_job_id,
                    metadata.timeline_job_id,
                    metadata.project_id,
                ),
            )
            conn.commit()

    def delete(self, content_id: str) -> bool:
        """Delete metadata by content ID. Returns True if deleted, False if not found."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM content_metadata WHERE id = ?", (content_id,))
            conn.commit()
            return cursor.rowcount > 0

    def exists(self, content_id: str) -> bool:
        """Check if metadata exists for content ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM content_metadata WHERE id = ? LIMIT 1",
                (content_id,),
            ).fetchone()
            return row is not None

    def list_all(
        self,
        include_deleted: bool = False,
        *,
        project_id: str | None = None,
    ) -> list[ContentMetadata]:
        """List content metadata, optionally filtered by project.

        Args:
            include_deleted: Ignored (no soft delete).
            project_id: None → all content, "none" → ungrouped only,
                         UUID string → content in that project.
        """
        if project_id is None:
            query = "SELECT * FROM content_metadata ORDER BY created_at DESC"
            params: tuple[str, ...] = ()
        elif project_id == "none":
            query = "SELECT * FROM content_metadata WHERE project_id IS NULL ORDER BY created_at DESC"
            params = ()
        else:
            query = "SELECT * FROM content_metadata WHERE project_id = ? ORDER BY created_at DESC"
            params = (project_id,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def _row_to_entity(self, row: sqlite3.Row) -> ContentMetadata:
        return ContentMetadata(
            id=row["id"],
            type=ContentType(row["type"]),
            original_filename=row["original_filename"],
            source_file=row["source_file"],
            video_file=row["video_file"],
            pdf_page_count=row["pdf_page_count"],
            timeline_path=row["timeline_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            source_type=row["source_type"],
            source_url=row["source_url"],
            video_status=row["video_status"],
            subtitle_status=row["subtitle_status"],
            enhance_translate_status=row["enhance_translate_status"],
            timeline_status=row["timeline_status"],
            notes_status=row["notes_status"],
            video_job_id=row["video_job_id"],
            subtitle_job_id=row["subtitle_job_id"],
            enhance_translate_job_id=row["enhance_translate_job_id"],
            timeline_job_id=row["timeline_job_id"],
            project_id=row["project_id"],
        )
