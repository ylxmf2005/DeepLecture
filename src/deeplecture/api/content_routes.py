"""
Unified content routes for both videos and slide decks.

This module provides a simplified API that treats videos and PDFs
as unified "content" items with consistent endpoints.
"""

from __future__ import annotations

import logging
import mimetypes
import imghdr
import os
import re
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
from werkzeug.utils import secure_filename
from deeplecture.services.content_service import ContentService
from deeplecture.services.slide_lecture_service import SlideLectureService
from deeplecture.services.subtitle_service import SubtitleService
from deeplecture.workers import TaskManager
from deeplecture.config.config import get_settings
from deeplecture.api.error_utils import api_error


logger = logging.getLogger(__name__)
VALID_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ALLOWED_VIDEO_MAGIC = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}
ALLOWED_PDF_MAGIC = "application/pdf"


def _get_default_source_language() -> str:
    """
    Resolve the default original-language code used when generating subtitles.
    """
    try:
        return get_settings().subtitle.source_language
    except Exception:
        return "en"


def _peek_bytes(file_storage, length: int = 4096) -> bytes:
    """Read and rewind a small prefix from an uploaded file."""
    stream = getattr(file_storage, "stream", file_storage)
    try:
        pos = stream.tell()
    except Exception:
        pos = None
    data = stream.read(length)
    try:
        if pos is not None:
            stream.seek(pos)
        else:
            stream.seek(0)
    except Exception:
        pass
    return data or b""


def _detect_mime_and_ext(file_storage) -> tuple[str | None, str | None]:
    """
    Very small magic-byte detector for PDF/mp4/webm/mov.
    Avoids new native dependencies while catching obvious spoofing.
    """
    head = _peek_bytes(file_storage, 4096)
    if head.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"

    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in {b"isom", b"iso2", b"mp41", b"mp42"}:
            return "video/mp4", ".mp4"
        if brand in {b"qt  ", b"qt  "}:
            return "video/quicktime", ".mov"

    if head.startswith(b"\x1A\x45\xDF\xA3") or b"webm" in head[:32].lower():
        return "video/webm", ".webm"

    return None, None


def _validate_content_id(raw: str) -> bool:
    return bool(raw) and VALID_ID_RE.match(raw) is not None


def register_content_routes(
    app: Flask,
    content_service: ContentService,
    slide_service: SlideLectureService | None = None,
    subtitle_service: SubtitleService | None = None,
    task_manager: TaskManager | None = None,
) -> None:
    """
    Register unified content routes.

    These routes provide a consistent interface for both video and PDF content.
    """

    slide_service = slide_service or SlideLectureService(
        content_service=content_service,
        task_manager=task_manager,
    )
    subtitle_service = subtitle_service or SubtitleService(
        content_service=content_service,
        task_manager=task_manager,
    )
    settings = get_settings()
    rate_limits = settings.rate_limits
    max_upload_bytes = settings.server.max_upload_bytes
    max_note_image_bytes = settings.server.max_note_image_bytes

    limiter = app.extensions.get("limiter")
    limit_upload = limiter.limit(f"{rate_limits.upload_per_minute} per minute") if limiter else (lambda f: f)
    limit_generate = limiter.limit(f"{rate_limits.generate_per_hour} per hour") if limiter else (lambda f: f)

    @app.route("/api/content", methods=["POST"])
    @app.route("/api/content/upload", methods=["POST"])
    @limit_upload
    def upload_content():
        """
        Unified upload endpoint for both videos and PDFs.

        Accepts either a video file or PDF file and returns a unified response.
        """
        content_length = request.content_length
        if content_length and content_length > max_upload_bytes:
            return jsonify({"error": "File too large"}), 413

        # Check for video file
        if "video" in request.files:
            video_file = request.files["video"]
            if video_file.filename == "":
                return jsonify({"error": "No file selected"}), 400

            mime, ext = _detect_mime_and_ext(video_file)
            if mime not in ALLOWED_VIDEO_MAGIC:
                return jsonify({"error": "Invalid video file type"}), 400

            safe_name = secure_filename(Path(video_file.filename or "upload").stem) + ext

            try:
                result = content_service.upload_video(video_file, safe_name)
                logger.info("Video uploaded: %s", result.content_id)

                return jsonify(
                    {
                        "contentId": result.content_id,
                        "filename": result.filename,
                        "contentType": result.content_type,
                        "message": result.message,
                    },
                )
            except Exception as e:
                return api_error(500, "Video upload failed", logger=logger, exc=e)

        # Check for PDF file
        elif "pdf" in request.files:
            pdf_file = request.files["pdf"]
            if pdf_file.filename == "":
                return jsonify({"error": "No file selected"}), 400

            mime, ext = _detect_mime_and_ext(pdf_file)
            if mime != ALLOWED_PDF_MAGIC or ext != ".pdf":
                return jsonify({"error": "Invalid PDF file"}), 400

            safe_name = secure_filename(Path(pdf_file.filename or "upload").stem) + ".pdf"

            try:
                result = content_service.upload_pdf(pdf_file, safe_name)
                logger.info("PDF uploaded: %s", result.content_id)

                return jsonify(
                    {
                        "contentId": result.content_id,
                        "filename": result.filename,
                        "contentType": result.content_type,
                        "message": result.message,
                    },
                )
            except Exception as e:
                return api_error(500, "PDF upload failed", logger=logger, exc=e)

        else:
            return jsonify({"error": "No video or PDF file provided"}), 400

    @app.route("/api/content/batch/pdfs", methods=["POST"])
    @app.route("/api/content/upload-multiple-pdfs", methods=["POST"])
    @limit_upload
    def upload_multiple_pdfs():
        """
        Upload multiple PDF files and merge them into a single PDF.

        Expects:
        - Multiple files with key 'pdfs'
        - Optional 'custom_name' field for the merged PDF name
        """
        pdf_files = request.files.getlist("pdfs")

        if not pdf_files or len(pdf_files) == 0:
            return jsonify({"error": "No PDF files provided"}), 400

        # Limit number of files to prevent DoS
        if len(pdf_files) > 50:
            return jsonify({"error": "Too many files. Maximum 50 PDFs allowed"}), 400

        # Validate all files are PDFs
        for pdf_file in pdf_files:
            if pdf_file.filename == "":
                return jsonify({"error": "Empty filename in uploaded files"}), 400
            size = getattr(pdf_file, "content_length", None)
            if size and size > max_upload_bytes:
                return jsonify({"error": f"File {pdf_file.filename} too large"}), 413

            mime, ext = _detect_mime_and_ext(pdf_file)
            if mime != ALLOWED_PDF_MAGIC or ext != ".pdf":
                return jsonify({"error": f"File {pdf_file.filename} is not a PDF"}), 400
            pdf_file.filename = secure_filename(Path(pdf_file.filename or "upload").stem) + ".pdf"

        custom_name = request.form.get("custom_name", "")

        try:
            result = content_service.start_upload_merge_pdfs(pdf_files, custom_name)
            logger.info(
                "Started PDF merge for %s (job %s)",
                result.content_id,
                result.job_id,
            )

            payload = {
                "contentId": result.content_id,
                "filename": result.filename,
                "contentType": result.content_type,
                "message": result.message,
                "status": result.status,
            }
            if result.job_id:
                payload["job_id"] = result.job_id

            return jsonify(payload)
        except ValueError as e:
            logger.error("PDF merge validation failed: %s", e)
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return api_error(500, "Multiple PDF upload failed", logger=logger, exc=e)

    @app.route("/api/content/batch/videos", methods=["POST"])
    @app.route("/api/content/upload-multiple-videos", methods=["POST"])
    @limit_upload
    def upload_multiple_videos():
        """
        Upload multiple video files and merge them into a single video.

        Expects:
        - Multiple files with key 'videos'
        - Optional 'custom_name' field for the merged video name
        """
        video_files = request.files.getlist("videos")

        if not video_files or len(video_files) == 0:
            return jsonify({"error": "No video files provided"}), 400

        # Limit number of files to prevent DoS
        if len(video_files) > 50:
            return jsonify({"error": "Too many files. Maximum 50 videos allowed"}), 400

        # Validate all files are videos
        for video_file in video_files:
            if video_file.filename == "":
                return jsonify({"error": "Empty filename in uploaded files"}), 400
            size = getattr(video_file, "content_length", None)
            if size and size > max_upload_bytes:
                return jsonify({"error": f"File {video_file.filename} too large"}), 413

            mime, ext = _detect_mime_and_ext(video_file)
            if mime not in ALLOWED_VIDEO_MAGIC:
                return jsonify({"error": f"File {video_file.filename} is not a valid video"}), 400
            video_file.filename = secure_filename(Path(video_file.filename or "upload").stem) + (ext or "")

        custom_name = request.form.get("custom_name", "")

        try:
            result = content_service.start_upload_merge_videos(video_files, custom_name)
            logger.info(
                "Started video merge for %s (job %s)",
                result.content_id,
                result.job_id,
            )

            payload = {
                "contentId": result.content_id,
                "filename": result.filename,
                "contentType": result.content_type,
                "message": result.message,
                "status": result.status,
                "requiresReencode": result.requires_reencode,
            }
            if result.job_id:
                payload["job_id"] = result.job_id
            if result.reencode_reason:
                payload["reencodeReason"] = result.reencode_reason

            return jsonify(payload)
        except ValueError as e:
            logger.error("Video merge validation failed: %s", e)
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return api_error(500, "Multiple video upload failed", logger=logger, exc=e)

    @app.route("/api/content/import", methods=["POST"])
    @app.route("/api/content/import-url", methods=["POST"])
    def import_content_url():
        """
        Import video from URL (Bilibili/YouTube).

        This endpoint starts an asynchronous import job and returns immediately
        with a job_id for status tracking. The actual download happens in the background.
        """
        data = request.json or {}
        url = data.get("url")
        custom_name = data.get("custom_name")

        if not url:
            return jsonify({"error": "URL is required"}), 400

        try:
            result = content_service.start_import_video_from_url(url, custom_name)
            logger.info(
                "Started video import from URL %s as content %s (job %s)",
                url,
                result.content_id,
                result.job_id,
            )

            payload = {
                "contentId": result.content_id,
                "filename": result.filename,
                "contentType": result.content_type,
                "message": result.message,
                "status": result.status,
            }
            if result.job_id:
                payload["job_id"] = result.job_id

            return jsonify(payload)
        except ValueError as e:
            logger.error("Video import validation failed: %s", e)
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return api_error(500, "Video import failed", logger=logger, exc=e)

    @app.route("/api/content/<content_id>", methods=["PATCH"])
    @app.route("/api/content/<content_id>/rename", methods=["POST"])
    def rename_content(content_id: str):
        """
        Rename content item.
        """
        data = request.json or {}
        new_name = data.get("new_name")

        if not new_name:
            return jsonify({"error": "New name is required"}), 400

        try:
            metadata = content_service.rename_content(content_id, new_name)
            return jsonify(
                {
                    "id": metadata.id,
                    "filename": metadata.original_filename,
                    "message": "Content renamed successfully",
                },
            )
        except Exception as e:
            return api_error(500, "Rename failed", logger=logger, exc=e)

    @app.route("/api/content", methods=["GET"])
    @app.route("/api/content/list", methods=["GET"])
    def list_content():
        """
        List all content (videos and PDFs) with unified metadata.

        Returns a list sorted by creation date (newest first).
        """
        try:
            content_list = content_service.list_all_content()
            serialized = [content_service.serialize_content(c) for c in content_list]

            return jsonify({"content": serialized, "count": len(serialized)})
        except Exception as e:
            return api_error(500, "Failed to list content", logger=logger, exc=e)

    @app.route("/api/content/<content_id>", methods=["GET"])
    def get_content(content_id: str):
        """
        Get metadata for a specific content item.
        """
        try:
            metadata = content_service.get_content(content_id)
            if not metadata:
                return jsonify({"error": "Content not found"}), 404

            return jsonify(content_service.serialize_content(metadata))
        except Exception as e:
            return api_error(500, "Failed to get content", logger=logger, exc=e)

    @app.route("/api/content/<content_id>", methods=["DELETE"])
    def delete_content(content_id: str):
        """
        Delete a content item and all associated files.
        """
        try:
            result = content_service.delete_content(content_id)
            if not result.get("deleted"):
                reason = result.get("reason")
                if reason == "not_found":
                    return jsonify({"error": "Content not found"}), 404

                return jsonify(
                    {
                        "error": "Failed to delete content",
                        "details": result.get("errors", []),
                    },
                ), 500

            return jsonify(
                {
                    "deleted": True,
                    "removedFiles": result.get("removed_files", []),
                    "removedDirs": result.get("removed_dirs", []),
                },
            )
        except Exception as e:
            return api_error(500, "Failed to delete content", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/video", methods=["GET"])
    def get_content_video(content_id: str):
        """
        Stream the video file for any content (video or slide).

        For videos: returns the uploaded file
        For slides: returns the generated lecture video (if ready)
        """
        try:
            video_path = content_service.get_video_path(content_id)
            if not video_path:
                metadata = content_service.get_content(content_id)
                if not metadata:
                    return jsonify({"error": "Content not found"}), 404

                if metadata.type == "slide" and metadata.video_status == "none":
                    return jsonify({"error": "Video not yet generated for this slide"}), 404

                return jsonify({"error": "Video file not found"}), 404

            if not os.path.exists(video_path):
                return jsonify({"error": "Video file not found"}), 404

            # Use send_file with conditional=True to handle Range requests automatically
            # This is more reliable than manual streaming implementation
            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                mime_type = "video/mp4"

            range_header = request.headers.get("Range")
            if range_header:
                logger.info("Video range request: %s, range=%s", content_id, range_header)

            return send_file(
                video_path,
                mimetype=mime_type,
                as_attachment=False,
                download_name=os.path.basename(video_path),
                conditional=True,
            )

        except Exception as e:
            return api_error(500, "Failed to stream video", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/pdf", methods=["GET"])
    def get_content_pdf(content_id: str):
        """
        Get the original PDF file (only for slide content).
        """
        try:
            pdf_path = content_service.get_pdf_path(content_id)
            if not pdf_path:
                return jsonify({"error": "PDF not found or content is not a slide"}), 404

            return send_file(
                pdf_path,
                mimetype="application/pdf",
                as_attachment=False,
            )
        except Exception as e:
            return api_error(500, "Failed to serve PDF", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/subtitles/generate", methods=["POST"])
    @app.route("/api/content/<content_id>/generate-subtitles", methods=["POST"])
    @limit_generate
    def generate_content_subtitles(content_id: str):
        """
        Generate original-language subtitles for video content.

        This unified endpoint now submits a background job via TaskManager.
        Clients should poll content metadata (or /api/tasks/<task_id>) instead of
        blocking the request thread for long-running Whisper calls.
        """
        try:
            metadata = content_service.get_content(content_id)
            if not metadata:
                return jsonify({"error": "Content not found"}), 404

            if metadata.type != "video":
                return jsonify({"error": "Content is not a video"}), 400

            data = request.json or {}
            raw_source_language = data.get("source_language")
            source_language = (
                str(raw_source_language)
                if raw_source_language
                else _get_default_source_language()
            )

            force_flag = data.get("force", False)
            force = (
                str(force_flag).lower() in ("1", "true", "yes", "y")
                if isinstance(force_flag, (str, int, bool))
                else False
            )

            subtitle_path = subtitle_service.resolve_subtitle_path(content_id)

            # Short-circuit when subtitles already exist and caller did not force regeneration.
            if not force and subtitle_service.subtitles_exist(content_id):
                content_service.mark_subtitles_generated(content_id, subtitle_path)
                return jsonify(
                    {
                        "subtitle_path": subtitle_path,
                        "status": "ready",
                        "message": "Subtitles already exist",
                    },
                )

            if task_manager is None:
                return jsonify({"error": "Task manager not configured"}), 500

            metadata_payload = {
                "content_id": content_id,
                "source_language": source_language,
                "subtitle_path": subtitle_path,
            }

            task_id = task_manager.submit_task(
                content_id,
                "subtitle_generation",
                metadata=metadata_payload,
            )

            try:
                content_service.update_feature_status(
                    content_id=content_id,
                    feature="subtitle",
                    status="processing",
                    job_id=task_id,
                )
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning(
                    "Failed to update subtitle status to processing for %s: %s",
                    content_id,
                    exc,
                )

            return jsonify(
                {
                    "task_id": task_id,
                    "status": "pending",
                    "message": "Subtitle generation task submitted",
                    "subtitle_path": subtitle_path,
                },
            )
        except Exception as e:
            return api_error(500, "Subtitle generation failed", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/video", methods=["POST"])
    @app.route("/api/content/<content_id>/generate-video", methods=["POST"])
    @limit_generate
    def generate_slide_video(content_id: str):
        """
        Start video generation for a slide deck.

        Accepts optional JSON body with:
        - force: boolean - If true, regenerate even if video already exists
        """
        try:
            metadata = content_service.get_content(content_id)
            if not metadata:
                return jsonify({"error": "Content not found"}), 404

            if metadata.type != "slide":
                return jsonify({"error": "Content is not a slide deck"}), 400

            # Check for force parameter
            force = False
            if request.is_json and request.json:
                force = request.json.get("force", False)

            if not force and metadata.video_status == "ready" and metadata.video_file:
                return jsonify({
                    "status": "ready",
                    "message": "Video already generated",
                    "video_path": metadata.video_file,
                }), 200

            if task_manager is None:
                return jsonify({"error": "Task manager not configured"}), 500

            # Precompute expected output paths to keep response shape stable
            lecture_video_path = slide_service.resolve_lecture_video_path(content_id)
            subtitle_path = slide_service.resolve_subtitle_path(content_id)

            metadata_payload = {
                "content_id": content_id,
                "deck_id": content_id,
                "force": force,
            }

            task_id = task_manager.submit_task(
                content_id,
                "video_generation",
                metadata=metadata_payload,
            )

            # Update content metadata with processing status and job_id
            content_service.update_feature_status(
                content_id=content_id,
                feature="video",
                status="processing",
                job_id=task_id,
            )

            # Return result with task_id for frontend polling
            return jsonify({
                "deck_id": content_id,
                "lecture_video_path": lecture_video_path,
                "subtitle_path": subtitle_path,
                "status": "pending",
                "message": "Slide lecture generation task submitted",
                "task_id": task_id,
            })

        except Exception as e:
            return api_error(500, "Failed to start generation", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/subtitles", methods=["GET"])
    def get_content_subtitles(content_id: str):
        """
        Get subtitles for content.

        Query params:
        - format: "srt" or "vtt" (default: srt)
        - lang: "original", "translated", "enhanced" (default: original)
        """
        try:
            subtitle_format = request.args.get("format", "srt")
            lang = request.args.get("lang", "original")

            # Get the appropriate subtitle path
            if lang == "translated":
                subtitle_path = content_service.get_translated_subtitle_path(content_id)
            elif lang == "enhanced":
                subtitle_path = content_service.get_enhanced_subtitle_path(content_id)
            else:
                subtitle_path = content_service.get_subtitle_path(content_id)

            if not subtitle_path or not os.path.exists(subtitle_path):
                return jsonify({"error": "Subtitles not found"}), 404

            # Convert to VTT if requested
            if subtitle_format == "vtt":
                with open(subtitle_path, "r", encoding="utf-8") as f:
                    srt_content = f.read()
                
                vtt_content = SubtitleService.convert_srt_to_vtt(srt_content)
                
                return Response(
                    vtt_content,
                    mimetype="text/vtt",
                )

            return send_file(
                subtitle_path,
                mimetype="text/plain",
                as_attachment=False,
            )

        except Exception as e:
            return api_error(500, "Failed to serve subtitles", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/translations", methods=["POST"])
    @app.route("/api/content/<content_id>/translate-subtitles", methods=["POST"])
    @limit_generate
    def translate_content_subtitles(content_id: str):
        """
        Enhance and translate subtitles for content using unified metadata.

        This is the modern replacement for /enhance-and-translate which relied
        on raw subtitle paths. The operation is now executed asynchronously
        via TaskManager; clients are expected to poll content metadata until
        hasTranslation becomes true.
        """
        try:
            data = request.json or {}
            raw_target_language = data.get("target_language")
            force_flag = data.get("force", False)

            if raw_target_language:
                target_language = str(raw_target_language)
            else:
                # Default target language from config
                try:
                    target_language = get_settings().subtitle.translation.target_language
                except Exception:
                    target_language = "zh"

            force = (
                str(force_flag).lower() in ("1", "true", "yes", "y")
                if isinstance(force_flag, (str, int, bool))
                else False
            )

            # Resolve original subtitle path from unified metadata.
            subtitle_path = content_service.get_subtitle_path(content_id)
            if not subtitle_path or not os.path.exists(subtitle_path):
                return jsonify({"error": "Original subtitles not found"}), 404

            translated_path = subtitle_service.resolve_translation_path(
                content_id,
                target_language,
            )

            if not force and subtitle_service.translation_exists(content_id, target_language):
                content_service.mark_translation_generated(
                    content_id,
                    translated_path,
                )
                return jsonify(
                    {
                        "translated_path": translated_path,
                        "status": "ready",
                        "message": "Translated subtitles already exist",
                    },
                )

            if task_manager is None:
                return jsonify({"error": "Task manager not configured"}), 500

            metadata_payload = {
                "content_id": content_id,
                "target_language": target_language,
                "force": force,
            }

            task_id = task_manager.submit_task(
                content_id,
                "subtitle_translation",
                metadata=metadata_payload,
            )

            try:
                content_service.update_feature_status(
                    content_id=content_id,
                    feature="translation",
                    status="processing",
                    job_id=task_id,
                )
                content_service.update_feature_status(
                    content_id=content_id,
                    feature="enhanced",
                    status="processing",
                    job_id=task_id,
                )
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning(
                    "Failed to update translation/enhanced status to processing for %s: %s",
                    content_id,
                    exc,
                )

            return jsonify(
                {
                    "task_id": task_id,
                    "status": "pending",
                    "message": "Subtitle translation task submitted",
                    "translated_path": translated_path,
                },
            )
        except Exception as e:
            return api_error(500, "Failed to translate subtitles", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/note-images", methods=["POST"])
    @app.route("/api/content/upload-note-image", methods=["POST"])
    @limit_upload
    def upload_note_image(content_id: str | None = None):
        """
        Upload a pasted image from the note editor.

        Expects:
        - 'image' file in the request
        - Path param content_id (preferred) or form field 'video_id'

        Returns the filename and path for the uploaded image.
        """
        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        image_file = request.files["image"]
        video_id = (content_id or request.form.get("video_id") or "").strip()

        if not _validate_content_id(video_id):
            return jsonify({"error": "video_id is invalid"}), 400

        if image_file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        size = getattr(image_file, "content_length", None)
        if size and size > max_note_image_bytes:
            return jsonify({"error": "Image too large"}), 413

        header = _peek_bytes(image_file, 1024)
        img_type = imghdr.what(None, h=header)
        ext_map = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "gif": ".gif", "webp": ".webp"}
        ext = ext_map.get(img_type or "")
        if not ext:
            return jsonify({"error": "Unsupported image type"}), 400

        filename = f"{uuid.uuid4().hex}{ext}"

        try:
            notes_assets_dir = content_service.ensure_content_dir(str(video_id), "notes_assets")
            file_path = os.path.join(notes_assets_dir, filename)
            image_file.save(file_path)
        except ValueError:
            return jsonify({"error": "Invalid path"}), 400
        except Exception as e:
            return api_error(500, "Note image upload failed", logger=logger, exc=e)

        logger.info("Note image uploaded: %s for video %s", filename, video_id)

        return jsonify({
            "filename": filename,
            "path": file_path,
            "url": f"/notes_assets/{video_id}/{filename}"
        })
