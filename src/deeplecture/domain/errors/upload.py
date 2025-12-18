"""Upload-related domain errors."""

from __future__ import annotations

from deeplecture.domain.errors.base import DomainError


class UploadError(DomainError):
    """Base class for upload-related errors."""


class UnsupportedFileFormatError(UploadError):
    """Raised when file format is not supported."""

    def __init__(self, format: str, supported: list[str] | None = None) -> None:
        msg = f"Unsupported file format: {format}"
        if supported:
            msg += f". Supported: {', '.join(supported)}"
        super().__init__(msg)
        self.format = format
        self.supported = supported


class FileSizeLimitExceededError(UploadError):
    """Raised when file size exceeds limit."""

    def __init__(self, size: int, limit: int) -> None:
        super().__init__(f"File size ({size / 1024 / 1024:.1f}MB) exceeds limit ({limit / 1024 / 1024:.1f}MB)")
        self.size = size
        self.limit = limit


class VideoDownloadError(UploadError):
    """Raised when video download fails."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"Failed to download video from {url}: {reason}")
        self.url = url
        self.reason = reason


class VideoMergeError(UploadError):
    """Raised when video merge operation fails."""

    def __init__(self, reason: str, file_count: int | None = None) -> None:
        msg = f"Failed to merge videos: {reason}"
        if file_count:
            msg = f"Failed to merge {file_count} videos: {reason}"
        super().__init__(msg)
        self.reason = reason
        self.file_count = file_count


class PDFMergeError(UploadError):
    """Raised when PDF merge operation fails."""

    def __init__(self, reason: str, file_count: int | None = None) -> None:
        msg = f"Failed to merge PDFs: {reason}"
        if file_count:
            msg = f"Failed to merge {file_count} PDFs: {reason}"
        super().__init__(msg)
        self.reason = reason
        self.file_count = file_count


class InvalidURLError(UploadError):
    """Raised when URL validation fails (security)."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"Invalid URL '{url}': {reason}")
        self.url = url
        self.reason = reason
