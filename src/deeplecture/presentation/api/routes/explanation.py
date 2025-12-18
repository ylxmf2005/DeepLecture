"""AI explanation routes."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import (
    accepted,
    bad_request,
    handle_errors,
    rate_limit,
    success,
)
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_language
from deeplecture.use_cases.dto.explanation import GenerateExplanationRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("explanation", __name__)


@bp.route("/<content_id>/explanations", methods=["POST"])
@rate_limit("generate")
@handle_errors
def create_explanation(content_id: str) -> Response:
    """Generate AI explanation for a captured slide (async task)."""
    content_id = validate_content_id(content_id)
    data = request.get_json(silent=True) or {}

    image_url = data.get("image_url", "").strip()
    timestamp = data.get("timestamp")
    learner_profile = data.get("learner_profile", "").strip() or None
    context_window = data.get("subtitle_context_window_seconds", 60)

    # Language parameters (subtitle_language → output_language order)
    subtitle_language = validate_language(data.get("subtitle_language"), field_name="subtitle_language", default="")
    output_language = validate_language(data.get("output_language"), field_name="output_language", default="")

    if not image_url:
        return bad_request("image_url is required")
    if timestamp is None:
        return bad_request("timestamp is required")
    if not output_language:
        return bad_request("output_language is required")

    try:
        timestamp = float(timestamp)
        context_window = float(context_window)
    except (TypeError, ValueError):
        return bad_request("timestamp and context_window must be numbers")

    # Model and prompt selection (optional, None = use defaults)
    llm_model = data.get("llm_model") or None
    prompts = data.get("prompts") or None

    container = get_container()

    # Resolve image URL to local path
    image_path = _resolve_image_url_to_path(container, content_id, image_url)
    if image_path is None:
        return bad_request("image_url must reference a captured screenshot for this content")

    # Generate entry ID and save pending entry immediately
    entry_id = str(uuid.uuid4())
    pending_entry = {
        "id": entry_id,
        "timestamp": timestamp,
        "explanation": None,  # Pending - will be filled by use case
        "created_at": datetime.now(timezone.utc).isoformat(),
        "image_url": image_url,
        "language": output_language,
    }
    container.explanation_storage.save(content_id, pending_entry)

    req = GenerateExplanationRequest(
        content_id=content_id,
        entry_id=entry_id,
        image_path=image_path,
        image_url=image_url,
        timestamp=timestamp,
        subtitle_language=subtitle_language or None,
        output_language=output_language,
        learner_profile=learner_profile,
        subtitle_context_window_seconds=context_window,
        llm_model=llm_model,
        prompts=prompts,
    )

    def _run_generation(ctx: object) -> dict:
        result = container.explanation_usecase.generate(req)
        return result.to_dict()

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="slide_explanation",
        task=_run_generation,
        metadata={
            "entry_id": entry_id,
            "timestamp": timestamp,
            "subtitle_language": subtitle_language,
            "output_language": output_language,
            "learner_profile": learner_profile,
        },
    )

    return accepted(
        {
            "content_id": content_id,
            "task_id": task_id,
            "entry_id": entry_id,
            "status": "pending",
            "message": "Explanation generation started",
        }
    )


@bp.route("/<content_id>/explanations", methods=["GET"])
@handle_errors
def list_explanations(content_id: str) -> Response:
    """Get explanation history for content."""
    content_id = validate_content_id(content_id)
    container = get_container()
    history = container.explanation_storage.load(content_id)
    return success({"history": history})


@bp.route("/<content_id>/explanations/<explanation_id>", methods=["DELETE"])
@handle_errors
def delete_explanation(content_id: str, explanation_id: str) -> Response:
    """Delete an explanation from history."""
    content_id = validate_content_id(content_id)
    explanation_id = explanation_id.strip()
    if not explanation_id:
        return bad_request("explanation_id is required")

    container = get_container()
    deleted = container.explanation_storage.delete(content_id, explanation_id)
    return success({"deleted": deleted})


def _resolve_image_url_to_path(container: object, content_id: str, image_url: str) -> str | None:
    """Resolve an API screenshot URL to a local filesystem path."""
    url = (image_url or "").strip()
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return None

    prefix = f"/api/content/{content_id}/screenshots/"
    if not parsed.path.startswith(prefix):
        return None

    filename = os.path.basename(parsed.path)
    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None

    content_dir = container.path_resolver.get_content_dir(content_id)
    local_path = os.path.join(content_dir, "screenshots", filename)
    if not os.path.isfile(local_path):
        return None
    return local_path
