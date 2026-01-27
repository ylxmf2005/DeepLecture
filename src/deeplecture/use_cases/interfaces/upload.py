"""Upload service protocols."""

from __future__ import annotations

from typing import Protocol


class FileStorageProtocol(Protocol):
    """Protocol for file storage service."""

    def store(
        self,
        data: bytes,
        filename: str,
        *,
        content_type: str | None = None,
    ) -> str:
        """Store file data.

        Args:
            data: File data.
            filename: Original filename.
            content_type: Optional MIME type.

        Returns:
            Storage path or URL.
        """
        ...

    def retrieve(self, path: str) -> bytes | None:
        """Retrieve file data.

        Args:
            path: Storage path.

        Returns:
            File data if exists, None otherwise.
        """
        ...

    def delete(self, path: str) -> bool:
        """Delete file.

        Args:
            path: Storage path.

        Returns:
            True if deleted, False if not found.
        """
        ...


class VideoDownloaderProtocol(Protocol):
    """Protocol for video download service."""

    def download(
        self,
        url: str,
        output_path: str,
        *,
        format_id: str | None = None,
    ) -> str:
        """Download video from URL.

        Args:
            url: Video URL.
            output_path: Output file path.
            format_id: Optional format identifier.

        Returns:
            Path to downloaded file.
        """
        ...

    def get_info(self, url: str) -> dict:
        """Get video information without downloading.

        Args:
            url: Video URL.

        Returns:
            Video metadata dictionary.
        """
        ...


class VideoMergerProtocol(Protocol):
    """Protocol for video merging service."""

    def merge(
        self,
        video_paths: list[str],
        output_path: str,
    ) -> str:
        """Merge multiple videos.

        Args:
            video_paths: List of video file paths.
            output_path: Output file path.

        Returns:
            Path to merged video.
        """
        ...


class PDFMergerProtocol(Protocol):
    """Protocol for PDF merging service."""

    def merge(
        self,
        pdf_paths: list[str],
        output_path: str,
    ) -> str:
        """Merge multiple PDFs.

        Args:
            pdf_paths: List of PDF file paths.
            output_path: Output file path.

        Returns:
            Path to merged PDF.
        """
        ...
