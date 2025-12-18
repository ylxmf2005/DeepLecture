"""Upload and import routes."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.config import get_settings
from deeplecture.di import get_container
from deeplecture.presentation.api.shared import (
    accepted,
    bad_request,
    created,
    error,
    handle_errors,
    rate_limit,
)
from deeplecture.presentation.api.shared.validation import (
    validate_content_id,
    validate_filename,
    validate_title,
    validate_url,
)
from deeplecture.use_cases.dto.upload import (
    ImportVideoFromURLRequest,
    MergePDFsRequest,
    MergeVideosRequest,
    UploadPDFRequest,
    UploadVideoRequest,
)

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("upload", __name__)

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
ALLOWED_PDF_EXT = {".pdf"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@bp.route("/upload", methods=["POST"])
@rate_limit("upload")
@handle_errors
def upload_content() -> Response:
    """Upload video or PDF files (single or multiple)."""
    container = get_container()
    upload_uc = container.upload_usecase

    video_files = [f for f in request.files.getlist("videos") if f.filename]
    if video_files:
        if len(video_files) == 1:
            file = video_files[0]
            filename = validate_filename(file.filename, field_name="videos", allowed_extensions=ALLOWED_VIDEO_EXT)
            content_id = str(uuid.uuid4())
            req = UploadVideoRequest(content_id=content_id, filename=filename, file_data=file)
            result = upload_uc.upload_video(req)
            return created(_serialize_upload_result(result))
        else:
            for f in video_files:
                validate_filename(f.filename, field_name="videos", allowed_extensions=ALLOWED_VIDEO_EXT)
            custom_name = validate_title(
                request.form.get("custom_name"), field_name="custom_name", default="Merged Video"
            )
            req = MergeVideosRequest(file_data_list=video_files, custom_name=custom_name, async_mode=True)
            result = upload_uc.merge_videos(req)
            return created(_serialize_upload_result(result))

    pdf_files = [f for f in request.files.getlist("pdfs") if f.filename]
    if pdf_files:
        if len(pdf_files) == 1:
            file = pdf_files[0]
            filename = validate_filename(file.filename, field_name="pdfs", allowed_extensions=ALLOWED_PDF_EXT)
            content_id = str(uuid.uuid4())
            req = UploadPDFRequest(content_id=content_id, filename=filename, file_data=file)
            result = upload_uc.upload_pdf(req)
            return created(_serialize_upload_result(result))
        else:
            for f in pdf_files:
                validate_filename(f.filename, field_name="pdfs", allowed_extensions=ALLOWED_PDF_EXT)
            custom_name = validate_title(
                request.form.get("custom_name"), field_name="custom_name", default="Merged PDF"
            )
            req = MergePDFsRequest(file_data_list=pdf_files, custom_name=custom_name, async_mode=True)
            result = upload_uc.merge_pdfs(req)
            return created(_serialize_upload_result(result))

    return bad_request("No file provided. Use 'videos' or 'pdfs' field.")


@bp.route("/upload-note-image", methods=["POST"])
@rate_limit("upload")
@handle_errors
def upload_note_image() -> Response:
    """Upload an image for notes."""
    container = get_container()
    settings = get_settings()

    content_id_raw = request.form.get("content_id") or request.form.get("contentId")
    content_id = validate_content_id(content_id_raw, field_name="content_id")
    container.content_usecase.get_content(content_id)

    image = request.files.get("image")
    if image is None or not image.filename:
        return bad_request("image file is required")

    max_bytes = int(settings.server.max_note_image_bytes)
    try:
        image.stream.seek(0, os.SEEK_END)
        size = int(image.stream.tell())
        image.stream.seek(0)
        if size > max_bytes:
            return bad_request(f"Image exceeds maximum size ({max_bytes} bytes)")
    except (OSError, AttributeError):
        if request.content_length and request.content_length > max_bytes:
            return bad_request(f"Image exceeds maximum size ({max_bytes} bytes)")

    original = validate_filename(image.filename, field_name="image.filename", allowed_extensions=ALLOWED_IMAGE_EXT)
    ext = Path(original).suffix.lower()
    filename = f"note_{uuid.uuid4().hex}{ext}"

    content_dir = Path(container.path_resolver.get_content_dir(content_id))
    screenshots_dir = content_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    output_path = (screenshots_dir / filename).resolve(strict=False)

    try:
        output_path.relative_to(content_dir.resolve(strict=False))
    except ValueError:
        return error("Failed to resolve output path", status=500)

    image.save(str(output_path))

    return created(
        {
            "content_id": content_id,
            "filename": filename,
            "url": f"/api/content/{content_id}/screenshots/{filename}",
        }
    )


@bp.route("/import-url", methods=["POST"])
@rate_limit("upload")
@handle_errors
def import_from_url() -> Response:
    """Import video from URL (async)."""
    data = request.get_json() or {}
    url = validate_url(data.get("url"), field_name="url")
    custom_name = validate_title(data.get("custom_name"), field_name="custom_name", default="") or None

    container = get_container()
    req = ImportVideoFromURLRequest(url=url, custom_name=custom_name)
    result = container.upload_usecase.start_import_video_from_url(req)

    return accepted(
        {
            "content_id": result.content_id,
            "filename": result.filename,
            "content_type": result.content_type,
            "status": "pending",
            "task_id": result.job_id,
            "message": result.message,
        }
    )


def _serialize_upload_result(result: object) -> dict:
    """Serialize UploadResult to API response format."""
    return {
        "content_id": result.content_id,
        "filename": result.filename,
        "content_type": result.content_type,
        "message": result.message,
    }
