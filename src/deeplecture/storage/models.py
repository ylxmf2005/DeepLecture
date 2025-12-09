"""SQLAlchemy ORM models for DeepLecture."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

UTC = getattr(datetime, "UTC", timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class ContentMetadataModel(Base):
    """SQLite model for content metadata."""

    __tablename__ = "content_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # "video" or "slide"
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now, nullable=False)
    source_file: Mapped[str] = mapped_column(Text, nullable=False)

    # File paths
    video_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subtitle_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    translated_subtitle_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enhanced_subtitle_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeline_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ask_conversations_dir: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    screenshots_dir: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source info
    source_type: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_page_count: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Feature status: "none" | "processing" | "ready" | "error"
    video_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    subtitle_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    translation_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    enhanced_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    timeline_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    notes_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)

    # Job IDs for tracking processing tasks
    video_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    subtitle_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    translation_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    enhanced_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timeline_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        result = {
            "id": self.id,
            "type": self.type,
            "original_filename": self.original_filename,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "source_file": self.source_file,
            "video_file": self.video_file,
            "subtitle_path": self.subtitle_path,
            "translated_subtitle_path": self.translated_subtitle_path,
            "enhanced_subtitle_path": self.enhanced_subtitle_path,
            "notes_path": self.notes_path,
            "timeline_path": self.timeline_path,
            "ask_conversations_dir": self.ask_conversations_dir,
            "screenshots_dir": self.screenshots_dir,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "pdf_page_count": self.pdf_page_count,
            "video_status": self.video_status,
            "subtitle_status": self.subtitle_status,
            "translation_status": self.translation_status,
            "enhanced_status": self.enhanced_status,
            "timeline_status": self.timeline_status,
            "notes_status": self.notes_status,
            "video_job_id": self.video_job_id,
            "subtitle_job_id": self.subtitle_job_id,
            "translation_job_id": self.translation_job_id,
            "enhanced_job_id": self.enhanced_job_id,
            "timeline_job_id": self.timeline_job_id,
            "notes_job_id": self.notes_job_id,
        }
        return {k: v for k, v in result.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContentMetadataModel:
        """Create model from dictionary."""
        # Parse datetime strings
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.rstrip("Z"))
        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.rstrip("Z"))

        return cls(
            id=data["id"],
            type=data["type"],
            original_filename=data["original_filename"],
            created_at=created_at or _utc_now(),
            updated_at=updated_at or _utc_now(),
            source_file=data["source_file"],
            video_file=data.get("video_file"),
            subtitle_path=data.get("subtitle_path"),
            translated_subtitle_path=data.get("translated_subtitle_path"),
            enhanced_subtitle_path=data.get("enhanced_subtitle_path"),
            notes_path=data.get("notes_path"),
            timeline_path=data.get("timeline_path"),
            ask_conversations_dir=data.get("ask_conversations_dir"),
            screenshots_dir=data.get("screenshots_dir"),
            source_type=data.get("source_type", "local"),
            source_url=data.get("source_url"),
            pdf_page_count=data.get("pdf_page_count"),
            video_status=data.get("video_status", "none"),
            subtitle_status=data.get("subtitle_status", "none"),
            translation_status=data.get("translation_status", "none"),
            enhanced_status=data.get("enhanced_status", "none"),
            timeline_status=data.get("timeline_status", "none"),
            notes_status=data.get("notes_status", "none"),
            video_job_id=data.get("video_job_id"),
            subtitle_job_id=data.get("subtitle_job_id"),
            translation_job_id=data.get("translation_job_id"),
            enhanced_job_id=data.get("enhanced_job_id"),
            timeline_job_id=data.get("timeline_job_id"),
            notes_job_id=data.get("notes_job_id"),
        )
