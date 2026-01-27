"""Note routes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.config import get_settings
from deeplecture.di import get_container
from deeplecture.domain import FeatureStatus, FeatureType
from deeplecture.presentation.api.shared import accepted, bad_request, handle_errors, rate_limit, success
from deeplecture.presentation.api.shared.validation import (
    ValidationError,
    validate_content_id,
    validate_language,
    validate_positive_int,
)
from deeplecture.use_cases.dto.note import GenerateNoteRequest, SaveNoteRequest

if TYPE_CHECKING:
    from flask import Response

logger = logging.getLogger(__name__)

bp = Blueprint("notes", __name__)

# Maximum note content length (200KB)
MAX_NOTE_CONTENT_LENGTH = 200_000


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

    # Validate content
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise ValidationError("content must be a string")
    if len(content) > MAX_NOTE_CONTENT_LENGTH:
        raise ValidationError(f"content exceeds maximum length ({MAX_NOTE_CONTENT_LENGTH})")

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

    # Get default context_mode from settings
    settings = get_settings()
    default_context_mode = settings.note.default_context_mode

    raw_context_mode = data.get("context_mode")
    if raw_context_mode is None:
        context_mode = default_context_mode
    elif not isinstance(raw_context_mode, str):
        raise ValidationError("context_mode must be a string")
    else:
        context_mode = raw_context_mode.strip() or default_context_mode

    learner_profile = data.get("learner_profile", "")
    user_instruction = data.get("user_instruction") or data.get("instruction") or ""
    max_parts = validate_positive_int(data.get("max_parts"), field_name="max_parts", required=False, default=None)

    # Model and prompt selection (optional, None = use defaults)
    llm_model = data.get("llm_model") or None

    # Validate prompts parameter
    raw_prompts = data.get("prompts")
    prompts: dict[str, str] | None = None
    if raw_prompts is not None:
        if not isinstance(raw_prompts, dict):
            raise ValidationError("prompts must be an object mapping func_id to impl_id")

        allowed_func_ids = {"note_outline", "note_part"}
        cleaned: dict[str, str] = {}

        for func_id, impl_id in raw_prompts.items():
            if not isinstance(func_id, str):
                raise ValidationError("prompts keys must be strings")
            if func_id not in allowed_func_ids:
                raise ValidationError(f"Unsupported prompts func_id: {func_id}")

            if impl_id is None:
                continue
            if not isinstance(impl_id, str):
                raise ValidationError(f"prompts['{func_id}'] must be a string")

            impl_id_str = impl_id.strip()
            if not impl_id_str:
                continue
            cleaned[func_id] = impl_id_str

        prompts = cleaned or None

    container = get_container()

    # Set notes_status to PROCESSING before starting the task
    try:
        metadata = container.metadata_storage.get(content_id)
        if metadata is not None:
            metadata = metadata.with_status(FeatureType.NOTES.value, FeatureStatus.PROCESSING)
            container.metadata_storage.save(metadata)
    except Exception:
        logger.exception("Failed to set notes status to PROCESSING for %s", content_id)

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

    def _run_generation(_ctx: object) -> dict:
        try:
            result = container.note_usecase.generate_note(generate_request)
            return result.to_dict()
        except Exception:
            # Set ERROR status on failure
            try:
                meta = container.metadata_storage.get(content_id)
                if meta is not None:
                    meta = meta.with_status(FeatureType.NOTES.value, FeatureStatus.ERROR)
                    container.metadata_storage.save(meta)
            except Exception:
                logger.exception("Failed to set notes status to ERROR for %s", content_id)
            raise

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
