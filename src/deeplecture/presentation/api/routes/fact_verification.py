"""Fact verification routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import accepted, bad_request, handle_errors, not_found, rate_limit, success
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_language
from deeplecture.use_cases.dto.fact_verification import GenerateVerificationRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("fact_verification", __name__)


@bp.route("", methods=["GET"])
@handle_errors
def get_verification() -> Response:
    """Get fact verification report for content."""
    content_id = validate_content_id(request.args.get("content_id"), field_name="content_id")
    language = validate_language(request.args.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language query parameter is required")

    container = get_container()
    result = container.fact_verification_usecase.get_report(content_id, language)

    if result is None:
        return not_found("Verification report not found")

    return success(result.to_dict())


@bp.route("/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_verification() -> Response:
    """Generate fact verification report (async task)."""
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    language = validate_language(data.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language is required")

    container = get_container()

    # Check if content exists
    metadata = container.content_usecase.get_content(content_id)
    if metadata is None:
        return not_found(f"Content not found: {content_id}")

    req = GenerateVerificationRequest(content_id=content_id, language=language)

    def _run_generation(ctx: object) -> dict:
        result = container.fact_verification_usecase.generate_report(req)
        return result.to_dict()

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="fact_verification",
        task=_run_generation,
        metadata={"language": language},
    )

    return accepted(
        {
            "content_id": content_id,
            "task_id": task_id,
            "status": "pending",
            "message": "Fact verification started",
        }
    )
