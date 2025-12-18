"""Media file serving routes (video, pdf, screenshots)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, send_file

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import handle_errors, not_found
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_filename

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("media", __name__)

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
ALLOWED_PDF_EXT = {".pdf"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@bp.route("/<content_id>/video", methods=["GET"])
@handle_errors
def get_content_video(content_id: str) -> Response:
    """Serve the playable video for a content item."""
    content_id = validate_content_id(content_id)
    container = get_container()
    metadata = container.content_usecase.get_content(content_id)
    content_dir = Path(container.path_resolver.get_content_dir(content_id))

    candidates = []
    if getattr(metadata, "video_file", None):
        candidates.append(metadata.video_file)
    if getattr(metadata, "source_file", None):
        candidates.append(metadata.source_file)

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve(strict=False)
        if not _is_within_dir(path, content_dir):
            continue
        if path.is_file() and path.suffix.lower() in ALLOWED_VIDEO_EXT:
            return send_file(path, conditional=True)

    return not_found("No video available for this content")


@bp.route("/<content_id>/pdf", methods=["GET"])
@handle_errors
def get_content_pdf(content_id: str) -> Response:
    """Serve the PDF slide deck for a content item."""
    content_id = validate_content_id(content_id)
    container = get_container()
    metadata = container.content_usecase.get_content(content_id)
    content_dir = Path(container.path_resolver.get_content_dir(content_id))

    source_file = getattr(metadata, "source_file", "")
    if not source_file:
        return not_found("PDF not available for this content")

    path = Path(source_file).expanduser().resolve(strict=False)
    if not _is_within_dir(path, content_dir):
        return not_found("PDF not available for this content")

    if path.is_file() and path.suffix.lower() in ALLOWED_PDF_EXT:
        return send_file(path, mimetype="application/pdf", conditional=True)

    return not_found("PDF not available for this content")


@bp.route("/<content_id>/screenshots/<filename>", methods=["GET"])
@handle_errors
def get_content_screenshot(content_id: str, filename: str) -> Response:
    """Serve a captured screenshot or note image for a content item."""
    content_id = validate_content_id(content_id)
    filename = validate_filename(filename, field_name="filename", allowed_extensions=ALLOWED_IMAGE_EXT)

    container = get_container()
    container.content_usecase.get_content(content_id)

    content_dir = Path(container.path_resolver.get_content_dir(content_id))
    image_path = (content_dir / "screenshots" / filename).resolve(strict=False)

    if not _is_within_dir(image_path, content_dir):
        return not_found("Screenshot not found")
    if not image_path.is_file():
        return not_found("Screenshot not found")

    return send_file(image_path, conditional=True)


def _is_within_dir(path: Path, base_dir: Path) -> bool:
    """Check that path stays within base_dir."""
    try:
        path.resolve(strict=False).relative_to(base_dir.resolve(strict=False))
        return True
    except ValueError:
        return False
