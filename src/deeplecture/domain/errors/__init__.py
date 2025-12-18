"""Domain errors - organized by module."""

from deeplecture.domain.errors.base import DomainError
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
    # Content
    "ContentNotFoundError",
    # Base
    "DomainError",
    "FileSizeLimitExceededError",
    # Feature
    "InvalidFeatureStatusTransitionError",
    "InvalidURLError",
    "PDFMergeError",
    # Subtitle
    "SubtitleError",
    "SubtitleGenerationError",
    "SubtitleNotFoundError",
    # Task
    "TaskError",
    "TaskNotFoundError",
    "TaskQueueFullError",
    "UnsupportedFileFormatError",
    # Upload
    "UploadError",
    "VideoDownloadError",
    "VideoMergeError",
]
