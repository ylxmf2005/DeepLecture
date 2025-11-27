from __future__ import annotations

import logging
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from deeplecture.app_context import AppContext, get_app_context
from deeplecture.dto.content import ContentUploadResult, VideoImportJobResult, VideoMergeJobResult
from deeplecture.dto.storage import ContentMetadata
from deeplecture.services.media_merge import merge_pdfs, merge_videos, probe_videos_compatibility
from deeplecture.storage.artifact_registry import ArtifactRegistry, get_default_artifact_registry
from deeplecture.storage.metadata_storage import MetadataStorage, get_default_metadata_storage
from deeplecture.workers import TaskManager
from deeplecture.utils.fs import safe_join

UTC = getattr(datetime, "UTC", timezone.utc)
logger = logging.getLogger(__name__)


class ContentService:
    """
    Unified service for managing both video and slide content.

    New unified storage structure:
        data/content/{content_id}/
            source.mp4|.pdf     - Original uploaded file
            metadata.json       - Content metadata
            artifacts.json      - Artifact registry
            subtitles/          - Subtitle files
            timeline/           - Timeline data
            notes/              - Notes
            screenshots/        - Screenshots
            ask/                - Conversations
    """

    def __init__(
        self,
        metadata_storage: Optional[MetadataStorage] = None,
        artifact_registry: Optional[ArtifactRegistry] = None,
        task_manager: Optional[TaskManager] = None,
        app_context: Optional[AppContext] = None,
        upload_folder: Optional[str] = None,
        output_folder: Optional[str] = None,
        temp_folder: Optional[str] = None,
    ) -> None:
        ctx = app_context or get_app_context()
        ctx.init_paths()

        self._metadata = metadata_storage or get_default_metadata_storage()
        self._artifact_registry = artifact_registry or get_default_artifact_registry()
        self._content_dir = output_folder or ctx.content_dir
        self._temp_dir = temp_folder or ctx.temp_dir
        self._upload_dir = upload_folder or os.path.join(self._content_dir, "uploads")
        self._task_manager: Optional[TaskManager] = task_manager
        self._artifacts_loaded = False
        self._artifacts_lock = threading.Lock()

        os.makedirs(self._content_dir, exist_ok=True)
        os.makedirs(self._temp_dir, exist_ok=True)
        os.makedirs(self._upload_dir, exist_ok=True)

        # Defer artifact loading until first use to avoid blocking startup

    def _content_path(self, content_id: str, *subpaths: str) -> str:
        """Get path under data/content/{content_id}/[subpaths]"""
        base = safe_join(self._content_dir, str(content_id))
        if subpaths:
            return safe_join(base, *subpaths)
        return base

    def _ensure_content_dir(self, content_id: str) -> str:
        """Ensure content directory exists"""
        path = self._content_path(content_id)
        os.makedirs(path, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Upload operations
    # ------------------------------------------------------------------

    def upload_video(self, file_obj, filename: str) -> ContentUploadResult:
        content_id = self._generate_content_id()
        ext = self._get_file_extension(filename)

        if ext not in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            raise ValueError(f"Unsupported video format: {ext}")

        content_dir = self._ensure_content_dir(content_id)
        video_path = os.path.join(content_dir, f"source{ext}")

        try:
            # Stream write to avoid loading large files into memory
            self._stream_save(file_obj, video_path)
            logger.info("Saved video to %s", video_path)

            now = datetime.now(UTC).replace(tzinfo=None).isoformat()
            metadata = ContentMetadata(
                id=content_id,
                type="video",
                original_filename=filename,
                created_at=now,
                updated_at=now,
                source_file=video_path,
                video_file=video_path,
                video_status="ready",
                source_type="local",
            )

            self._persist_metadata(metadata)
        except Exception:
            if os.path.exists(video_path):
                os.remove(video_path)
            raise

        return ContentUploadResult(
            content_id=content_id,
            filename=filename,
            content_type="video",
            message="Video uploaded successfully",
        )

    def upload_pdf(self, file_obj, filename: str) -> ContentUploadResult:
        content_id = self._generate_content_id()
        content_dir = self._ensure_content_dir(content_id)
        pdf_path = os.path.join(content_dir, "source.pdf")

        try:
            # Stream write to avoid loading large files into memory
            self._stream_save(file_obj, pdf_path)
            logger.info("Saved PDF to %s", pdf_path)

            page_count = self._get_pdf_page_count(pdf_path)
            now = datetime.now(UTC).replace(tzinfo=None).isoformat()
            metadata = ContentMetadata(
                id=content_id,
                type="slide",
                original_filename=filename,
                created_at=now,
                updated_at=now,
                source_file=pdf_path,
                video_file=None,
                pdf_page_count=page_count,
                video_status="none",
                source_type="local",
            )

            self._persist_metadata(metadata)
        except Exception:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            raise

        return ContentUploadResult(
            content_id=content_id,
            filename=filename,
            content_type="slide",
            message="PDF uploaded successfully",
        )

    def start_import_video_from_url(
        self,
        url: str,
        custom_name: Optional[str] = None,
    ) -> VideoImportJobResult:
        if not url:
            raise ValueError("URL is required")

        content_id = self._generate_content_id()
        self._ensure_content_dir(content_id)
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()
        display_name = custom_name if custom_name else url

        metadata = ContentMetadata(
            id=content_id,
            type="video",
            original_filename=display_name,
            created_at=now,
            updated_at=now,
            source_file="",
            video_file=None,
            video_status="processing",
            source_type="remote",
            source_url=url,
        )

        try:
            self._persist_metadata(metadata)
        except Exception as exc:
            logger.error("Failed to create metadata for URL import %s: %s", url, exc)
            raise RuntimeError("Failed to create metadata for URL import") from exc

        task_mgr = self._require_task_manager()
        try:
            task_id = task_mgr.submit_task(
                content_id,
                "video_import_url",
                metadata={
                    "content_id": content_id,
                    "url": url,
                    "custom_name": custom_name,
                },
            )
        except Exception as exc:
            logger.error("Failed to submit video import job for %s: %s", content_id, exc)
            try:
                self.delete_content(content_id)
            except Exception:
                pass
            raise RuntimeError("Failed to submit video import job") from exc

        try:
            self.update_feature_status(content_id=content_id, feature="video", status="processing", job_id=task_id)
        except Exception:
            pass

        return VideoImportJobResult(
            content_id=content_id,
            filename=display_name,
            content_type="video",
            status="processing",
            message="Video import started",
            job_id=task_id,
        )

    def import_video_from_url_sync(
        self,
        content_id: str,
        url: str,
        custom_name: Optional[str] = None,
    ) -> ContentUploadResult:
        from deeplecture.services.video_downloader import VideoDownloader

        content_dir = self._content_path(content_id)
        downloader = VideoDownloader(content_dir)

        video_path: Optional[str] = None

        try:
            result = downloader.download_video(url, "source")

            if not result.get("success"):
                error_message = result.get("error") or "unknown error"
                raise RuntimeError(f"Download failed: {error_message}")

            video_path = result.get("filepath")
            if not video_path:
                raise RuntimeError("Download failed: missing output filepath")

            display_name = custom_name if custom_name else (result.get("title") or os.path.basename(video_path))
            now = datetime.now(UTC).replace(tzinfo=None).isoformat()

            metadata = self._metadata.get(content_id)
            if metadata:
                metadata.original_filename = display_name
                metadata.source_file = video_path
                metadata.video_file = video_path
                metadata.video_status = "ready"
                metadata.video_job_id = None
                metadata.source_type = result.get("source_type") or metadata.source_type
                metadata.source_url = url
                metadata.updated_at = now
            else:
                metadata = ContentMetadata(
                    id=content_id,
                    type="video",
                    original_filename=display_name,
                    created_at=now,
                    updated_at=now,
                    source_file=video_path,
                    video_file=video_path,
                    video_status="ready",
                    source_type=result.get("source_type") or "local",
                    source_url=url,
                )

            self._persist_metadata(metadata)
        except Exception:
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
            raise

        return ContentUploadResult(
            content_id=content_id,
            filename=display_name,
            content_type="video",
            message="Video imported successfully",
        )

    def upload_multiple_pdfs(self, file_objects: List, custom_name: str) -> ContentUploadResult:
        if not file_objects:
            raise ValueError("No PDF files provided")

        content_id = self._generate_content_id()
        content_dir = self._ensure_content_dir(content_id)
        temp_dir = os.path.join(self._temp_dir, f"merge_{content_id}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            temp_paths = []
            for idx, file_obj in enumerate(file_objects):
                temp_path = os.path.join(temp_dir, f"part_{idx}.pdf")
                file_obj.save(temp_path)
                temp_paths.append(temp_path)

            merged_path = os.path.join(content_dir, "source.pdf")
            merge_pdfs(temp_paths, merged_path)

            page_count = self._get_pdf_page_count(merged_path)
            now = datetime.now(UTC).replace(tzinfo=None).isoformat()
            display_name = custom_name if custom_name else "Merged PDF"
            if not display_name.endswith('.pdf'):
                display_name = f"{display_name}.pdf"

            metadata = ContentMetadata(
                id=content_id,
                type="slide",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file=merged_path,
                video_file=None,
                pdf_page_count=page_count,
                video_status="none",
                source_type="local",
            )

            self._persist_metadata(metadata)

            return ContentUploadResult(
                content_id=content_id,
                filename=display_name,
                content_type="slide",
                message=f"Successfully merged {len(file_objects)} PDFs",
            )
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def upload_multiple_videos(self, file_objects: List, custom_name: str) -> ContentUploadResult:
        if not file_objects:
            raise ValueError("No video files provided")

        content_id = self._generate_content_id()
        content_dir = self._ensure_content_dir(content_id)
        temp_dir = os.path.join(self._temp_dir, f"merge_{content_id}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            temp_paths = []
            allowed_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
            for idx, file_obj in enumerate(file_objects):
                original_name = getattr(file_obj, 'filename', f'video_{idx}.mp4')
                ext = self._get_file_extension(original_name)
                if ext.lower() not in allowed_extensions:
                    raise ValueError(f"Unsupported video format: {ext}")
                temp_path = os.path.join(temp_dir, f"part_{idx}{ext}")
                file_obj.save(temp_path)
                temp_paths.append(temp_path)

            merged_path = os.path.join(content_dir, "source.mp4")
            merge_videos(temp_paths, merged_path)

            now = datetime.now(UTC).replace(tzinfo=None).isoformat()
            display_name = custom_name if custom_name else "Merged Video"
            if not display_name.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                display_name = f"{display_name}.mp4"

            metadata = ContentMetadata(
                id=content_id,
                type="video",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file=merged_path,
                video_file=merged_path,
                video_status="ready",
                source_type="local",
            )

            self._persist_metadata(metadata)

            return ContentUploadResult(
                content_id=content_id,
                filename=display_name,
                content_type="video",
                message=f"Successfully merged {len(file_objects)} videos",
            )
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def start_upload_merge_pdfs(self, file_objects: List, custom_name: str) -> VideoMergeJobResult:
        if not file_objects:
            raise ValueError("No PDF files provided")

        content_id = self._generate_content_id()
        self._ensure_content_dir(content_id)
        temp_dir = os.path.join(self._temp_dir, f"merge_{content_id}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            temp_paths = []
            for idx, file_obj in enumerate(file_objects):
                original_name = getattr(file_obj, "filename", f"pdf_{idx}.pdf")
                ext = self._get_file_extension(original_name)
                if ext != ".pdf":
                    raise ValueError(f"Unsupported format: {ext}")
                temp_path = os.path.join(temp_dir, f"part_{idx}.pdf")
                file_obj.save(temp_path)
                temp_paths.append(temp_path)

            now = datetime.now(UTC).replace(tzinfo=None).isoformat()
            display_name = custom_name if custom_name else "Merged PDF"
            if not display_name.endswith(".pdf"):
                display_name = f"{display_name}.pdf"

            metadata = ContentMetadata(
                id=content_id,
                type="slide",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file="",
                video_file=None,
                video_status="processing",
                source_type="local",
            )

            self._persist_metadata(metadata)

            task_mgr = self._require_task_manager()
            task_id = task_mgr.submit_task(
                content_id,
                "pdf_merge",
                metadata={
                    "content_id": content_id,
                    "file_count": len(file_objects),
                    "custom_name": custom_name,
                    "temp_dir": temp_dir,
                    "temp_paths": temp_paths,
                    "display_name": display_name,
                },
            )

            self.update_feature_status(content_id=content_id, feature="video", status="processing", job_id=task_id)

            return VideoMergeJobResult(
                content_id=content_id,
                filename=display_name,
                content_type="slide",
                status="processing",
                message="PDF merge started",
                job_id=task_id,
            )
        except Exception:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise

    def start_upload_merge_videos(self, file_objects: List, custom_name: str) -> VideoMergeJobResult:
        if not file_objects:
            raise ValueError("No video files provided")

        content_id = self._generate_content_id()
        self._ensure_content_dir(content_id)
        content_dir = self._content_path(content_id)

        allowed_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        now = datetime.now(UTC).replace(tzinfo=None).isoformat()

        # Single file: direct save, no async task needed
        if len(file_objects) == 1:
            file_obj = file_objects[0]
            original_name = getattr(file_obj, 'filename', 'video.mp4')
            ext = self._get_file_extension(original_name)
            if ext.lower() not in allowed_extensions:
                raise ValueError(f"Unsupported format: {ext}")

            display_name = custom_name if custom_name else original_name
            if not display_name.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                display_name = f"{display_name}.mp4"

            dest_path = os.path.join(content_dir, "source.mp4")
            file_obj.save(dest_path)

            metadata = ContentMetadata(
                id=content_id,
                type="video",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file=dest_path,
                video_file=dest_path,
                video_status="ready",
                source_type="local",
            )
            self._persist_metadata(metadata)

            return VideoMergeJobResult(
                content_id=content_id,
                filename=display_name,
                content_type="video",
                status="ready",
                message="Video uploaded",
                job_id=None,
            )

        # Multiple files: async merge via worker
        temp_dir = os.path.join(self._temp_dir, f"merge_{content_id}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            temp_paths = []
            for idx, file_obj in enumerate(file_objects):
                original_name = getattr(file_obj, 'filename', f'video_{idx}.mp4')
                ext = self._get_file_extension(original_name)
                if ext.lower() not in allowed_extensions:
                    raise ValueError(f"Unsupported format: {ext}")
                temp_path = os.path.join(temp_dir, f"part_{idx}{ext}")
                file_obj.save(temp_path)
                temp_paths.append(temp_path)

            # Check video format compatibility
            compat_result = probe_videos_compatibility(temp_paths)
            requires_reencode = not compat_result["compatible"]
            reencode_reason = compat_result.get("reason")

            display_name = custom_name if custom_name else "Merged Video"
            if not display_name.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                display_name = f"{display_name}.mp4"

            metadata = ContentMetadata(
                id=content_id,
                type="video",
                original_filename=display_name,
                created_at=now,
                updated_at=now,
                source_file="",
                video_file=None,
                video_status="processing",
                source_type="local",
            )

            self._persist_metadata(metadata)

            task_mgr = self._require_task_manager()
            task_id = task_mgr.submit_task(
                content_id,
                "video_merge",
                metadata={
                    "content_id": content_id,
                    "file_count": len(file_objects),
                    "custom_name": custom_name,
                    "temp_dir": temp_dir,
                    "temp_paths": temp_paths,
                    "display_name": display_name,
                },
            )

            self.update_feature_status(content_id=content_id, feature="video", status="processing", job_id=task_id)

            return VideoMergeJobResult(
                content_id=content_id,
                filename=display_name,
                content_type="video",
                status="processing",
                message="Video merge started",
                job_id=task_id,
                requires_reencode=requires_reencode,
                reencode_reason=reencode_reason,
            )
        except Exception:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise

    def _merge_videos_job_sync(
        self,
        content_id: str,
        temp_dir: str,
        temp_paths: List[str],
        display_name: str,
        file_count: int,
    ) -> None:
        content_dir = self._content_path(content_id)
        merged_path: Optional[str] = None

        try:
            merged_path = os.path.join(content_dir, "source.mp4")
            merge_videos(temp_paths, merged_path)

            now = datetime.now(UTC).replace(tzinfo=None).isoformat()
            metadata = self._metadata.get(content_id)
            if metadata:
                metadata.source_file = merged_path
                metadata.video_file = merged_path
                metadata.video_status = "ready"
                metadata.video_job_id = None
                metadata.updated_at = now
                self._persist_metadata(metadata)
        except Exception as exc:
            logger.error("Video merge failed for %s: %s", content_id, exc)
            try:
                metadata = self._metadata.get(content_id)
                if metadata:
                    metadata.video_status = "error"
                    metadata.video_job_id = None
                    metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
                    self._persist_metadata(metadata)
            except Exception:
                pass
            if merged_path and os.path.exists(merged_path):
                os.remove(merged_path)
            raise
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _merge_pdfs_job_sync(
        self,
        content_id: str,
        temp_dir: str,
        temp_paths: List[str],
        display_name: str,
        file_count: int,
    ) -> None:
        content_dir = self._content_path(content_id)
        merged_path: Optional[str] = None

        try:
            merged_path = os.path.join(content_dir, "source.pdf")
            merge_pdfs(temp_paths, merged_path)

            page_count = self._get_pdf_page_count(merged_path)
            now = datetime.now(UTC).replace(tzinfo=None).isoformat()
            metadata = self._metadata.get(content_id)
            if metadata:
                metadata.source_file = merged_path
                metadata.pdf_page_count = page_count
                metadata.video_status = "none"
                metadata.updated_at = now
                self._persist_metadata(metadata)
        except Exception as exc:
            logger.error("PDF merge failed for %s: %s", content_id, exc)
            try:
                metadata = self._metadata.get(content_id)
                if metadata:
                    metadata.video_status = "error"
                    metadata.video_job_id = None
                    metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
                    self._persist_metadata(metadata)
            except Exception:
                pass
            if merged_path and os.path.exists(merged_path):
                os.remove(merged_path)
            raise
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def rename_content(self, content_id: str, new_name: str) -> ContentMetadata:
        metadata = self._require_metadata(content_id)
        metadata.original_filename = new_name
        metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
        self._persist_metadata(metadata)
        return metadata

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    def get_content(self, content_id: str) -> Optional[ContentMetadata]:
        return self._metadata.get(content_id)

    def list_all_content(self) -> List[ContentMetadata]:
        # Trigger lazy artifact load on first access
        self._ensure_artifacts_loaded()
        return self._metadata.list_all()

    def content_exists(self, content_id: str) -> bool:
        return self._metadata.exists(content_id)

    # ------------------------------------------------------------------
    # Deletion operations
    # ------------------------------------------------------------------

    def delete_content(self, content_id: str) -> Dict[str, Any]:
        metadata = self._metadata.get(content_id)
        if not metadata:
            return {"deleted": False, "reason": "not_found", "removed_files": [], "removed_dirs": [], "errors": []}

        content_dir = self._content_path(content_id)
        errors: List[str] = []

        try:
            if os.path.exists(content_dir):
                shutil.rmtree(content_dir)
        except Exception as exc:
            errors.append(f"{content_dir}: {exc}")

        self._artifact_registry.remove_content(content_id)

        return {
            "deleted": len(errors) == 0,
            "reason": "delete_failed" if errors else None,
            "removed_files": [],
            "removed_dirs": [content_dir] if not errors else [],
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def get_video_path(self, content_id: str) -> Optional[str]:
        metadata = self._metadata.get(content_id)
        if not metadata:
            return None

        if metadata.type == "video":
            return metadata.video_file or metadata.source_file

        if metadata.type == "slide":
            if metadata.video_status == "ready" and metadata.video_file:
                return metadata.video_file
            return None

        return None

    def get_pdf_path(self, content_id: str) -> Optional[str]:
        metadata = self._metadata.get(content_id)
        if not metadata or metadata.type != "slide":
            return None
        return metadata.source_file if os.path.exists(metadata.source_file) else None

    def get_subtitle_path(self, content_id: str) -> Optional[str]:
        metadata = self._metadata.get(content_id)
        if not metadata or metadata.subtitle_status != "ready":
            return None
        return metadata.subtitle_path

    def get_translated_subtitle_path(self, content_id: str) -> Optional[str]:
        metadata = self._metadata.get(content_id)
        if not metadata or metadata.translation_status != "ready":
            return None
        return metadata.translated_subtitle_path

    def get_enhanced_subtitle_path(self, content_id: str) -> Optional[str]:
        metadata = self._metadata.get(content_id)
        if not metadata or metadata.enhanced_status != "ready":
            return None
        return metadata.enhanced_subtitle_path

    # ------------------------------------------------------------------
    # Content-scoped path helpers
    # ------------------------------------------------------------------

    def ensure_content_dir(self, content_id: str, namespace: str) -> str:
        path = self._content_path(content_id, namespace)
        os.makedirs(path, exist_ok=True)
        self._register_artifact(content_id, path, kind=f"dir:{namespace}", is_directory=True)
        return path

    def build_content_path(self, content_id: str, namespace: str, filename: Optional[str] = None) -> str:
        if filename:
            return self._content_path(content_id, namespace, filename)
        return self._content_path(content_id, namespace)

    def ensure_notes_path(self, content_id: str) -> str:
        notes_dir = self.ensure_content_dir(content_id, "notes")
        return os.path.join(notes_dir, "notes.md")

    def ensure_ask_dir(self, content_id: str) -> str:
        return self.ensure_content_dir(content_id, "ask")

    def ensure_timeline_dir(self, content_id: str) -> str:
        return self.ensure_content_dir(content_id, "timeline")

    def mark_timeline_generated(self, content_id: str, timeline_path: str) -> bool:
        metadata = self._metadata.get(content_id)
        if not metadata:
            return False

        metadata.timeline_path = timeline_path
        metadata.timeline_status = "ready"
        metadata.timeline_job_id = None
        metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
        self._persist_metadata(metadata)
        return True

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    def update_feature_status(
        self,
        content_id: str,
        feature: str,
        status: str,
        job_id: Optional[str] = None,
    ) -> bool:
        """
        Update the status of a specific feature.

        Args:
            content_id: The content ID
            feature: Feature name (video, subtitle, translation, enhanced, timeline, notes)
            status: Status value (none, processing, ready, error)
            job_id: Optional job ID for tracking

        Returns:
            True if update succeeded
        """
        return self._metadata.update_feature_status(content_id, feature, status, job_id)  # type: ignore

    def mark_video_generated(self, content_id: str, video_path: str) -> bool:
        metadata = self._metadata.get(content_id)
        if not metadata or metadata.type != "slide":
            return False

        metadata.video_file = video_path
        metadata.video_status = "ready"
        metadata.video_job_id = None
        metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
        self._persist_metadata(metadata)
        return True

    def mark_subtitles_generated(self, content_id: str, subtitle_path: str) -> bool:
        updated = self._metadata.update_subtitles(content_id, subtitle_path=subtitle_path)
        if updated:
            self._register_artifact(content_id, subtitle_path, kind="subtitle:original", media_type="text/srt")
        return updated

    def mark_translation_generated(self, content_id: str, translated_path: str) -> bool:
        updated = self._metadata.update_subtitles(content_id, translated_path=translated_path)
        if updated:
            self._register_artifact(content_id, translated_path, kind="subtitle:translated", media_type="text/srt")
        return updated

    def mark_enhanced_generated(self, content_id: str, enhanced_path: str) -> bool:
        updated = self._metadata.update_subtitles(content_id, enhanced_path=enhanced_path)
        if updated:
            self._register_artifact(content_id, enhanced_path, kind="subtitle:enhanced", media_type="text/srt")
        return updated

    # ------------------------------------------------------------------
    # Serialization for API responses
    # ------------------------------------------------------------------

    def serialize_content(self, metadata: ContentMetadata) -> Dict[str, Any]:
        result = {
            "type": metadata.type,
            "id": metadata.id,
            "filename": metadata.original_filename,
            "createdAt": metadata.created_at,
            "sourceType": metadata.source_type,
            "sourceUrl": metadata.source_url,
            # New feature status fields
            "videoStatus": metadata.video_status,
            "subtitleStatus": metadata.subtitle_status,
            "translationStatus": metadata.translation_status,
            "enhancedStatus": metadata.enhanced_status,
            "timelineStatus": metadata.timeline_status,
            "notesStatus": metadata.notes_status,
            # Video merge info
            "requiresReencode": metadata.requires_reencode,
            "reencodeReason": metadata.reencode_reason,
        }

        if metadata.type == "slide":
            result["pageCount"] = metadata.pdf_page_count

        return result

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def register_artifact(
        self,
        content_id: str,
        path: str,
        *,
        kind: str,
        media_type: Optional[str] = None,
        is_directory: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._register_artifact(content_id, path, kind=kind, media_type=media_type, is_directory=is_directory, metadata=metadata)

    def unregister_artifact(self, content_id: str, path: Optional[str]) -> None:
        if not path:
            return
        try:
            self._artifact_registry.remove(content_id, path)
        except Exception:
            pass

    def _persist_metadata(self, metadata: ContentMetadata) -> ContentMetadata:
        self._metadata.save(metadata)
        self._register_artifact(metadata.id, self._metadata.metadata_path(metadata.id), kind="metadata")
        return metadata

    def _register_artifact(
        self,
        content_id: str,
        path: Optional[str],
        *,
        kind: str,
        media_type: Optional[str] = None,
        is_directory: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not path:
            return
        try:
            self._artifact_registry.register(content_id, path, kind=kind, media_type=media_type, is_directory=is_directory, metadata=metadata)
        except Exception as exc:
            logger.warning("Failed to register artifact for %s: %s", content_id, exc)

    def _backfill_artifacts(self) -> None:
        """
        Lazy-load artifacts on first access.

        Uses double-checked locking to ensure thread-safe one-time load.
        """
        if self._artifacts_loaded:
            return

        with self._artifacts_lock:
            if self._artifacts_loaded:
                return

            try:
                for metadata in self._metadata.list_all():
                    self._register_artifact(
                        metadata.id,
                        self._metadata.metadata_path(metadata.id),
                        kind="metadata"
                    )
                self._artifacts_loaded = True
                logger.info("Artifacts backfill completed")
            except Exception as exc:
                logger.warning("Artifacts backfill failed: %s", exc)

    def _ensure_artifacts_loaded(self) -> None:
        """Ensure artifacts are loaded (lazy-load trigger point)."""
        if not self._artifacts_loaded:
            self._backfill_artifacts()

    def _generate_content_id(self) -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _stream_save(file_obj, dest_path: str, chunk_size: int = 65536) -> None:
        """
        Stream a file to disk to avoid buffering large payloads in memory.

        Uses 64KB chunks to balance I/O efficiency and memory footprint.
        For a 1GB video, peak memory drops from 1GB to ~64KB.

        Args:
            file_obj: Flask/Werkzeug FileStorage object
            dest_path: Destination file path
            chunk_size: Bytes per read (default 64KB)
        """
        with open(dest_path, 'wb') as f:
            while True:
                chunk = file_obj.stream.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)

    @staticmethod
    def _get_file_extension(filename: str) -> str:
        _, ext = os.path.splitext(filename)
        return ext.lower()

    @staticmethod
    def _get_pdf_page_count(pdf_path: str) -> int:
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(pdf_path)
            try:
                return len(doc)
            finally:
                doc.close()
        except Exception:
            return 0

    def _require_task_manager(self) -> TaskManager:
        if self._task_manager is None:
            raise RuntimeError("TaskManager is required for background content tasks")
        return self._task_manager

    def _require_metadata(self, content_id: str) -> ContentMetadata:
        metadata = self._metadata.get(content_id)
        if not metadata:
            raise FileNotFoundError(f"Content {content_id} not found")
        return metadata


def get_default_content_service(task_manager: Optional[TaskManager] = None) -> ContentService:
    return ContentService(task_manager=task_manager)
