"""Upload-related protocol interfaces."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VideoDownloaderProtocol(Protocol):
    """
    Contract for video downloading service.

    Implementations handle downloading videos from URLs with security validation.
    """

    def validate_url(self, url: str) -> None:
        """
        Validate URL for security constraints.

        Args:
            url: The URL to validate

        Raises:
            InvalidURLError: If URL fails security validation
        """
        ...

    def download_video(self, url: str, output_filename: str) -> dict[str, Any]:
        """
        Download a video from a URL.

        Args:
            url: The URL of the video
            output_filename: The desired filename (without extension)

        Returns:
            Dict containing:
            - success: bool
            - filepath: str (absolute path to downloaded file)
            - title: str (original video title)
            - duration: int (in seconds)
            - source_type: str (platform: youtube, bilibili, web)
            - error: str (if failed)
        """
        ...


@runtime_checkable
class VideoMergerProtocol(Protocol):
    """
    Contract for video merging service.

    Implementations handle merging multiple video files with format normalization.
    """

    def merge_videos(
        self,
        input_paths: list[str],
        output_path: str,
        force_reencode: bool = False,
    ) -> None:
        """
        Merge multiple videos into one.

        Args:
            input_paths: List of video file paths to merge
            output_path: Output file path
            force_reencode: If True, always re-encode even if formats match

        Raises:
            VideoMergeError: If merge operation fails
        """
        ...


@runtime_checkable
class PDFMergerProtocol(Protocol):
    """
    Contract for PDF merging service.

    Implementations handle merging multiple PDF files.
    """

    def merge_pdfs(self, input_paths: list[str], output_path: str) -> None:
        """
        Merge multiple PDFs into one.

        Args:
            input_paths: List of PDF file paths to merge
            output_path: Output file path

        Raises:
            PDFMergeError: If merge operation fails
        """
        ...


@runtime_checkable
class FileStorageProtocol(Protocol):
    """
    Contract for file storage operations.

    Implementations handle saving file-like objects to disk.
    """

    def save_file(self, file_obj: Any, destination_path: str) -> None:
        """
        Save file-like object to destination.

        Args:
            file_obj: File-like object (framework-agnostic)
            destination_path: Absolute path to save file

        Raises:
            UploadError: If save operation fails
        """
        ...

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """
        Get page count from PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Number of pages

        Raises:
            UploadError: If operation fails
        """
        ...

    def move_file(self, src_path: str, dest_path: str) -> None:
        """
        Move file from source to destination.

        Args:
            src_path: Source file path
            dest_path: Destination file path

        Raises:
            UploadError: If operation fails
        """
        ...

    def remove_file(self, file_path: str) -> None:
        """
        Remove a file.

        Args:
            file_path: File path to remove

        Raises:
            UploadError: If operation fails
        """
        ...

    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists.

        Args:
            file_path: File path to check

        Returns:
            True if file exists
        """
        ...

    def is_regular_file(self, file_path: str) -> bool:
        """
        Check if path is a regular file (not directory/symlink).

        Args:
            file_path: File path to check

        Returns:
            True if regular file
        """
        ...

    def remove_dir(self, dir_path: str) -> None:
        """
        Remove a directory and all its contents.

        Args:
            dir_path: Directory path to remove

        Raises:
            UploadError: If operation fails or directory doesn't exist
        """
        ...

    def copy_file(self, src_path: str, dest_path: str) -> None:
        """
        Copy file from source to destination, preserving metadata.

        Args:
            src_path: Source file path
            dest_path: Destination file path

        Raises:
            UploadError: If operation fails
        """
        ...

    def makedirs(self, dir_path: str, exist_ok: bool = True) -> None:
        """
        Create directory and all parent directories.

        Args:
            dir_path: Directory path to create
            exist_ok: If True, don't raise if directory exists

        Raises:
            UploadError: If operation fails
        """
        ...

    def read_text(self, file_path: str, encoding: str = "utf-8") -> str:
        """
        Read file contents as text.

        Args:
            file_path: File path to read
            encoding: Text encoding

        Returns:
            File contents as string

        Raises:
            UploadError: If operation fails
        """
        ...

    def write_text(self, file_path: str, content: str, encoding: str = "utf-8") -> None:
        """
        Write text content to file.

        Args:
            file_path: File path to write
            content: Text content
            encoding: Text encoding

        Raises:
            UploadError: If operation fails
        """
        ...

    def read_bytes(self, file_path: str) -> bytes:
        """
        Read file contents as bytes.

        Args:
            file_path: File path to read

        Returns:
            File contents as bytes

        Raises:
            UploadError: If operation fails
        """
        ...

    def write_bytes(self, file_path: str, data: bytes) -> None:
        """
        Write bytes to file.

        Args:
            file_path: File path to write
            data: Bytes data

        Raises:
            UploadError: If operation fails
        """
        ...

    def replace_file(self, src_path: str, dest_path: str) -> None:
        """
        Atomically replace destination file with source file.

        This is an atomic operation on POSIX systems - either the replacement
        succeeds completely or the destination is unchanged.

        Args:
            src_path: Source file path (will be removed after replacement)
            dest_path: Destination file path (will be replaced)

        Raises:
            UploadError: If operation fails
        """
        ...
