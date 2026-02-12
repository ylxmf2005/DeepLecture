"""Note routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import accepted, bad_request, handle_errors, rate_limit, success
from deeplecture.presentation.api.shared.model_resolution import resolve_models_for_task
from deeplecture.presentation.api.shared.validation import (
    validate_content_id,
    validate_language,
    validate_positive_int,
)
from deeplecture.use_cases.dto.note import GenerateNoteRequest, SaveNoteRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("notes", __name__)


@bp.route("", methods=["GET"])
@handle_errors
def get_note() -> Response:
    """Get note for content."""
    content_id = validate_content_id(request.args.get("content_id"), field_name="content_id")

    container = get_container()
    result = container.note_usecase.get_note(content_id)

    if result is None:
        return success({"content_id": content_id, "content": "", "updated_at": None})

    return success(result.to_dict())


@bp.route("", methods=["POST"])
@handle_errors
def save_note() -> Response:
    """Save note content."""
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    content = data.get("content", "")

    container = get_container()
    save_request = SaveNoteRequest(content_id=content_id, content=content)
    result = container.note_usecase.save_note(save_request)

    return success(result.to_dict())


@bp.route("/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_note() -> Response:
    """Generate AI notes for content (async task)."""
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    language = validate_language(data.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language is required")

    context_mode = data.get("context_mode", "auto")
    learner_profile = data.get("learner_profile", "")
    user_instruction = data.get("user_instruction") or data.get("instruction") or ""
    max_parts = validate_positive_int(data.get("max_parts"), field_name="max_parts", required=False, default=None)

    # Model and prompt selection (optional, None = use defaults)
    llm_model = data.get("llm_model") or None
    prompts = data.get("prompts") or None

    container = get_container()
    llm_model, _ = resolve_models_for_task(
        container=container,
        content_id=content_id,
        task_key="note_generation",
        llm_model=llm_model,
        tts_model=None,
    )

    generate_request = GenerateNoteRequest(
        content_id=content_id,
        language=language,
        context_mode=context_mode,
        learner_profile=learner_profile,
        user_instruction=user_instruction,
        max_parts=max_parts,
        llm_model=llm_model,
        prompts=prompts,
    )

    def _run_generation(ctx: object) -> dict:
        result = container.note_usecase.generate_note(generate_request)
        return result.to_dict()

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="note_generation",
        task=_run_generation,
        metadata={"language": language, "context_mode": context_mode},
    )

    return accepted(
        {
            "content_id": content_id,
            "task_id": task_id,
            "status": "pending",
            "message": "Note generation started",
        }
    )
