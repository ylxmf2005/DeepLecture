"""Upload use case - handles video and PDF upload/import/merge operations."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from deeplecture.domain import ContentMetadata, FeatureStatus, FeatureType
from deeplecture.domain.errors import (
    ContentNotFoundError,
    InvalidURLError,
    PDFMergeError,
    UnsupportedFileFormatError,
    UploadError,
    VideoDownloadError,
    VideoMergeError,
)
from deeplecture.use_cases.dto.upload import (
    ImportJobResult,
    ImportVideoFromURLRequest,
    UploadResult,
)

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.upload import (
        MergePDFsRequest,
        MergeVideosRequest,
        UploadPDFRequest,
        UploadVideoRequest,
    )
    from deeplecture.use_cases.interfaces import (
        FileStorageProtocol,
        MetadataStorageProtocol,
        PathResolverProtocol,
        PDFMergerProtocol,
        TaskContextProtocol,
        TaskQueueProtocol,
        VideoDownloaderProtocol,
        VideoMergerProtocol,
    )

UTC = getattr(datetime, "UTC", timezone.utc)
logger = logging.getLogger(__name__)


class UploadUseCase:
    """
    Upload and merge operations for videos and PDFs.

    Orchestrates:
    - Single video/PDF uploads
    - URL-based video imports (async)
    - Multi-file video/PDF merges (sync/async)
    - Metadata persistence
    - Task queue submission for async operations
    """

    # Supported file extensions
    VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})
    PDF_EXTENSION = ".pdf"

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        file_storage: FileStorageProtocol,
        path_resolver: PathResolverProtocol,
        video_downloader: VideoDownloaderProtocol | None = None,
        video_merger: VideoMergerProtocol | None = None,
        pdf_merger: PDFMergerProtocol | None = None,
        task_queue: TaskQueueProtocol | None = None,
    ) -> None:
        """
        Initialize UploadUseCase.

        Args:
            metadata_storage: Content metadata storage
            file_storage: File save/load operations
            path_resolver: Content path resolution (provides temp_dir via property)
            video_downloader: Video download service (optional, required for URL imports)
            video_merger: Video merge service (optional, required for video merges)
            pdf_merger: PDF merge service (optional, required for PDF merges)
            task_queue: Task queue for async operations (optional)
        """
        self._metadata = metadata_storage
        self._file_storage = file_storage
        self._path_resolver = path_resolver
        self._video_downloader = video_downloader
        self._video_merger = video_merger
        self._pdf_merger = pdf_merger
        self._task_queue = task_queue

    # =========================================================================
    # PUBLIC API - Single File Uploads
    # =========================================================================

    def upload_video(self, request: UploadVideoRequest) -> UploadResult:
        """
        Upload a single video file.

        1. Validate file extension
        2. Save file to content directory
        3. Create metadata
        4. Return result

        Args:
            request: Upload request with content_id, filename, file_data

        Returns:
            UploadResult with content info

        Raises:
            UnsupportedFileFormatError: If file format is not supported
            UploadError: If upload operation fails
        """
        ext = self._get_file_extension(request.filename)
        if ext not in self.VIDEO_EXTENSIONS:
            raise UnsupportedFileFormatError(ext, list(self.VIDEO_EXTENSIONS))

        content_dir = self._path_resolver.ensure_content_root(request.content_id)
        video_path = os.path.join(content_dir, f"source{ext}")

        try:
            # Save file
            self._file_storage.save_file(request.file_data, video_path)
            logger.info("Saved video to %s", video_path)

            # Create metadata
            now = datetime.now(UTC)
            metadata = ContentMetadata(
                id=request.content_id,
                type="video",
                original_filename=request.filename,
                created_at=now,
                updated_at=now,
                source_file=video_path,
                video_file=video_path,
                video_status=FeatureStatus.READY.value,
                source_type="local",
            )
            self._metadata.save(metadata)

            return UploadResult(
                content_id=request.content_id,
                filename=request.filename,
                content_type="video",
                message="Video uploaded successfully",
            )

        except Exception as e:
            # Rollback: remove file on failure
            if self._file_storage.file_exists(video_path):
                self._file_storage.remove_file(video_path)
            logger.error("Video upload failed: %s", e)
            raise UploadError(f"Video upload failed: {e}") from e

    def upload_pdf(self, request: UploadPDFRequest) -> UploadResult:
        """
        Upload a single PDF file.

        1. Validate file extension
        2. Save file to content directory
        3. Get page count
        4. Create metadata
        5. Return result

        Args:
            request: Upload request with content_id, filename, file_data

        Returns:
            UploadResult with content info

        Raises:
            UnsupportedFileFormatError: If file is not PDF
            UploadError: If upload operation fails
        """
        ext = self._get_file_extension(request.filename)
        if ext != self.PDF_EXTENSION:
            raise UnsupportedFileFormatError(ext, [self.PDF_EXTENSION])

        content_dir = self._path_resolver.ensure_content_root(request.content_id)
        pdf_path = os.path.join(content_dir, "source.pdf")

        try:
            # Save file
            self._file_storage.save_file(request.file_data, pdf_path)
            logger.info("Saved PDF to %s", pdf_path)

            # Get page count
            page_count = self._file_storage.get_pdf_page_count(pdf_path)

            # Create metadata
            now = datetime.now(UTC)
            metadata = ContentMetadata(
                id=request.content_id,
                type="slide",
                original_filename=request.filename,
                created_at=now,
                updated_at=now,
                source_file=pdf_path,
                video_file=None,
                pdf_page_count=page_count,
                video_status=FeatureStatus.NONE.value,
                source_type="local",
            )
            self._metadata.save(metadata)

            return UploadResult(
                content_id=request.content_id,
                filename=request.filename,
                content_type="slide",
                message="PDF uploaded successfully",
            )

        except Exception as e:
            # Rollback: remove file on failure
            if self._file_storage.file_exists(pdf_path):
                self._file_storage.remove_file(pdf_path)
            logger.error("PDF upload failed: %s", e)
            raise UploadError(f"PDF upload failed: {e}") from e

    # =========================================================================
    # PUBLIC API - Video Import from URL
    # =========================================================================

    def start_import_video_from_url(
        self,
        request: ImportVideoFromURLRequest,
    ) -> ImportJobResult:
        """
        Start async video import from URL.

        1. Generate content_id
        2. Create content directory
        3. Create placeholder metadata (status=processing)
        4. Submit task to queue
        5. Return job result

        Args:
            request: Import request with URL and optional custom name

        Returns:
            ImportJobResult with task_id

        Raises:
            InvalidURLError: If URL validation fails
            UploadError: If task submission fails
        """
        if not self._video_downloader:
            raise UploadError("Video downloader not configured")
        if not self._task_queue:
            raise UploadError("Task queue not configured for async operations")

        # Validate URL first
        try:
            self._video_downloader.validate_url(request.url)
        except ValueError as e:
            raise InvalidURLError(request.url, str(e)) from e

        # Generate content ID and setup directory
        content_id = self._generate_content_id()
        self._path_resolver.ensure_content_root(content_id)

        display_name = request.custom_name if request.custom_name else request.url
        now = datetime.now(UTC)

        # Create placeholder metadata
        metadata = ContentMetadata(
            id=content_id,
            type="video",
            original_filename=display_name,
            created_at=now,
            updated_at=now,
            source_file="",
            video_file=None,
            video_status=FeatureStatus.PROCESSING.value,
            source_type="remote",
            source_url=request.url,
        )

        try:
            self._metadata.save(metadata)
        except Exception as e:
            # Rollback: clean up directory
            self._cleanup_content_dir(content_id)
            logger.error("Failed to create metadata for URL import: %s", e)
            raise UploadError(f"Failed to create metadata: {e}") from e

        # Submit async task
        try:
            # Closure captures request for worker execution
            def _task(ctx: TaskContextProtocol) -> UploadResult:
                return self.import_video_from_url_sync(
                    ctx.content_id,
                    ImportVideoFromURLRequest(url=request.url, custom_name=request.custom_name),
                )

            task_id = self._task_queue.submit(
                content_id,
                "video_import_url",
                _task,
                metadata={
                    "content_id": content_id,
                    "url": request.url,
                    "custom_name": request.custom_name,
                },
            )

            # Update metadata with job_id
            metadata = metadata.with_status(FeatureType.VIDEO.value, FeatureStatus.PROCESSING, job_id=task_id)
            self._metadata.save(metadata)

            return ImportJobResult(
                content_id=content_id,
                filename=display_name,
                content_type="video",
                status=FeatureStatus.PROCESSING,
                message="Video import started",
                job_id=task_id,
            )

        except Exception as e:
            # Rollback: clean up content + metadata
            self._cleanup_content_dir(content_id)
            logger.error("Failed to submit URL import task: %s", e)
            raise UploadError(f"Failed to submit task: {e}") from e

    def import_video_from_url_sync(
        self,
        content_id: str,
        request: ImportVideoFromURLRequest,
    ) -> UploadResult:
        """
        Synchronously import video from URL (called by worker).

        1. Download video
        2. Update metadata with file path
        3. Return result

        Args:
            content_id: Pre-created content ID
            request: Import request with URL and optional custom name

        Returns:
            UploadResult with content info

        Raises:
            VideoDownloadError: If download fails
        """
        if not self._video_downloader:
            raise UploadError("Video downloader not configured")

        content_dir = self._path_resolver.ensure_content_root(content_id)

        try:
            # Download video
            result = self._video_downloader.download_video(request.url, "source")

            if not result.get("success"):
                error_message = result.get("error", "unknown error")
                raise VideoDownloadError(request.url, error_message)

            video_path = result.get("filepath")
            if not video_path:
                raise VideoDownloadError(request.url, "missing output filepath")

            # Security: validate original path BEFORE any resolution (prevents symlink attacks)
            if not self._file_storage.file_exists(video_path):
                raise VideoDownloadError(request.url, f"downloaded file not found: {video_path!r}")

            # Security hardening: ensure it's a regular file (not directory/symlink)
            # is_regular_file uses os.lstat which does NOT follow symlinks
            if not self._file_storage.is_regular_file(video_path):
                raise VideoDownloadError(
                    request.url,
                    f"expected regular file, got directory or symlink: {video_path!r}",
                )

            # Now safe to get extension from validated path
            ext = Path(video_path).suffix.lower() or ".mp4"
            dest_path = Path(content_dir) / f"source{ext}"

            # Move file to controlled directory
            if self._file_storage.file_exists(str(dest_path)):
                self._file_storage.remove_file(str(dest_path))
            self._file_storage.move_file(video_path, str(dest_path))
            controlled_path = str(dest_path)

            # Determine display name
            display_name = (
                request.custom_name if request.custom_name else result.get("title", os.path.basename(video_path))
            )

            # Update metadata (use controlled path, not downloader's arbitrary path)
            now = datetime.now(UTC)
            metadata = self._metadata.get(content_id)
            if not metadata:
                raise ContentNotFoundError(content_id)

            metadata = replace(
                metadata,
                original_filename=display_name,
                source_file=controlled_path,
                video_file=controlled_path,
                video_status=FeatureStatus.READY.value,
                video_job_id=None,
                source_type=result.get("source_type", "remote"),
                source_url=request.url,
                updated_at=now,
            )

            self._metadata.save(metadata)

            return UploadResult(
                content_id=content_id,
                filename=display_name,
                content_type="video",
                message="Video imported successfully",
            )

        except Exception as e:
            # Update metadata to error status
            metadata = self._metadata.get(content_id)
            if metadata:
                metadata = replace(
                    metadata,
                    video_status=FeatureStatus.ERROR.value,
                    video_job_id=None,
                    updated_at=datetime.now(UTC),
                )
                self._metadata.save(metadata)

            logger.error("Video import failed for %s: %s", content_id, e)
            raise

    # =========================================================================
    # PUBLIC API - Video Merge
    # =========================================================================

    def merge_videos(self, request: MergeVideosRequest) -> UploadResult | ImportJobResult:
        """
        Merge multiple video files.

        If async_mode=False or only 1 file: sync merge
        If async_mode=True and >1 files: async via task queue

        Args:
            request: Merge request with file list and custom name

        Returns:
            UploadResult (sync) or ImportJobResult (async)

        Raises:
            UnsupportedFileFormatError: If any file has unsupported format
            VideoMergeError: If merge operation fails
        """
        if not request.file_data_list:
            raise UploadError("No video files provided")

        # Single file: direct upload (sync)
        if len(request.file_data_list) == 1:
            return self._merge_videos_single_file(request)

        # Multiple files: sync or async
        if request.async_mode:
            return self._merge_videos_async(request)
        return self._merge_videos_sync(request)

    def _merge_videos_single_file(self, request: MergeVideosRequest) -> UploadResult:
        """Handle single-file video 'merge' (direct upload)."""
        file_obj = request.file_data_list[0]
        filename = getattr(file_obj, "filename", "video.mp4")
        ext = self._get_file_extension(filename)

        if ext.lower() not in self.VIDEO_EXTENSIONS:
            raise UnsupportedFileFormatError(ext, list(self.VIDEO_EXTENSIONS))

        content_id = self._generate_content_id()
        content_dir = self._path_resolver.ensure_content_root(content_id)

        display_name = request.custom_name if request.custom_name else filename
        if not self._has_video_extension(display_name):
            display_name = f"{display_name}.mp4"

        dest_path = os.path.join(content_dir, "source.mp4")

        try:
            self._file_storage.save_file(file_obj, dest_path)

            now = datetime.now(UTC)
            metadata = ContentMetadata(
                id=content_id,
                type="video",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file=dest_path,
                video_file=dest_path,
                video_status=FeatureStatus.READY.value,
                source_type="local",
            )
            self._metadata.save(metadata)

            return UploadResult(
                content_id=content_id,
                filename=display_name,
                content_type="video",
                message="Video uploaded",
            )

        except Exception as e:
            if self._file_storage.file_exists(dest_path):
                self._file_storage.remove_file(dest_path)
            raise UploadError(f"Video upload failed: {e}") from e

    def _merge_videos_sync(self, request: MergeVideosRequest) -> UploadResult:
        """Synchronous video merge."""
        if not self._video_merger:
            raise UploadError("Video merger not configured")

        content_id = self._generate_content_id()
        temp_dir: str | None = None

        try:
            content_dir = self._path_resolver.ensure_content_root(content_id)
            temp_dir = self._path_resolver.ensure_temp_dir(f"merge_{content_id}")

            # Save files to temp directory
            temp_paths = []
            for idx, file_obj in enumerate(request.file_data_list):
                filename = getattr(file_obj, "filename", f"video_{idx}.mp4")
                ext = self._get_file_extension(filename)
                if ext.lower() not in self.VIDEO_EXTENSIONS:
                    raise UnsupportedFileFormatError(ext, list(self.VIDEO_EXTENSIONS))
                temp_path = os.path.join(temp_dir, f"part_{idx}{ext}")
                self._file_storage.save_file(file_obj, temp_path)
                temp_paths.append(temp_path)

            # Merge videos
            merged_path = os.path.join(content_dir, "source.mp4")
            self._video_merger.merge_videos(temp_paths, merged_path)

            # Create metadata
            display_name = request.custom_name if request.custom_name else "Merged Video"
            if not self._has_video_extension(display_name):
                display_name = f"{display_name}.mp4"

            now = datetime.now(UTC)
            metadata = ContentMetadata(
                id=content_id,
                type="video",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file=merged_path,
                video_file=merged_path,
                video_status=FeatureStatus.READY.value,
                source_type="local",
            )
            self._metadata.save(metadata)

            return UploadResult(
                content_id=content_id,
                filename=display_name,
                content_type="video",
                message=f"Successfully merged {len(request.file_data_list)} videos",
            )

        except Exception:
            self._cleanup_content_dir(content_id)
            raise

        finally:
            if temp_dir is not None:
                self._path_resolver.cleanup_temp_dir(temp_dir)

    def _merge_videos_async(self, request: MergeVideosRequest) -> ImportJobResult:
        """Async video merge via task queue."""
        if not self._video_merger:
            raise UploadError("Video merger not configured")
        if not self._task_queue:
            raise UploadError("Task queue not configured for async operations")

        content_id = self._generate_content_id()
        temp_dir: str | None = None
        task_id: str | None = None

        try:
            self._path_resolver.ensure_content_root(content_id)
            temp_dir = self._path_resolver.ensure_temp_dir(f"merge_{content_id}")

            # Save files to temp directory
            temp_paths = []
            for idx, file_obj in enumerate(request.file_data_list):
                filename = getattr(file_obj, "filename", f"video_{idx}.mp4")
                ext = self._get_file_extension(filename)
                if ext.lower() not in self.VIDEO_EXTENSIONS:
                    raise UnsupportedFileFormatError(ext, list(self.VIDEO_EXTENSIONS))
                temp_path = os.path.join(temp_dir, f"part_{idx}{ext}")
                self._file_storage.save_file(file_obj, temp_path)
                temp_paths.append(temp_path)

            display_name = request.custom_name if request.custom_name else "Merged Video"
            if not self._has_video_extension(display_name):
                display_name = f"{display_name}.mp4"

            # Create placeholder metadata
            now = datetime.now(UTC)
            metadata = ContentMetadata(
                id=content_id,
                type="video",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file="",
                video_file=None,
                video_status=FeatureStatus.PROCESSING.value,
                source_type="local",
            )
            self._metadata.save(metadata)

            # Submit task
            file_count = len(request.file_data_list)

            def _task(ctx: TaskContextProtocol) -> None:
                self.merge_videos_job_sync(ctx.content_id, str(temp_dir), temp_paths, display_name)

            task_id = self._task_queue.submit(
                content_id,
                "video_merge",
                _task,
                metadata={
                    "content_id": content_id,
                    "file_count": file_count,
                    "custom_name": request.custom_name,
                    "temp_dir": str(temp_dir),
                    "temp_paths": temp_paths,
                    "display_name": display_name,
                },
            )

            # Update metadata with job_id
            metadata = metadata.with_status(FeatureType.VIDEO.value, FeatureStatus.PROCESSING, job_id=task_id)
            self._metadata.save(metadata)

            return ImportJobResult(
                content_id=content_id,
                filename=display_name,
                content_type="video",
                status=FeatureStatus.PROCESSING,
                message="Video merge started",
                job_id=task_id,
            )

        except Exception as e:
            # Only clean up if task was NOT submitted (worker needs resources)
            if task_id is None:
                if temp_dir is not None:
                    self._path_resolver.cleanup_temp_dir(temp_dir)
                self._cleanup_content_dir(content_id)
            raise UploadError(f"Video merge failed: {e}") from e

    def merge_videos_job_sync(
        self,
        content_id: str,
        temp_dir: str,
        temp_paths: list[str],
        display_name: str,
    ) -> None:
        """
        Synchronous video merge (called by worker).

        Args:
            content_id: Content ID
            temp_dir: Temporary directory with source files
            temp_paths: List of temp file paths
            display_name: Display name for merged video

        Raises:
            VideoMergeError: If merge fails
            UploadError: If path validation fails
        """
        if not self._video_merger:
            raise UploadError("Video merger not configured")

        # Validate paths are under temp directory (prevent arbitrary directory deletion)
        safe_temp_dir = self._validate_path_under_base(self._path_resolver.temp_dir, temp_dir, name="temp_dir")
        safe_temp_paths = [
            str(self._validate_path_under_base(str(safe_temp_dir), p, name=f"temp_paths[{i}]"))
            for i, p in enumerate(temp_paths)
        ]

        content_dir = self._path_resolver.get_content_dir(content_id)
        merged_path = os.path.join(content_dir, "source.mp4")

        try:
            # Merge videos (use validated paths)
            self._video_merger.merge_videos(safe_temp_paths, merged_path)

            # Update metadata
            metadata = self._metadata.get(content_id)
            if not metadata:
                raise ContentNotFoundError(content_id)

            metadata = replace(
                metadata,
                source_file=merged_path,
                video_file=merged_path,
                video_status=FeatureStatus.READY.value,
                video_job_id=None,
                updated_at=datetime.now(UTC),
            )
            self._metadata.save(metadata)

        except Exception as e:
            # Update metadata to error status
            metadata = self._metadata.get(content_id)
            if metadata:
                metadata = replace(
                    metadata,
                    video_status=FeatureStatus.ERROR.value,
                    video_job_id=None,
                    updated_at=datetime.now(UTC),
                )
                self._metadata.save(metadata)

            if self._file_storage.file_exists(merged_path):
                self._file_storage.remove_file(merged_path)

            logger.error("Video merge failed for %s: %s", content_id, e)
            raise VideoMergeError(str(e), len(temp_paths)) from e

        finally:
            # Only clean up validated path
            self._path_resolver.cleanup_temp_dir(str(safe_temp_dir))

    # =========================================================================
    # PUBLIC API - PDF Merge
    # =========================================================================

    def merge_pdfs(self, request: MergePDFsRequest) -> UploadResult | ImportJobResult:
        """
        Merge multiple PDF files.

        If async_mode=False: sync merge
        If async_mode=True: async via task queue

        Args:
            request: Merge request with file list and custom name

        Returns:
            UploadResult (sync) or ImportJobResult (async)

        Raises:
            UnsupportedFileFormatError: If any file is not PDF
            PDFMergeError: If merge operation fails
        """
        if not request.file_data_list:
            raise UploadError("No PDF files provided")

        if request.async_mode:
            return self._merge_pdfs_async(request)
        return self._merge_pdfs_sync(request)

    def _merge_pdfs_sync(self, request: MergePDFsRequest) -> UploadResult:
        """Synchronous PDF merge."""
        if not self._pdf_merger:
            raise UploadError("PDF merger not configured")

        content_id = self._generate_content_id()
        temp_dir: str | None = None

        try:
            content_dir = self._path_resolver.ensure_content_root(content_id)
            temp_dir = self._path_resolver.ensure_temp_dir(f"merge_{content_id}")

            # Save files to temp directory
            temp_paths = []
            for idx, file_obj in enumerate(request.file_data_list):
                filename = getattr(file_obj, "filename", f"pdf_{idx}.pdf")
                ext = self._get_file_extension(filename)
                if ext != self.PDF_EXTENSION:
                    raise UnsupportedFileFormatError(ext, [self.PDF_EXTENSION])
                temp_path = os.path.join(temp_dir, f"part_{idx}.pdf")
                self._file_storage.save_file(file_obj, temp_path)
                temp_paths.append(temp_path)

            # Merge PDFs
            merged_path = os.path.join(content_dir, "source.pdf")
            self._pdf_merger.merge_pdfs(temp_paths, merged_path)

            # Get page count
            page_count = self._file_storage.get_pdf_page_count(merged_path)

            # Create metadata
            display_name = request.custom_name if request.custom_name else "Merged PDF"
            if not display_name.endswith(".pdf"):
                display_name = f"{display_name}.pdf"

            now = datetime.now(UTC)
            metadata = ContentMetadata(
                id=content_id,
                type="slide",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file=merged_path,
                video_file=None,
                pdf_page_count=page_count,
                video_status=FeatureStatus.NONE.value,
                source_type="local",
            )
            self._metadata.save(metadata)

            return UploadResult(
                content_id=content_id,
                filename=display_name,
                content_type="slide",
                message=f"Successfully merged {len(request.file_data_list)} PDFs",
            )

        except Exception:
            self._cleanup_content_dir(content_id)
            raise

        finally:
            if temp_dir is not None:
                self._path_resolver.cleanup_temp_dir(temp_dir)

    def _merge_pdfs_async(self, request: MergePDFsRequest) -> ImportJobResult:
        """Async PDF merge via task queue."""
        if not self._pdf_merger:
            raise UploadError("PDF merger not configured")
        if not self._task_queue:
            raise UploadError("Task queue not configured for async operations")

        content_id = self._generate_content_id()
        temp_dir: str | None = None
        task_id: str | None = None

        try:
            self._path_resolver.ensure_content_root(content_id)
            temp_dir = self._path_resolver.ensure_temp_dir(f"merge_{content_id}")

            # Save files to temp directory
            temp_paths = []
            for idx, file_obj in enumerate(request.file_data_list):
                filename = getattr(file_obj, "filename", f"pdf_{idx}.pdf")
                ext = self._get_file_extension(filename)
                if ext != self.PDF_EXTENSION:
                    raise UnsupportedFileFormatError(ext, [self.PDF_EXTENSION])
                temp_path = os.path.join(temp_dir, f"part_{idx}.pdf")
                self._file_storage.save_file(file_obj, temp_path)
                temp_paths.append(temp_path)

            display_name = request.custom_name if request.custom_name else "Merged PDF"
            if not display_name.endswith(".pdf"):
                display_name = f"{display_name}.pdf"

            # Create placeholder metadata (uses video_status for compatibility)
            now = datetime.now(UTC)
            metadata = ContentMetadata(
                id=content_id,
                type="slide",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file="",
                video_file=None,
                video_status=FeatureStatus.PROCESSING.value,  # NOTE: intentionally uses video_status for PDF merge
                source_type="local",
            )
            self._metadata.save(metadata)

            # Submit task
            file_count = len(request.file_data_list)

            def _task(ctx: TaskContextProtocol) -> None:
                self.merge_pdfs_job_sync(ctx.content_id, str(temp_dir), temp_paths, display_name)

            task_id = self._task_queue.submit(
                content_id,
                "pdf_merge",
                _task,
                metadata={
                    "content_id": content_id,
                    "file_count": file_count,
                    "custom_name": request.custom_name,
                    "temp_dir": str(temp_dir),
                    "temp_paths": temp_paths,
                    "display_name": display_name,
                },
            )

            # Update metadata with job_id (uses feature="video" for compatibility)
            metadata = metadata.with_status(FeatureType.VIDEO.value, FeatureStatus.PROCESSING, job_id=task_id)
            self._metadata.save(metadata)

            return ImportJobResult(
                content_id=content_id,
                filename=display_name,
                content_type="slide",
                status=FeatureStatus.PROCESSING,
                message="PDF merge started",
                job_id=task_id,
            )

        except Exception as e:
            # Only clean up if task was NOT submitted (worker needs resources)
            if task_id is None:
                if temp_dir is not None:
                    self._path_resolver.cleanup_temp_dir(temp_dir)
                self._cleanup_content_dir(content_id)
            raise UploadError(f"PDF merge failed: {e}") from e

    def merge_pdfs_job_sync(
        self,
        content_id: str,
        temp_dir: str,
        temp_paths: list[str],
        display_name: str,
    ) -> None:
        """
        Synchronous PDF merge (called by worker).

        Args:
            content_id: Content ID
            temp_dir: Temporary directory with source files
            temp_paths: List of temp file paths
            display_name: Display name for merged PDF

        Raises:
            PDFMergeError: If merge fails
            UploadError: If path validation fails
        """
        if not self._pdf_merger:
            raise UploadError("PDF merger not configured")

        # Validate paths are under temp directory (prevent arbitrary directory deletion)
        safe_temp_dir = self._validate_path_under_base(self._path_resolver.temp_dir, temp_dir, name="temp_dir")
        safe_temp_paths = [
            str(self._validate_path_under_base(str(safe_temp_dir), p, name=f"temp_paths[{i}]"))
            for i, p in enumerate(temp_paths)
        ]

        content_dir = self._path_resolver.get_content_dir(content_id)
        merged_path = os.path.join(content_dir, "source.pdf")

        try:
            # Merge PDFs (use validated paths)
            self._pdf_merger.merge_pdfs(safe_temp_paths, merged_path)

            # Get page count
            page_count = self._file_storage.get_pdf_page_count(merged_path)

            # Update metadata
            metadata = self._metadata.get(content_id)
            if not metadata:
                raise ContentNotFoundError(content_id)

            metadata = replace(
                metadata,
                source_file=merged_path,
                pdf_page_count=page_count,
                video_status=FeatureStatus.NONE.value,
                video_job_id=None,
                updated_at=datetime.now(UTC),
            )
            self._metadata.save(metadata)

        except Exception as e:
            # Update metadata to error status
            metadata = self._metadata.get(content_id)
            if metadata:
                metadata = replace(
                    metadata,
                    video_status=FeatureStatus.ERROR.value,
                    video_job_id=None,
                    updated_at=datetime.now(UTC),
                )
                self._metadata.save(metadata)

            if self._file_storage.file_exists(merged_path):
                self._file_storage.remove_file(merged_path)

            logger.error("PDF merge failed for %s: %s", content_id, e)
            raise PDFMergeError(str(e), len(temp_paths)) from e

        finally:
            # Only clean up validated path (safe_temp_dir already verified by _validate_path_under_base)
            self._path_resolver.cleanup_temp_dir(str(safe_temp_dir))

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @staticmethod
    def _generate_content_id() -> str:
        """Generate unique content ID."""
        return str(uuid.uuid4())

    @staticmethod
    def _get_file_extension(filename: str) -> str:
        """Get file extension in lowercase."""
        _, ext = os.path.splitext(filename)
        return ext.lower()

    def _has_video_extension(self, filename: str) -> bool:
        """Check if filename has a video extension."""
        ext = self._get_file_extension(filename)
        return ext in self.VIDEO_EXTENSIONS

    def _cleanup_content_dir(self, content_id: str) -> None:
        """Clean up content directory on failure."""
        content_dir = self._path_resolver.get_content_dir(content_id)
        try:
            self._file_storage.remove_dir(content_dir)
            logger.info("Cleaned up content directory: %s", content_dir)
        except Exception as e:
            logger.error("Failed to clean up content directory %s: %s", content_dir, e)

    def _validate_path_under_base(self, base_dir: str, target: str, *, name: str) -> Path:
        """
        Validate that target path is under base directory (prevent path traversal attacks).

        Args:
            base_dir: Allowed base directory
            target: Path to validate
            name: Name for error message

        Returns:
            Resolved Path object

        Raises:
            UploadError: If path escapes base directory
        """
        base = Path(base_dir).expanduser().resolve()
        path = Path(target).expanduser().resolve()
        try:
            path.relative_to(base)
        except ValueError:
            raise UploadError(f"{name} escapes allowed directory: {target!r}") from None
        return path
