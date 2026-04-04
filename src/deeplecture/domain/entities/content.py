"""Domain entities for content management."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Final, Literal, get_args

from deeplecture.domain.entities.feature import FeatureType

if TYPE_CHECKING:
    from deeplecture.domain.entities.feature import FeatureStatus

UTC = getattr(datetime, "UTC", timezone.utc)


class ContentType(str, Enum):
    """Type of content."""

    VIDEO = "video"
    SLIDE = "slide"


# local: uploaded file, remote: generic URL (non-platform), youtube/bilibili: platform-specific
SourceType = Literal["local", "remote", "youtube", "bilibili"]

# FeatureName derived from FeatureType enum (Single Source of Truth)
FeatureName = Literal["video", "subtitle", "enhance_translate", "timeline", "notes"]

# Validate FeatureName matches FeatureType at module load
_FEATURE_TYPE_VALUES = {ft.value for ft in FeatureType}
_FEATURE_NAME_VALUES = set(get_args(FeatureName))
assert (
    _FEATURE_TYPE_VALUES == _FEATURE_NAME_VALUES
), f"FeatureName mismatch: {_FEATURE_NAME_VALUES} != {_FEATURE_TYPE_VALUES}"

_STATUS_FIELD_BY_FEATURE: Final[dict[str, str]] = {
    "video": "video_status",
    "subtitle": "subtitle_status",
    "enhance_translate": "enhance_translate_status",
    "timeline": "timeline_status",
    "notes": "notes_status",
}

_JOB_FIELD_BY_FEATURE: Final[dict[str, str | None]] = {
    "video": "video_job_id",
    "subtitle": "subtitle_job_id",
    "enhance_translate": "enhance_translate_job_id",
    "timeline": "timeline_job_id",
    "notes": None,
}


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _coerce_datetime(value: datetime | str, *, name: str) -> datetime:
    if isinstance(value, datetime):
        return _ensure_utc(value)
    if isinstance(value, str):
        return _ensure_utc(datetime.fromisoformat(value))
    raise TypeError(f"{name} must be datetime or ISO-8601 str, got {type(value)!r}")


@dataclass(slots=True)
class ContentMetadata:
    """
    Core entity representing uploaded content.

    Design principle: This is a pure data structure.
    Business logic belongs in UseCases, not here.

    DEPRECATION NOTICE:
    - `source_file`, `video_file`, `timeline_path` are deprecated.
    - Use ArtifactStorage for all file path management.
    - These fields remain for backward compatibility during migration.
    """

    id: str
    type: ContentType
    original_filename: str

    # DEPRECATED: Use ArtifactStorage.get_path(content_id, "source") instead
    source_file: str

    # DEPRECATED: Use ArtifactStorage.get_path(content_id, "video") instead
    video_file: str | None = None

    pdf_page_count: int | None = None

    # DEPRECATED: Use ArtifactStorage.get_path(content_id, "timeline") instead
    timeline_path: str | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Source info
    source_type: SourceType = "local"
    source_url: str | None = None
    detected_source_language: str | None = None

    # Feature statuses (stored as strings for flexibility)
    video_status: str = "none"
    subtitle_status: str = "none"
    enhance_translate_status: str = "none"
    timeline_status: str = "none"
    notes_status: str = "none"

    # Job tracking
    video_job_id: str | None = None
    subtitle_job_id: str | None = None
    enhance_translate_job_id: str | None = None
    timeline_job_id: str | None = None

    # Project grouping
    project_id: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.type, str):
            object.__setattr__(self, "type", ContentType(self.type))

        object.__setattr__(self, "created_at", _coerce_datetime(self.created_at, name="created_at"))
        object.__setattr__(self, "updated_at", _coerce_datetime(self.updated_at, name="updated_at"))

        if self.source_type not in ("local", "remote", "youtube", "bilibili"):
            raise ValueError(f"Invalid source_type: {self.source_type!r}")

        if self.pdf_page_count is not None and not isinstance(self.pdf_page_count, int):
            object.__setattr__(self, "pdf_page_count", int(self.pdf_page_count))

    def with_status(
        self,
        feature: FeatureName | str,
        status: FeatureStatus,
        *,
        job_id: str | None = None,
    ) -> ContentMetadata:
        """Return a new instance with updated status (immutable update)."""
        status_field = _STATUS_FIELD_BY_FEATURE.get(feature)
        if status_field is None:
            raise ValueError(f"Unknown feature: {feature!r}")

        updates: dict[str, object] = {
            status_field: status.value,
            "updated_at": datetime.now(UTC),
        }

        if job_id is not None:
            job_field = _JOB_FIELD_BY_FEATURE.get(feature)
            if job_field is None:
                raise ValueError(f"Job tracking not supported for feature: {feature!r}")
            updates[job_field] = job_id

        return replace(self, **updates)

    def with_job_id(self, feature: FeatureName | str, job_id: str | None) -> ContentMetadata:
        """Return a new instance with updated job_id (immutable update)."""
        job_field = _JOB_FIELD_BY_FEATURE.get(feature)
        if job_field is None:
            raise ValueError(f"Job tracking not supported for feature: {feature!r}")
        return replace(self, **{job_field: job_id, "updated_at": datetime.now(UTC)})

    def get_status(self, feature: FeatureName | str) -> str:
        """Get status for a feature."""
        status_field = _STATUS_FIELD_BY_FEATURE.get(feature)
        if status_field is None:
            raise ValueError(f"Unknown feature: {feature!r}")
        return getattr(self, status_field)
