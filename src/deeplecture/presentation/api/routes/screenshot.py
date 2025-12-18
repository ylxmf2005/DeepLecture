"""Screenshot capture routes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import bad_request, error, handle_errors, not_found, rate_limit, success
from deeplecture.presentation.api.shared.validation import validate_content_id

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("screenshot", __name__)


@bp.route("/<content_id>/screenshots", methods=["POST"])
@rate_limit("generate")
@handle_errors
def create_screenshot(content_id: str) -> Response:
    """Capture a video frame at specified timestamp."""
    content_id = validate_content_id(content_id)
    data = request.get_json(silent=True) or {}

    timestamp = data.get("timestamp")
    if timestamp is None:
        return bad_request("timestamp is required")

    try:
        timestamp = float(timestamp)
    except (TypeError, ValueError):
        return bad_request("timestamp must be a number")

    container = get_container()

    video_path = container.artifact_storage.get_path(content_id, "video", fallback_kinds=["source"])
    if video_path is None:
        metadata = container.content_usecase.get_content(content_id)
        for candidate in (getattr(metadata, "video_file", None), getattr(metadata, "source_file", None)):
            if not candidate:
                continue
            p = Path(candidate).expanduser().resolve(strict=False)
            if p.is_file():
                video_path = str(p)
                break
    if video_path is None:
        return not_found("No video found for content")

    content_dir = container.path_resolver.get_content_dir(content_id)
    screenshots_dir = os.path.join(content_dir, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    filename = f"frame_{int(timestamp * 1000)}.png"
    output_path = os.path.join(screenshots_dir, filename)

    try:
        container.video_processor.extract_frame(video_path, timestamp, output_path)
    except RuntimeError:
        return error("Failed to capture frame", status=500)

    image_url = f"/api/content/{content_id}/screenshots/{filename}"

    return success({"image_url": image_url, "timestamp": timestamp})
