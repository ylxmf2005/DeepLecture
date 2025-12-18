"""Timeline routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import accepted, bad_request, handle_errors, not_found, rate_limit, success
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_language
from deeplecture.use_cases.dto.timeline import GenerateTimelineRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("timeline", __name__)


@bp.route("/<content_id>", methods=["GET"])
@handle_errors
def get_timeline(content_id: str) -> Response:
    """Get timeline for content."""
    content_id = validate_content_id(content_id)
    language = validate_language(request.args.get("language"), field_name="language", default="") or None

    container = get_container()
    result = container.timeline_usecase.get_timeline(content_id, language)

    if result is None:
        return not_found(f"Timeline not found for {content_id}")

    return success(
        {
            "content_id": result.content_id,
            "language": result.language,
            "entries": [_serialize_entry(e) for e in result.entries],
            "count": len(result.entries),
            "cached": result.cached,
            "status": result.status,
        }
    )


@bp.route("/<content_id>/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_timeline(content_id: str) -> Response:
    """Generate timeline using LLM (async task)."""
    content_id = validate_content_id(content_id)
    data = request.get_json() or {}

    # Validate both language parameters
    subtitle_language = validate_language(data.get("subtitle_language"), field_name="subtitle_language", default="")
    output_language = validate_language(data.get("output_language"), field_name="output_language", default="")
    if not subtitle_language:
        return bad_request("subtitle_language is required")
    if not output_language:
        return bad_request("output_language is required")

    learner_profile = data.get("learner_profile", "").strip() or None
    force = bool(data.get("force", False))

    # Model and prompt selection (optional, None = use defaults)
    llm_model = data.get("llm_model") or None
    prompts = data.get("prompts") or None

    container = get_container()
    req = GenerateTimelineRequest(
        content_id=content_id,
        subtitle_language=subtitle_language,
        output_language=output_language,
        learner_profile=learner_profile,
        force=force,
        llm_model=llm_model,
        prompts=prompts,
    )

    def _run_generation(ctx: object) -> dict:
        result = container.timeline_usecase.generate(req)
        return {
            "content_id": result.content_id,
            "language": result.language,
            "entries": [_serialize_entry(e) for e in result.entries],
            "count": len(result.entries),
            "status": result.status,
        }

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="timeline_generation",
        task=_run_generation,
        metadata={
            "subtitle_language": subtitle_language,
            "output_language": output_language,
            "learner_profile": learner_profile,
        },
    )

    return accepted(
        {
            "content_id": content_id,
            "task_id": task_id,
            "status": "pending",
            "message": "Timeline generation started",
        }
    )


def _serialize_entry(entry: object) -> dict:
    """Serialize timeline entry to API format."""
    return {
        "id": entry.id,
        "kind": entry.kind,
        "start": entry.start,
        "end": entry.end,
        "title": entry.title,
        "markdown": entry.markdown,
    }
