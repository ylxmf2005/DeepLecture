"""Cheatsheet routes."""

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
from deeplecture.use_cases.dto.cheatsheet import GenerateCheatsheetRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("cheatsheet", __name__)


@bp.route("", methods=["GET"])
@handle_errors
def get_cheatsheet() -> Response:
    """Get cheatsheet for content."""
    content_id = validate_content_id(request.args.get("content_id"), field_name="content_id")

    container = get_container()
    result = container.cheatsheet_usecase.get(content_id)

    return success(result.to_dict())


@bp.route("", methods=["POST"])
@handle_errors
def save_cheatsheet() -> Response:
    """Save cheatsheet content."""
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    content = data.get("content", "")

    container = get_container()
    result = container.cheatsheet_usecase.save(content_id, content)

    return success(result.to_dict())


@bp.route("/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_cheatsheet() -> Response:
    """Generate AI cheatsheet for content (async task).

    Parameters:
        content_id: Content identifier (required)
        language: Output language (required)
        context_mode: "auto" | "subtitle" | "slide" | "both" (default: "auto")
        user_instruction: Additional generation guidance (optional)
        min_criticality: "high" | "medium" | "low" (default: "medium")
        target_pages: Target length in pages (default: 2)
        subject_type: "auto" | "stem" | "humanities" (default: "auto")
    """
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    language = validate_language(data.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language is required")

    context_mode = data.get("context_mode", "auto")
    user_instruction = data.get("user_instruction") or data.get("instruction") or ""
    min_criticality = data.get("min_criticality", "medium")
    target_pages = validate_positive_int(data.get("target_pages"), field_name="target_pages", required=False, default=2)
    subject_type = data.get("subject_type", "auto")

    # Validate enum values
    valid_context_modes = {"auto", "subtitle", "slide", "both"}
    if context_mode not in valid_context_modes:
        return bad_request(f"context_mode must be one of: {', '.join(valid_context_modes)}")

    valid_criticality = {"high", "medium", "low"}
    if min_criticality not in valid_criticality:
        return bad_request(f"min_criticality must be one of: {', '.join(valid_criticality)}")

    valid_subjects = {"auto", "stem", "humanities"}
    if subject_type not in valid_subjects:
        return bad_request(f"subject_type must be one of: {', '.join(valid_subjects)}")

    llm_model = data.get("llm_model") or None
    prompts = data.get("prompts") or None

    container = get_container()
    llm_model, _ = resolve_models_for_task(
        container=container,
        content_id=content_id,
        task_key="cheatsheet_generation",
        llm_model=llm_model,
        tts_model=None,
    )

    generate_request = GenerateCheatsheetRequest(
        content_id=content_id,
        language=language,
        context_mode=context_mode,
        user_instruction=user_instruction,
        min_criticality=min_criticality,
        target_pages=target_pages if target_pages is not None else 2,
        subject_type=subject_type,
        llm_model=llm_model,
        prompts=prompts,
    )

    def _run_generation(ctx: object) -> dict:
        result = container.cheatsheet_usecase.generate(generate_request)
        return result.to_dict()

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="cheatsheet_generation",
        task=_run_generation,
        metadata={
            "language": language,
            "context_mode": context_mode,
            "min_criticality": min_criticality,
        },
    )

    return accepted(
        {
            "content_id": content_id,
            "task_id": task_id,
            "status": "pending",
            "message": "Cheatsheet generation started",
        }
    )
