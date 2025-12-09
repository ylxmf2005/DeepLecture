"""SQLite-based metadata storage with automatic locking."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional

from sqlalchemy import select

from deeplecture.app_context import AppContext, get_app_context
from deeplecture.dto.storage import ContentMetadata
from deeplecture.storage.database import get_session, init_db
from deeplecture.storage.models import ContentMetadataModel

logger = logging.getLogger(__name__)
UTC = getattr(datetime, "UTC", timezone.utc)

# Feature status type
FeatureStatus = Literal["none", "processing", "ready", "error"]

# Feature names for status updates
FeatureName = Literal["video", "subtitle", "translation", "enhanced", "timeline", "notes"]


def _model_to_dto(model: ContentMetadataModel) -> ContentMetadata:
    """Convert SQLAlchemy model to DTO."""
    # Timestamps are stored as naive UTC, output with Z suffix for consistency
    created_at = f"{model.created_at.isoformat()}Z" if model.created_at else ""
    updated_at = f"{model.updated_at.isoformat()}Z" if model.updated_at else ""
    return ContentMetadata(
        id=model.id,
        type=model.type,
        original_filename=model.original_filename,
        created_at=created_at,
        updated_at=updated_at,
        source_file=model.source_file,
        video_file=model.video_file,
        subtitle_path=model.subtitle_path,
        translated_subtitle_path=model.translated_subtitle_path,
        enhanced_subtitle_path=model.enhanced_subtitle_path,
        source_type=model.source_type,
        source_url=model.source_url,
        pdf_page_count=model.pdf_page_count,
        notes_path=model.notes_path,
        ask_conversations_dir=model.ask_conversations_dir,
        screenshots_dir=model.screenshots_dir,
        timeline_path=model.timeline_path,
        video_status=model.video_status,
        subtitle_status=model.subtitle_status,
        translation_status=model.translation_status,
        enhanced_status=model.enhanced_status,
        timeline_status=model.timeline_status,
        notes_status=model.notes_status,
        video_job_id=model.video_job_id,
        subtitle_job_id=model.subtitle_job_id,
        translation_job_id=model.translation_job_id,
        enhanced_job_id=model.enhanced_job_id,
        timeline_job_id=model.timeline_job_id,
        notes_job_id=model.notes_job_id,
    )


def _dto_to_model(dto: ContentMetadata) -> ContentMetadataModel:
    """Convert DTO to SQLAlchemy model."""
    created_at = dto.created_at
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.rstrip("Z"))
    updated_at = dto.updated_at
    if isinstance(updated_at, str):
        updated_at = datetime.fromisoformat(updated_at.rstrip("Z"))

    return ContentMetadataModel(
        id=dto.id,
        type=dto.type,
        original_filename=dto.original_filename,
        created_at=created_at,
        updated_at=updated_at,
        source_file=dto.source_file,
        video_file=dto.video_file,
        subtitle_path=dto.subtitle_path,
        translated_subtitle_path=dto.translated_subtitle_path,
        enhanced_subtitle_path=dto.enhanced_subtitle_path,
        source_type=dto.source_type,
        source_url=dto.source_url,
        pdf_page_count=dto.pdf_page_count,
        notes_path=dto.notes_path,
        ask_conversations_dir=dto.ask_conversations_dir,
        screenshots_dir=dto.screenshots_dir,
        timeline_path=dto.timeline_path,
        video_status=dto.video_status,
        subtitle_status=dto.subtitle_status,
        translation_status=dto.translation_status,
        enhanced_status=dto.enhanced_status,
        timeline_status=dto.timeline_status,
        notes_status=dto.notes_status,
        video_job_id=dto.video_job_id,
        subtitle_job_id=dto.subtitle_job_id,
        translation_job_id=dto.translation_job_id,
        enhanced_job_id=dto.enhanced_job_id,
        timeline_job_id=dto.timeline_job_id,
        notes_job_id=dto.notes_job_id,
    )


class MetadataStorage:
    """SQLite-based storage for content metadata with automatic locking."""

    def __init__(
        self,
        *,
        app_context: Optional[AppContext] = None,
        metadata_folder: Optional[str] = None,  # Kept for API compatibility, ignored
    ) -> None:
        self._ctx = app_context or get_app_context()
        self._ctx.init_paths()
        init_db(self._ctx)

    def save(self, metadata: ContentMetadata) -> None:
        """Save or update metadata."""
        try:
            with get_session(self._ctx) as session:
                existing = session.get(ContentMetadataModel, metadata.id)
                if existing:
                    # Update existing record
                    model = _dto_to_model(metadata)
                    for key in ContentMetadataModel.__table__.columns.keys():
                        if key != "id":
                            setattr(existing, key, getattr(model, key))
                    existing.updated_at = datetime.now(UTC).replace(tzinfo=None)
                else:
                    # Insert new record
                    model = _dto_to_model(metadata)
                    session.add(model)
            logger.info("Saved metadata for content %s", metadata.id)
        except Exception as exc:
            logger.error("Failed to save metadata for %s: %s", metadata.id, exc)
            raise

    def get(self, content_id: str) -> Optional[ContentMetadata]:
        """Get metadata by content ID."""
        try:
            with get_session(self._ctx) as session:
                model = session.get(ContentMetadataModel, content_id)
                if model:
                    return _model_to_dto(model)
                return None
        except Exception as exc:
            logger.error("Failed to load metadata for %s: %s", content_id, exc)
            return None

    def exists(self, content_id: str) -> bool:
        """Check if content exists."""
        try:
            with get_session(self._ctx) as session:
                model = session.get(ContentMetadataModel, content_id)
                return model is not None
        except Exception:
            return False

    def delete(self, content_id: str) -> bool:
        """Delete metadata by content ID."""
        try:
            with get_session(self._ctx) as session:
                model = session.get(ContentMetadataModel, content_id)
                if model:
                    session.delete(model)
                    logger.info("Deleted metadata for content %s", content_id)
                    return True
                return False
        except Exception as exc:
            logger.error("Failed to delete metadata for %s: %s", content_id, exc)
            return False

    def list_all(self) -> List[ContentMetadata]:
        """List all content metadata, sorted by created_at descending."""
        try:
            with get_session(self._ctx) as session:
                stmt = select(ContentMetadataModel).order_by(ContentMetadataModel.created_at.desc())
                result = session.execute(stmt).scalars().all()
                return [_model_to_dto(m) for m in result]
        except Exception as exc:
            logger.error("Failed to list metadata: %s", exc)
            return []

    def update_feature_status(
        self,
        content_id: str,
        feature: FeatureName,
        status: FeatureStatus,
        job_id: Optional[str] = None,
    ) -> bool:
        """Update the status of a specific feature."""
        try:
            with get_session(self._ctx) as session:
                model = session.get(ContentMetadataModel, content_id)
                if not model:
                    return False

                setattr(model, f"{feature}_status", status)
                setattr(model, f"{feature}_job_id", job_id)
                model.updated_at = datetime.now(UTC).replace(tzinfo=None)
                return True
        except Exception as exc:
            logger.error("Failed to update feature status for %s: %s", content_id, exc)
            return False

    def update_video_file(self, content_id: str, video_file: str) -> bool:
        """Update video file path and status."""
        try:
            with get_session(self._ctx) as session:
                model = session.get(ContentMetadataModel, content_id)
                if not model:
                    return False

                model.video_file = video_file
                model.video_status = "ready"
                model.video_job_id = None
                model.updated_at = datetime.now(UTC).replace(tzinfo=None)
                return True
        except Exception as exc:
            logger.error("Failed to update video file for %s: %s", content_id, exc)
            return False

    def update_subtitles(
        self,
        content_id: str,
        subtitle_path: Optional[str] = None,
        translated_path: Optional[str] = None,
        enhanced_path: Optional[str] = None,
    ) -> bool:
        """Update subtitle paths and statuses."""
        try:
            with get_session(self._ctx) as session:
                model = session.get(ContentMetadataModel, content_id)
                if not model:
                    return False

                if subtitle_path:
                    model.subtitle_path = subtitle_path
                    model.subtitle_status = "ready"
                    model.subtitle_job_id = None

                if translated_path:
                    model.translated_subtitle_path = translated_path
                    model.translation_status = "ready"
                    model.translation_job_id = None

                if enhanced_path:
                    model.enhanced_subtitle_path = enhanced_path
                    model.enhanced_status = "ready"
                    model.enhanced_job_id = None

                model.updated_at = datetime.now(UTC).replace(tzinfo=None)
                return True
        except Exception as exc:
            logger.error("Failed to update subtitles for %s: %s", content_id, exc)
            return False

    def db_path(self) -> str:
        """Return the SQLite database path."""
        import os
        return os.path.join(self._ctx.data_dir, "deeplecture.db")


def get_default_metadata_storage() -> MetadataStorage:
    return MetadataStorage()
