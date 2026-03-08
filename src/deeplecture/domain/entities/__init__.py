"""Domain entities."""

from deeplecture.domain.entities.artifact import VIDEO_FALLBACK_CHAIN, ArtifactKind
from deeplecture.domain.entities.config import (
    ContentConfig,
    DictionaryInteractionMode,
    NoteContextMode,
    ViewMode,
)
from deeplecture.domain.entities.content import ContentMetadata, ContentType, FeatureName
from deeplecture.domain.entities.feature import FeatureStatus, FeatureType
from deeplecture.domain.entities.media import Segment
from deeplecture.domain.entities.project import Project
from deeplecture.domain.entities.task import Task, TaskStatus
from deeplecture.domain.entities.voiceover import (
    # Constants
    LEADING_SILENCE_THRESHOLD,
    MERGE_TOLERANCE,
    SLOT_SKIP_THRESHOLD,
    # Entities
    SubtitleSegment,
    SyncSegment,
    # Pure functions
    calculate_slot_end,
    merge_sync_segments,
    parse_srt_text,
)

__all__ = [
    "LEADING_SILENCE_THRESHOLD",
    "MERGE_TOLERANCE",
    "SLOT_SKIP_THRESHOLD",
    "VIDEO_FALLBACK_CHAIN",
    "ArtifactKind",
    "ContentConfig",
    "ContentMetadata",
    "ContentType",
    "DictionaryInteractionMode",
    "FeatureName",
    "FeatureStatus",
    "FeatureType",
    "NoteContextMode",
    "Project",
    "Segment",
    "SubtitleSegment",
    "SyncSegment",
    "Task",
    "TaskStatus",
    "ViewMode",
    "calculate_slot_end",
    "merge_sync_segments",
    "parse_srt_text",
]
