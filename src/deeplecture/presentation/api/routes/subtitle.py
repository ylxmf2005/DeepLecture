"""Subtitle routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint, request
from flask import Response as FlaskResponse

from deeplecture.di import get_container
from deeplecture.domain import FeatureStatus
from deeplecture.presentation.api.shared import accepted, bad_request, handle_errors, not_found, rate_limit, success
from deeplecture.presentation.api.shared.model_resolution import resolve_models_for_task
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_language
from deeplecture.use_cases.dto.subtitle import EnhanceTranslateRequest, GenerateSubtitleRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("subtitle", __name__)


@bp.route("/<content_id>", methods=["GET"])
@handle_errors
def get_subtitle(content_id: str) -> Response:
    """Get subtitles for content."""
    content_id = validate_content_id(content_id)
    language = validate_language(request.args.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language query parameter is required")

    container = get_container()
    result = container.subtitle_usecase.get_subtitles(content_id, language)

    if result is None:
        return not_found(f"Subtitles not found: {language}")

    return success(
        {
            "content_id": result.content_id,
            "language": result.language,
            "segments": [{"start": seg.start, "end": seg.end, "text": seg.text} for seg in result.segments],
            "count": len(result.segments),
        }
    )


@bp.route("/<content_id>/vtt", methods=["GET"])
@handle_errors
def get_subtitle_vtt(content_id: str) -> Response:
    """Get subtitles in WebVTT format."""
    content_id = validate_content_id(content_id)
    language = validate_language(request.args.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language query parameter is required")

    container = get_container()
    result = container.subtitle_usecase.get_subtitles(content_id, language)
    if result is None:
        return not_found(f"Subtitles not found: {language}")

    vtt_content = result.to_vtt()
    return FlaskResponse(
        vtt_content,
        mimetype="text/vtt",
        headers={"Content-Disposition": f"inline; filename={content_id}_{language}.vtt"},
    )


@bp.route("/<content_id>/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_subtitle(content_id: str) -> Response:
    """Generate subtitles using ASR."""
    content_id = validate_content_id(content_id)
    data = request.get_json() or {}
    language = validate_language(data.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language is required")

    container = get_container()
    metadata = container.content_usecase.get_content(content_id)
    force = bool(data.get("force", False))

    if not force and getattr(metadata, "subtitle_status", "none") == FeatureStatus.READY.value:
        return success({"content_id": content_id, "status": "ready", "message": "Subtitles already generated"})

    req = GenerateSubtitleRequest(content_id=content_id, language=language)

    def _run(ctx: object) -> dict:
        result = container.subtitle_usecase.generate(req)
        return {"content_id": result.content_id, "language": result.language}

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="subtitle_generation",
        task=_run,
        metadata={"language": language},
    )

    container.content_usecase.update_feature_status(content_id, "subtitle", "processing", job_id=task_id)

    return accepted(
        {"content_id": content_id, "task_id": task_id, "status": "pending", "message": "Subtitle generation started"}
    )


@bp.route("/<content_id>/enhance-translate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def enhance_and_translate(content_id: str) -> Response:
    """Enhance and translate subtitles using LLM."""
    content_id = validate_content_id(content_id)
    data = request.get_json() or {}
    source_language = validate_language(data.get("source_language"), field_name="source_language", default="")
    target_language = validate_language(data.get("target_language"), field_name="target_language", default="")

    if not source_language:
        return bad_request("source_language is required")
    if not target_language:
        return bad_request("target_language is required")

    container = get_container()
    metadata = container.content_usecase.get_content(content_id)
    force = bool(data.get("force", False))

    # Model and prompt selection (optional, None = use defaults)
    llm_model = data.get("llm_model") or None
    prompts = data.get("prompts") or None

    llm_model, _ = resolve_models_for_task(
        container=container,
        content_id=content_id,
        task_key="subtitle_translation",
        llm_model=llm_model,
        tts_model=None,
    )

    if not force and getattr(metadata, "enhance_translate_status", "none") == FeatureStatus.READY.value:
        return success(
            {"content_id": content_id, "status": "ready", "message": "Enhancement and translation already completed"}
        )

    req = EnhanceTranslateRequest(
        content_id=content_id,
        source_language=source_language,
        target_language=target_language,
        llm_model=llm_model,
        prompts=prompts,
    )

    def _run(ctx: object) -> dict:
        container.subtitle_usecase.enhance_and_translate(req)
        return {"content_id": content_id, "source_language": source_language, "target_language": target_language}

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="subtitle_translation",
        task=_run,
        metadata={"source_language": source_language, "target_language": target_language},
    )

    container.content_usecase.update_feature_status(content_id, "enhance_translate", "processing", job_id=task_id)

    return accepted(
        {
            "content_id": content_id,
            "task_id": task_id,
            "status": "pending",
            "message": "Enhancement and translation started",
        }
    )
