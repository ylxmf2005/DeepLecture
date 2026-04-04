"""Slide video generation routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.domain import ContentType, FeatureStatus
from deeplecture.presentation.api.shared import accepted, bad_request, handle_errors, rate_limit, success
from deeplecture.presentation.api.shared.model_resolution import resolve_models_for_task
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_language
from deeplecture.use_cases.dto.slide import SlideGenerationRequest
from deeplecture.use_cases.shared.source_language import (
    SourceLanguageResolutionError,
    resolve_source_language,
)

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("generation", __name__)


@bp.route("/<content_id>/generate-video", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_slide_video(content_id: str) -> Response:
    """Generate a lecture video from a slide deck (async task)."""
    content_id = validate_content_id(content_id)
    data = request.get_json(silent=True) or {}

    source_language = validate_language(
        data.get("source_language"),
        field_name="source_language",
        default="",
        allow_auto=True,
    )
    target_language = validate_language(data.get("target_language"), field_name="target_language", default="")

    if not source_language:
        return bad_request("source_language is required")
    if not target_language:
        return bad_request("target_language is required")

    tts_language = str(data.get("tts_language", "source")).strip().lower() or "source"
    if tts_language not in ("source", "target"):
        return bad_request("tts_language must be 'source' or 'target'")

    force = bool(data.get("force", False))

    # Runtime model/prompt selection
    llm_model = data.get("llm_model") or None
    tts_model = data.get("tts_model") or None
    prompts_dict = data.get("prompts") or None
    # Convert dict to tuple of tuples for frozen dataclass
    prompts = tuple(prompts_dict.items()) if prompts_dict else None

    container = get_container()
    llm_model, tts_model = resolve_models_for_task(
        container=container,
        content_id=content_id,
        task_key="video_generation",
        llm_model=llm_model,
        tts_model=tts_model,
    )
    metadata = container.content_usecase.get_content(content_id)

    if metadata.type != ContentType.SLIDE:
        return bad_request("generate-video is only supported for slide content")

    try:
        resolved_source_language = resolve_source_language(
            source_language,
            metadata=metadata,
            field_name="source_language",
        )
    except SourceLanguageResolutionError:
        return bad_request(
            "source_language is set to auto, but slide video generation needs a concrete source language. "
            "Choose a specific source language before generating the video."
        )

    if not force and getattr(metadata, "video_status", "none") == FeatureStatus.READY.value:
        return success({"deck_id": content_id, "status": "ready", "message": "Video already generated"})

    gen_request = SlideGenerationRequest(
        content_id=content_id,
        source_language=resolved_source_language,
        target_language=target_language,
        tts_language=tts_language,
        llm_model=llm_model,
        tts_model=tts_model,
        prompts=prompts,
    )

    def _run(ctx: object) -> dict:
        result = container.slide_lecture_usecase.generate(gen_request)
        return {"video_path": result.video_path}

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="video_generation",
        task=_run,
        metadata={
            "source_language": source_language,
            "resolved_source_language": resolved_source_language,
            "target_language": target_language,
            "tts_language": tts_language,
        },
    )

    container.content_usecase.update_feature_status(content_id, "video", "processing", job_id=task_id)

    return accepted(
        {
            "deck_id": content_id,
            "status": "pending",
            "message": "Video generation started",
            "task_id": task_id,
        }
    )
