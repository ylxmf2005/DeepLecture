"""Podcast routes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, request, send_file

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import (
    accepted,
    bad_request,
    handle_errors,
    not_found,
    rate_limit,
    success,
)
from deeplecture.presentation.api.shared.model_resolution import resolve_models_for_task
from deeplecture.presentation.api.shared.validation import (
    validate_content_id,
    validate_language,
)
from deeplecture.use_cases.dto.podcast import GeneratePodcastRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("podcast", __name__)


@bp.route("/<content_id>", methods=["GET"])
@handle_errors
def get_podcast(content_id: str) -> Response:
    """Get podcast manifest for content."""
    content_id = validate_content_id(content_id)
    language = validate_language(request.args.get("language"), field_name="language", default="") or None

    container = get_container()
    result = container.podcast_usecase.get(content_id, language)

    if not result.segments:
        return not_found(f"Podcast not found for {content_id}")

    return success(result.to_dict())


@bp.route("/<content_id>/audio", methods=["GET"])
@handle_errors
def get_podcast_audio(content_id: str) -> Response:
    """Stream podcast audio file (M4A)."""
    content_id = validate_content_id(content_id)
    language = validate_language(request.args.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language is required")

    container = get_container()
    audio_path_str = container.podcast_storage.get_audio_path(content_id, language)
    audio_path = Path(audio_path_str)

    if not audio_path.is_file():
        return not_found("Podcast audio not found")

    return send_file(audio_path, mimetype="audio/mp4", conditional=True)


@bp.route("/<content_id>/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_podcast(content_id: str) -> Response:
    """Generate podcast using LLM + TTS (async task)."""
    content_id = validate_content_id(content_id)
    data = request.get_json() or {}

    # Validate language
    language = validate_language(data.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language is required")

    context_mode = data.get("context_mode", "both")
    user_instruction = data.get("user_instruction", "").strip()
    subject_type = data.get("subject_type", "auto")

    # Validate enum values
    valid_context_modes = {"subtitle", "slide", "both"}
    if context_mode not in valid_context_modes:
        return bad_request(f"context_mode must be one of: {', '.join(sorted(valid_context_modes))}")

    valid_subjects = {"auto", "stem", "humanities"}
    if subject_type not in valid_subjects:
        return bad_request(f"subject_type must be one of: {', '.join(valid_subjects)}")

    # Model selection: LLM resolved via standard cascade, TTS per-speaker from request body
    llm_model = data.get("llm_model") or None
    tts_model_host = data.get("tts_model_host") or None
    tts_model_guest = data.get("tts_model_guest") or None
    voice_id_host = data.get("voice_id_host") or None
    voice_id_guest = data.get("voice_id_guest") or None
    turn_gap_seconds = data.get("turn_gap_seconds", 0.3)
    prompts = data.get("prompts") or None

    container = get_container()
    llm_model, default_tts_model = resolve_models_for_task(
        container=container,
        content_id=content_id,
        task_key="podcast_generation",
        llm_model=llm_model,
        tts_model=None,
    )

    # Per-speaker TTS: fall back to cascade-resolved default if not explicitly set
    if not tts_model_host:
        tts_model_host = default_tts_model
    if not tts_model_guest:
        tts_model_guest = default_tts_model

    req = GeneratePodcastRequest(
        content_id=content_id,
        language=language,
        context_mode=context_mode,
        user_instruction=user_instruction,
        subject_type=subject_type,
        llm_model=llm_model,
        tts_model_host=tts_model_host,
        tts_model_guest=tts_model_guest,
        voice_id_host=voice_id_host,
        voice_id_guest=voice_id_guest,
        turn_gap_seconds=float(turn_gap_seconds),
        prompts=prompts,
    )

    def _run_generation(_ctx: object) -> dict:
        result = container.podcast_usecase.generate(req)
        return result.to_dict()

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="podcast_generation",
        task=_run_generation,
        metadata={
            "language": language,
            "context_mode": context_mode,
        },
    )

    return accepted(
        {
            "content_id": content_id,
            "task_id": task_id,
            "status": "pending",
            "message": "Podcast generation started",
        }
    )
