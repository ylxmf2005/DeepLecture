"""Storage record Data Transfer Objects."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

UTC = getattr(datetime, "UTC", timezone.utc)


def _utc_now() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


@dataclass
class ArtifactRecord:
    artifact_id: str
    content_id: str
    path: str
    kind: str
    is_directory: bool = False
    media_type: Optional[str] = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> ArtifactRecord:
        return cls(
            artifact_id=payload["artifact_id"],
            content_id=payload["content_id"],
            path=payload["path"],
            kind=payload.get("kind", "unknown"),
            is_directory=bool(payload.get("is_directory", False)),
            media_type=payload.get("media_type"),
            created_at=payload.get("created_at", _utc_now()),
            updated_at=payload.get("updated_at", payload.get("created_at", _utc_now())),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class ContentMetadata:
    """Unified metadata for both video and slide content."""

    id: str
    type: str  # "video" or "slide"
    original_filename: str
    created_at: str
    updated_at: str
    source_file: str

    video_file: Optional[str] = None
    subtitle_path: Optional[str] = None
    translated_subtitle_path: Optional[str] = None
    enhanced_subtitle_path: Optional[str] = None
    source_type: str = "local"
    source_url: Optional[str] = None
    pdf_page_count: Optional[int] = None
    notes_path: Optional[str] = None
    ask_conversations_dir: Optional[str] = None
    screenshots_dir: Optional[str] = None
    timeline_path: Optional[str] = None

    # Feature status fields: "none" | "processing" | "ready" | "error"
    video_status: str = "none"
    subtitle_status: str = "none"
    translation_status: str = "none"
    enhanced_status: str = "none"
    timeline_status: str = "none"
    notes_status: str = "none"

    # Job IDs for tracking processing tasks
    video_job_id: Optional[str] = None
    subtitle_job_id: Optional[str] = None
    translation_job_id: Optional[str] = None
    enhanced_job_id: Optional[str] = None
    timeline_job_id: Optional[str] = None
    notes_job_id: Optional[str] = None

    # Video merge metadata
    requires_reencode: bool = False
    reencode_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContentMetadata:
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class ConversationRecord:
    video_id: str
    conversation_id: str
    title: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "conversation_id": self.conversation_id,
            "title": self.title,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class NoteRecord:
    video_id: str
    path: str
    content: str
    updated_at: Optional[datetime]


@dataclass
class SubtitleRecord:
    video_id: str
    language: str
    path: str
    is_translation: bool
    created_at: datetime
    is_enhanced: bool = False


@dataclass
class TimelineRecord:
    video_id: str
    language: str
    path: str
    learner_profile: str
    status: str
    generated_at: Optional[datetime]
