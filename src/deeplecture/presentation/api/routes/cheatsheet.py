"""Cheatsheet routes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.domain import FeatureStatus, FeatureType
from deeplecture.presentation.api.shared import (
    accepted,
    bad_request,
    handle_errors,
    rate_limit,
    success,
)
from deeplecture.presentation.api.shared.validation import (
    ValidationError,
    validate_content_id,
    validate_language,
    validate_positive_int,
)
from deeplecture.use_cases.dto.cheatsheet import (
    GenerateCheatsheetRequest,
    SaveCheatsheetRequest,
)

if TYPE_CHECKING:
    from flask import Response

logger = logging.getLogger(__name__)

bp = Blueprint("cheatsheet", __name__)

# Maximum cheatsheet content length (100KB - typically shorter than notes)
MAX_CHEATSHEET_CONTENT_LENGTH = 100_000

# Valid parameter values
VALID_CONTEXT_MODES = {"auto", "subtitle", "slide", "both"}
VALID_CRITICALITY_LEVELS = {"high", "medium", "low"}
VALID_SUBJECT_TYPES = {"auto", "stem", "humanities"}


@bp.route("", methods=["GET"])
@handle_errors
def get_cheatsheet() -> Response:
    """Get cheatsheet for content."""
    content_id = validate_content_id(
        request.args.get("content_id"), field_name="content_id"
    )

    container = get_container()
    result = container.cheatsheet_usecase.get_cheatsheet(content_id)

    if result is None:
        return success({"content_id": content_id, "content": "", "updated_at": None})

    return success(result.to_dict())


@bp.route("", methods=["POST"])
@handle_errors
def save_cheatsheet() -> Response:
    """Save cheatsheet content."""
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    content = data.get("content", "")

    # Validate content
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise ValidationError("content must be a string")
    if len(content) > MAX_CHEATSHEET_CONTENT_LENGTH:
        raise ValidationError(
            f"content exceeds maximum length ({MAX_CHEATSHEET_CONTENT_LENGTH})"
        )

    container = get_container()
    save_request = SaveCheatsheetRequest(content_id=content_id, content=content)
    result = container.cheatsheet_usecase.save_cheatsheet(save_request)

    return success(result.to_dict())


@bp.route("/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_cheatsheet() -> Response:
    """Generate AI cheatsheet for content (async task).

    Two-stage pipeline:
    1. Extract knowledge items with criticality scoring
    2. Render into scannable Markdown format
    """
    data = request.get_json(silent=True) or {}

    content_id = validate_content_id(data.get("content_id"), field_name="content_id")
    language = validate_language(
        data.get("language"), field_name="language", default=""
    )
    if not language:
        return bad_request("language is required")

    # Context mode
    raw_context_mode = data.get("context_mode", "auto")
    if not isinstance(raw_context_mode, str):
        raise ValidationError("context_mode must be a string")
    context_mode = raw_context_mode.strip().lower() or "auto"
    if context_mode not in VALID_CONTEXT_MODES:
        raise ValidationError(
            f"context_mode must be one of: {', '.join(VALID_CONTEXT_MODES)}"
        )

    # Criticality filter
    raw_criticality = data.get("min_criticality", "medium")
    if not isinstance(raw_criticality, str):
        raise ValidationError("min_criticality must be a string")
    min_criticality = raw_criticality.strip().lower() or "medium"
    if min_criticality not in VALID_CRITICALITY_LEVELS:
        raise ValidationError(
            f"min_criticality must be one of: {', '.join(VALID_CRITICALITY_LEVELS)}"
        )

    # Subject type
    raw_subject = data.get("subject_type", "auto")
    if not isinstance(raw_subject, str):
        raise ValidationError("subject_type must be a string")
    subject_type = raw_subject.strip().lower() or "auto"
    if subject_type not in VALID_SUBJECT_TYPES:
        raise ValidationError(
            f"subject_type must be one of: {', '.join(VALID_SUBJECT_TYPES)}"
        )

    # Target pages
    target_pages = validate_positive_int(
        data.get("target_pages"), field_name="target_pages", required=False, default=2
    )

    user_instruction = data.get("user_instruction") or data.get("instruction") or ""

    # Model selection (optional)
    llm_model = data.get("llm_model") or None

    container = get_container()

    # Set cheatsheet status to PROCESSING before starting the task
    try:
        metadata = container.metadata_storage.get(content_id)
        if metadata is not None:
            metadata = metadata.with_status(
                FeatureType.CHEATSHEET.value, FeatureStatus.PROCESSING
            )
            container.metadata_storage.save(metadata)
    except Exception:
        logger.exception(
            "Failed to set cheatsheet status to PROCESSING for %s", content_id
        )

    generate_request = GenerateCheatsheetRequest(
        content_id=content_id,
        language=language,
        context_mode=context_mode,
        user_instruction=user_instruction,
        min_criticality=min_criticality,
        target_pages=target_pages,
        subject_type=subject_type,
        llm_model=llm_model,
    )

    def _run_generation(_ctx: object) -> dict:
        try:
            result = container.cheatsheet_usecase.generate_cheatsheet(generate_request)
            return result.to_dict()
        except Exception:
            # Set ERROR status on failure
            try:
                meta = container.metadata_storage.get(content_id)
                if meta is not None:
                    meta = meta.with_status(
                        FeatureType.CHEATSHEET.value, FeatureStatus.ERROR
                    )
                    container.metadata_storage.save(meta)
            except Exception:
                logger.exception(
                    "Failed to set cheatsheet status to ERROR for %s", content_id
                )
            raise

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="cheatsheet_generation",
        task=_run_generation,
        metadata={
            "language": language,
            "context_mode": context_mode,
            "min_criticality": min_criticality,
            "subject_type": subject_type,
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
