"""
Domain Layer - Business Core.

Contains:
- Entities: Pure data structures representing business concepts
- Errors: Domain-level exceptions

Rules:
- Zero external dependencies (only stdlib)
- No I/O operations
- No framework imports
"""

# Entities
from deeplecture.domain.entities import (
    ContentMetadata,
    ContentType,
    FeatureName,
    FeatureStatus,
    FeatureType,
    Segment,
    Task,
    TaskStatus,
)

# Errors
from deeplecture.domain.errors import (
    ContentNotFoundError,
    DomainError,
    InvalidFeatureStatusTransitionError,
    SubtitleError,
    SubtitleGenerationError,
    SubtitleNotFoundError,
    TaskError,
    TaskNotFoundError,
    TaskQueueFullError,
    VideoMergeError,
)

__all__ = [
    "ContentMetadata",
    "ContentNotFoundError",
    "ContentType",
    "DomainError",
    "FeatureName",
    "FeatureStatus",
    "FeatureType",
    "InvalidFeatureStatusTransitionError",
    "Segment",
    "SubtitleError",
    "SubtitleGenerationError",
    "SubtitleNotFoundError",
    "Task",
    "TaskError",
    "TaskNotFoundError",
    "TaskQueueFullError",
    "TaskStatus",
    "VideoMergeError",
]
