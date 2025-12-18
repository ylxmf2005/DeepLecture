"""Voiceover routes."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, send_file

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import (
    accepted,
    bad_request,
    error,
    handle_errors,
    not_found,
    rate_limit,
    success,
)
from deeplecture.presentation.api.shared.validation import validate_content_id, validate_filename, validate_language
from deeplecture.use_cases.dto.voiceover import GenerateVoiceoverRequest

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("voiceovers", __name__)

UTC = timezone.utc


@bp.route("/content/<content_id>/voiceovers", methods=["GET"])
@handle_errors
def list_voiceovers(content_id: str) -> Response:
    """List all voiceovers for a content item."""
    content_id = validate_content_id(content_id)

    container = get_container()
    voiceovers = container.voiceover_storage.list_all(content_id)

    return success({"voiceovers": voiceovers})


@bp.route("/content/<content_id>/voiceovers", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_voiceover(content_id: str) -> Response:
    """Generate voiceover for content (async task)."""
    from flask import request

    content_id = validate_content_id(content_id)
    data = request.get_json(silent=True) or {}

    voiceover_name = validate_filename(data.get("voiceover_name"), field_name="voiceover_name")

    if voiceover_name.lower().endswith((".m4a", ".wav", ".mp3", ".aac", ".opus")):
        voiceover_name = Path(voiceover_name).stem
    if not voiceover_name:
        return bad_request("voiceover_name is required")

    language = validate_language(data.get("language"), field_name="language", default="")
    if not language:
        return bad_request("language is required")

    # TTS model selection (optional, None = use default)
    tts_model = data.get("tts_model") or None

    container = get_container()

    video_path = container.artifact_storage.get_path(content_id, "video", fallback_kinds=["source"])
    if video_path is None:
        metadata = container.content_usecase.get_content(content_id)
        for candidate in (getattr(metadata, "video_file", None), getattr(metadata, "source_file", None)):
            if not candidate:
                continue
            p = Path(candidate).expanduser().resolve(strict=False)
            if p.is_file():
                video_path = str(p)
                break
    if video_path is None:
        return not_found("No video found for content")

    content_dir = container.path_resolver.get_content_dir(content_id)
    output_dir = os.path.join(content_dir, "voiceovers")

    gen_request = GenerateVoiceoverRequest(
        content_id=content_id,
        video_path=video_path,
        output_dir=output_dir,
        language=language,
        subtitle_language=language,
        audio_basename=voiceover_name,
        tts_model=tts_model,
    )

    # Register entry as "processing" BEFORE task submission
    voiceover_entry = {
        "id": voiceover_name,
        "name": voiceover_name,
        "language": language,
        "status": "processing",
    }
    container.voiceover_storage.add_entry(content_id, voiceover_entry)

    def _run_generation(ctx: object) -> dict:
        try:
            result = container.voiceover_usecase.generate(gen_request)
            # Update status to "done" on success
            container.voiceover_storage.update_status(content_id, voiceover_name, "done")
            return {
                "audio_path": result.audio_path,
                "timeline_path": result.timeline_path,
                "audio_duration": result.audio_duration,
                "video_duration": result.video_duration,
            }
        except Exception:
            # Update status to "error" on failure
            container.voiceover_storage.update_status(content_id, voiceover_name, "error")
            raise

    try:
        task_id = container.task_manager.submit(
            content_id=content_id,
            task_type="voiceover_generation",
            task=_run_generation,
            metadata={"voiceover_name": voiceover_name, "language": language},
        )
    except Exception:
        # Rollback: remove the entry if submit fails
        container.voiceover_storage.remove_entry(content_id, voiceover_name)
        raise

    return accepted(
        {
            "voiceover": {
                "id": voiceover_name,
                "name": voiceover_name,
                "language": language,
                "created_at": datetime.now(UTC).isoformat(),
                "status": "processing",
            },
            "message": "Voiceover generation started",
            "task_id": task_id,
        }
    )


@bp.route("/content/<content_id>/voiceovers/<voiceover_id>", methods=["DELETE"])
@handle_errors
def delete_voiceover(content_id: str, voiceover_id: str) -> Response:
    """Delete a voiceover and its associated files."""
    content_id = validate_content_id(content_id)
    voiceover_id = validate_filename(voiceover_id, field_name="voiceover_id")
    voiceover_id = Path(voiceover_id).stem

    container = get_container()
    content_dir = container.path_resolver.get_content_dir(content_id)
    voiceovers_dir = os.path.join(content_dir, "voiceovers")

    deleted = False
    file_storage = container.file_storage

    # Remove physical files
    audio_path = os.path.join(voiceovers_dir, f"{voiceover_id}.m4a")
    if os.path.isfile(audio_path):
        file_storage.remove_file(audio_path)
        deleted = True

    timeline_path = os.path.join(voiceovers_dir, f"{voiceover_id}_sync_timeline.json")
    if os.path.isfile(timeline_path):
        file_storage.remove_file(timeline_path)

    # Remove entry from voiceovers.json
    if container.voiceover_storage.remove_entry(content_id, voiceover_id):
        deleted = True

    return success({"deleted": deleted})


@bp.route("/content/<content_id>/voiceovers/<voiceover_id>", methods=["PATCH"])
@handle_errors
def update_voiceover(content_id: str, voiceover_id: str) -> Response:
    """Update voiceover metadata (name). Renaming only allowed when status is done."""
    from flask import request

    content_id = validate_content_id(content_id)
    voiceover_id = validate_filename(voiceover_id, field_name="voiceover_id")
    voiceover_id = Path(voiceover_id).stem

    data = request.get_json(silent=True) or {}

    new_name = data.get("name") or data.get("voiceover_name")
    if new_name is None:
        return bad_request("name is required")
    if not isinstance(new_name, str):
        return bad_request("name must be a string")

    new_name = validate_filename(new_name, field_name="name")
    if new_name.lower().endswith((".m4a", ".wav", ".mp3", ".aac", ".opus")):
        new_name = Path(new_name).stem
    new_id = Path(new_name).stem
    if not new_id or new_id in (".", ".."):
        return bad_request("name is invalid")

    container = get_container()
    voiceovers = container.voiceover_storage.list_all(content_id)
    current = next((v for v in voiceovers if v.get("id") == voiceover_id), None)
    if current is None:
        return not_found(f"Voiceover not found: {voiceover_id}")

    # No change needed
    if new_id == voiceover_id:
        return success({"voiceover": current})

    # Rename only allowed for completed voiceovers
    if str(current.get("status") or "").lower() != "done":
        return bad_request("Only completed voiceovers can be renamed")

    # Check for conflicts
    if any(v.get("id") == new_id for v in voiceovers):
        return bad_request(f"Voiceover already exists: {new_id}")

    content_dir = container.path_resolver.get_content_dir(content_id)
    voiceovers_dir = os.path.join(content_dir, "voiceovers")
    file_storage = container.file_storage

    old_audio = os.path.join(voiceovers_dir, f"{voiceover_id}.m4a")
    old_timeline = os.path.join(voiceovers_dir, f"{voiceover_id}_sync_timeline.json")
    new_audio = os.path.join(voiceovers_dir, f"{new_id}.m4a")
    new_timeline = os.path.join(voiceovers_dir, f"{new_id}_sync_timeline.json")

    if not os.path.isfile(old_audio):
        return not_found("Audio file not found")
    if os.path.exists(new_audio) or os.path.exists(new_timeline):
        return bad_request("Target filename already exists")

    # Rename files with rollback on failure
    try:
        file_storage.move_file(old_audio, new_audio)
        if os.path.isfile(old_timeline):
            try:
                file_storage.move_file(old_timeline, new_timeline)
            except Exception:
                file_storage.move_file(new_audio, old_audio)
                raise
    except Exception:
        return error("Failed to rename voiceover files", status=500)

    # Update entry in voiceovers.json
    container.voiceover_storage.remove_entry(content_id, voiceover_id)
    updated = dict(current)
    updated["id"] = new_id
    updated["name"] = new_id
    updated["updated_at"] = datetime.now(UTC).isoformat()
    container.voiceover_storage.add_entry(content_id, updated)

    refreshed = container.voiceover_storage.list_all(content_id)
    persisted = next((v for v in refreshed if v.get("id") == new_id), updated)

    return success({"voiceover": persisted})


@bp.route("/content/<content_id>/voiceovers/<voiceover_id>/audio", methods=["GET"])
@handle_errors
def get_voiceover_audio(content_id: str, voiceover_id: str) -> Response:
    """Serve the generated voiceover audio (m4a)."""
    content_id = validate_content_id(content_id)
    voiceover_id = validate_filename(voiceover_id, field_name="voiceover_id")
    voiceover_id = Path(voiceover_id).stem

    container = get_container()
    content_dir = Path(container.path_resolver.get_content_dir(content_id))
    audio_path = (content_dir / "voiceovers" / f"{voiceover_id}.m4a").resolve(strict=False)

    try:
        audio_path.relative_to(content_dir.resolve(strict=False))
    except ValueError:
        return not_found("Audio not found")

    if not audio_path.is_file():
        return not_found("Audio not found")

    return send_file(audio_path, mimetype="audio/mp4", conditional=True)


@bp.route("/content/<content_id>/voiceovers/<voiceover_id>/timeline", methods=["GET"])
@handle_errors
def get_voiceover_timeline(content_id: str, voiceover_id: str) -> Response:
    """Get sync timeline for a voiceover."""
    content_id = validate_content_id(content_id)
    voiceover_id = validate_filename(voiceover_id, field_name="voiceover_id")
    voiceover_id = Path(voiceover_id).stem

    container = get_container()
    content_dir = container.path_resolver.get_content_dir(content_id)
    voiceovers_dir = os.path.join(content_dir, "voiceovers")

    timeline_path = os.path.join(voiceovers_dir, f"{voiceover_id}_sync_timeline.json")

    if not os.path.isfile(timeline_path):
        return not_found(f"Timeline not found for voiceover: {voiceover_id}")

    try:
        with open(timeline_path, encoding="utf-8") as f:
            timeline_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return error("Failed to read timeline", status=500)

    return success(timeline_data)
