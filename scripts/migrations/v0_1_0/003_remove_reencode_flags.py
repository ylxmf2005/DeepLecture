"""
Migration: Drop requires_reencode / reencode_reason columns from content_metadata.

Why: these fields are deprecated and should not exist in the schema.
This migration rebuilds the table without those columns in an idempotent way.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class Migration:
    id = "v0_1_0_003_remove_reencode_flags"
    description = "Drop requires_reencode/reencode_reason from content_metadata"

    @staticmethod
    def run() -> int:
        project_root = Path(__file__).parent.parent.parent.parent
        db_path = project_root / "data" / "deeplecture.db"

        if not db_path.exists():
            logger.info("Database not found, skipping")
            return 0

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("PRAGMA table_info(content_metadata)")
            cols = [row[1] for row in cur.fetchall()]
            if "requires_reencode" not in cols and "reencode_reason" not in cols:
                logger.info("Columns already absent, no work to do")
                return 0

            logger.info("Rebuilding content_metadata without reencode columns")
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("BEGIN")

            conn.execute(
                """
                CREATE TABLE content_metadata_new (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    type VARCHAR(20) NOT NULL,
                    original_filename TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    source_file TEXT NOT NULL,
                    video_file TEXT,
                    subtitle_path TEXT,
                    translated_subtitle_path TEXT,
                    enhanced_subtitle_path TEXT,
                    notes_path TEXT,
                    timeline_path TEXT,
                    ask_conversations_dir TEXT,
                    screenshots_dir TEXT,
                    source_type VARCHAR(20) NOT NULL,
                    source_url TEXT,
                    pdf_page_count INTEGER,
                    video_status VARCHAR(20) NOT NULL,
                    subtitle_status VARCHAR(20) NOT NULL,
                    translation_status VARCHAR(20) NOT NULL,
                    enhanced_status VARCHAR(20) NOT NULL,
                    timeline_status VARCHAR(20) NOT NULL,
                    notes_status VARCHAR(20) NOT NULL,
                    video_job_id VARCHAR(100),
                    subtitle_job_id VARCHAR(100),
                    translation_job_id VARCHAR(100),
                    enhanced_job_id VARCHAR(100),
                    timeline_job_id VARCHAR(100),
                    notes_job_id VARCHAR(100)
                )
                """
            )

            conn.execute(
                """
                INSERT INTO content_metadata_new (
                    id, type, original_filename, created_at, updated_at, source_file,
                    video_file, subtitle_path, translated_subtitle_path, enhanced_subtitle_path,
                    notes_path, timeline_path, ask_conversations_dir, screenshots_dir,
                    source_type, source_url, pdf_page_count,
                    video_status, subtitle_status, translation_status, enhanced_status,
                    timeline_status, notes_status,
                    video_job_id, subtitle_job_id, translation_job_id, enhanced_job_id, timeline_job_id, notes_job_id
                )
                SELECT
                    id, type, original_filename, created_at, updated_at, source_file,
                    video_file, subtitle_path, translated_subtitle_path, enhanced_subtitle_path,
                    notes_path, timeline_path, ask_conversations_dir, screenshots_dir,
                    source_type, source_url, pdf_page_count,
                    video_status, subtitle_status, translation_status, enhanced_status,
                    timeline_status, notes_status,
                    video_job_id, subtitle_job_id, translation_job_id, enhanced_job_id, timeline_job_id, notes_job_id
                FROM content_metadata
                """
            )

            conn.execute("DROP TABLE content_metadata")
            conn.execute("ALTER TABLE content_metadata_new RENAME TO content_metadata")
            conn.execute("COMMIT")
            logger.info("Migration completed")
            return 1
        except Exception as exc:
            conn.execute("ROLLBACK")
            logger.error("Migration failed: %s", exc)
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.close()
