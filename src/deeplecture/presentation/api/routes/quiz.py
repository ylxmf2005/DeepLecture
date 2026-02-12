"""Quiz routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import (
    accepted,
    bad_request,
    handle_errors,
    not_found,
    rate_limit,
    success,
)
from deeplecture.presentation.api.shared.validation import (
    validate_content_id,
    validate_language,
)
from deeplecture.use_cases.dto.quiz import GenerateQuizRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("quiz", __name__)


@bp.route("/<content_id>", methods=["GET"])
@handle_errors
def get_quiz(content_id: str) -> Response:
    """Get quiz for content."""
    content_id = validate_content_id(content_id)
    language = validate_language(request.args.get("language"), field_name="language", default="") or None

    container = get_container()
    result = container.quiz_usecase.get(content_id, language)

    if not result.items:
        return not_found(f"Quiz not found for {content_id}")

    return success(result.to_dict())


@bp.route("/<content_id>/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_quiz(content_id: str) -> Response:
    """Generate quiz using LLM (async task)."""
    content_id = validate_content_id(content_id)
    data = request.get_json() or {}

    # Validate language
    language = validate_language(data.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language is required")

    # Optional parameters
    question_count = data.get("question_count", 5)
    if not isinstance(question_count, int) or question_count < 1 or question_count > 20:
        return bad_request("question_count must be an integer between 1 and 20")

    context_mode = data.get("context_mode", "auto")
    user_instruction = data.get("user_instruction", "").strip()
    min_criticality = data.get("min_criticality", "medium")
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
    req = GenerateQuizRequest(
        content_id=content_id,
        language=language,
        question_count=question_count,
        context_mode=context_mode,
        user_instruction=user_instruction,
        min_criticality=min_criticality,
        subject_type=subject_type,
        llm_model=llm_model,
        prompts=prompts,
    )

    def _run_generation(ctx: object) -> dict:
        result = container.quiz_usecase.generate(req)
        return result.to_dict()

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="quiz_generation",
        task=_run_generation,
        metadata={
            "language": language,
            "question_count": question_count,
            "context_mode": context_mode,
        },
    )

    return accepted(
        {
            "content_id": content_id,
            "task_id": task_id,
            "status": "pending",
            "message": "Quiz generation started",
        }
    )
