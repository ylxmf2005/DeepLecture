"""
Migration: Import JSON metadata files into SQLite database.

This is a one-time migration that reads all existing metadata.json files
and imports them into the new SQLite database. After this migration,
the JSON files are no longer the source of truth.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class Migration:
    id = "v0.1.0_json_to_sqlite"
    description = "Import JSON metadata files into SQLite database"

    @staticmethod
    def run() -> int:
        """Import all JSON metadata into SQLite."""
        from contextlib import contextmanager
        from pathlib import Path
        from typing import Generator

        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker

        from deeplecture.storage.models import Base, ContentMetadataModel

        project_root = Path(__file__).parent.parent.parent.parent
        data_dir = project_root / "data"
        content_dir = data_dir / "content"
        if not content_dir.exists():
            logger.info("No content directory found, skipping JSON import")
            return 0

        db_path = data_dir / "deeplecture.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

        @contextmanager
        def get_session() -> Generator[Session, None, None]:
            session = SessionLocal()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        imported_count = 0

        for content_id in os.listdir(content_dir):
            content_path = os.path.join(content_dir, content_id)
            if not os.path.isdir(content_path):
                continue

            metadata_path = os.path.join(content_path, "metadata.json")
            if not os.path.exists(metadata_path):
                continue

            # Each record in its own transaction for isolation
            try:
                with get_session() as session:
                    # Check if already in database
                    existing = session.get(ContentMetadataModel, content_id)
                    if existing:
                        logger.debug("Content %s already in database, skipping", content_id)
                        continue

                    with open(metadata_path, encoding="utf-8") as f:
                        data = json.load(f)

                    # Apply legacy migration inline
                    data = _migrate_legacy_format(data)

                    # Convert to model and save
                    model = ContentMetadataModel.from_dict(data)
                    session.add(model)
                    imported_count += 1
                    logger.debug("Imported content %s", content_id)

            except Exception as e:
                # Transaction is automatically rolled back by get_session context manager
                logger.error("Failed to import %s: %s", content_id, e)

        logger.info("Imported %d content records from JSON to SQLite", imported_count)
        return imported_count


def _migrate_legacy_format(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy metadata format inline during import."""
    # Skip if already migrated
    if "video_status" in data:
        for legacy_field in ["status", "processing_job_id", "has_subtitles", "has_translation", "has_enhanced_subtitles"]:
            data.pop(legacy_field, None)
        return data

    # Migrate video status
    legacy_status = data.pop("status", None)
    video_file = data.get("video_file")
    if video_file:
        data["video_status"] = "processing" if legacy_status == "processing" else "ready"
    else:
        data["video_status"] = "processing" if legacy_status == "processing" else "none"

    # Migrate subtitle status
    has_subtitles = data.pop("has_subtitles", None)
    data["subtitle_status"] = "ready" if (has_subtitles or data.get("subtitle_path")) else "none"

    # Migrate translation status
    has_translation = data.pop("has_translation", None)
    data["translation_status"] = "ready" if (has_translation or data.get("translated_subtitle_path")) else "none"

    # Migrate enhanced status
    has_enhanced = data.pop("has_enhanced_subtitles", None)
    data["enhanced_status"] = "ready" if (has_enhanced or data.get("enhanced_subtitle_path")) else "none"

    # Migrate timeline/notes status
    data["timeline_status"] = "ready" if data.get("timeline_path") else "none"
    data["notes_status"] = "ready" if data.get("notes_path") else "none"

    # Remove legacy job id
    data.pop("processing_job_id", None)

    return data
