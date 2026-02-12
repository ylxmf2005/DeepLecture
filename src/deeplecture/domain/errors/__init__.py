"""Domain errors - organized by module."""

from deeplecture.domain.errors.base import DomainError
from deeplecture.domain.errors.bookmark import BookmarkNotFoundError
from deeplecture.domain.errors.content import ContentNotFoundError
from deeplecture.domain.errors.feature import InvalidFeatureStatusTransitionError
from deeplecture.domain.errors.subtitle import (
    SubtitleError,
    SubtitleGenerationError,
    SubtitleNotFoundError,
)
from deeplecture.domain.errors.task import (
    TaskError,
    TaskNotFoundError,
    TaskQueueFullError,
)
from deeplecture.domain.errors.timeline import (
    TimelineError,
    TimelineGenerationError,
)
from deeplecture.domain.errors.upload import (
    FileSizeLimitExceededError,
    InvalidURLError,
    PDFMergeError,
    UnsupportedFileFormatError,
    UploadError,
    VideoDownloadError,
    VideoMergeError,
)

__all__ = [
    "BookmarkNotFoundError",
    "ContentNotFoundError",
    "DomainError",
    "FileSizeLimitExceededError",
    "InvalidFeatureStatusTransitionError",
    "InvalidURLError",
    "PDFMergeError",
    "SubtitleError",
    "SubtitleGenerationError",
    "SubtitleNotFoundError",
    "TaskError",
    "TaskNotFoundError",
    "TaskQueueFullError",
    "TimelineError",
    "TimelineGenerationError",
    "UnsupportedFileFormatError",
    "UploadError",
    "VideoDownloadError",
    "VideoMergeError",
]
