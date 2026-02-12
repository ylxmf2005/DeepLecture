"""Per-video configuration CRUD routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.domain.entities.config import ContentConfig
from deeplecture.presentation.api.shared import bad_request, handle_errors, success
from deeplecture.presentation.api.shared.validation import validate_content_id

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("content_config", __name__)

_VALID_CONTEXT_MODES = {"subtitle", "slide", "both"}
_VALID_VIEW_MODES = {"normal", "widescreen", "web-fullscreen", "fullscreen"}
_VALID_DICTIONARY_INTERACTION_MODES = {"hover", "click"}
_MAX_LEARNER_PROFILE_LENGTH = 2000
_MAX_MODEL_NAME_LENGTH = 128
_MAX_PATH_LENGTH = 512

# ---------------------------------------------------------------------------
# Declarative validation tables
# ---------------------------------------------------------------------------

_BOOL_FIELDS: tuple[str, ...] = (
    "auto_pause_on_leave",
    "auto_resume_on_return",
    "auto_switch_subtitles_on_leave",
    "auto_switch_voiceover_on_leave",
    "browser_notifications_enabled",
    "toast_notifications_enabled",
    "title_flash_enabled",
    "live2d_enabled",
    "live2d_sync_with_video_audio",
    "dictionary_enabled",
    "hide_sidebars",
)

_INT_RANGE_FIELDS: dict[str, tuple[int, int]] = {
    "voiceover_auto_switch_threshold_ms": (0, 60_000),
    "summary_threshold_seconds": (0, 3600),
    "subtitle_context_window_seconds": (0, 300),
    "subtitle_repeat_count": (1, 10),
    "subtitle_font_size": (8, 72),
    "subtitle_bottom_offset": (0, 500),
}

_ENUM_FIELDS: dict[str, set[str]] = {
    "note_context_mode": _VALID_CONTEXT_MODES,
    "view_mode": _VALID_VIEW_MODES,
    "dictionary_interaction_mode": _VALID_DICTIONARY_INTERACTION_MODES,
}


@bp.route("/<content_id>/config", methods=["GET"])
@handle_errors
def get_config(content_id: str) -> Response:
    """Return sparse per-video config (only overrides)."""
    content_id = validate_content_id(content_id)
    container = get_container()
    config = container.content_config_storage.load(content_id)
    if config is None:
        return success({})
    return success(config.to_sparse_dict())


@bp.route("/<content_id>/config", methods=["PUT"])
@handle_errors
def put_config(content_id: str) -> Response:
    """Replace sparse per-video config (full replacement)."""
    content_id = validate_content_id(content_id)
    data = request.get_json(silent=True) or {}

    error_msg = _validate_config_fields(data)
    if error_msg:
        return bad_request(error_msg)

    config = ContentConfig.from_dict(data)
    container = get_container()
    container.content_config_storage.save(content_id, config)
    return success(config.to_sparse_dict())


@bp.route("/<content_id>/config", methods=["DELETE"])
@handle_errors
def delete_config(content_id: str) -> Response:
    """Remove all per-video overrides."""
    content_id = validate_content_id(content_id)
    container = get_container()
    container.content_config_storage.delete(content_id)
    return success({})


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_bool(data: dict, field: str) -> str | None:
    value = data.get(field)
    if value is not None and not isinstance(value, bool):
        return f"{field} must be a boolean"
    return None


def _validate_int_range(data: dict, field: str, lo: int, hi: int) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        return f"{field} must be an integer"
    if value < lo or value > hi:
        return f"{field} must be between {lo} and {hi}"
    return None


def _validate_enum(data: dict, field: str, allowed: set[str]) -> str | None:
    value = data.get(field)
    if value is not None and value not in allowed:
        return f"{field} must be one of: {', '.join(sorted(allowed))}"
    return None


def _validate_live2d_model_position(data: dict) -> str | None:
    pos = data.get("live2d_model_position")
    if pos is None:
        return None
    if not isinstance(pos, dict):
        return "live2d_model_position must be a JSON object with numeric x and y"
    if "x" not in pos or "y" not in pos:
        return "live2d_model_position must contain x and y"
    if not isinstance(pos["x"], int | float) or not isinstance(pos["y"], int | float):
        return "live2d_model_position x and y must be numbers"
    return None


def _validate_live2d_model_scale(data: dict) -> str | None:
    value = data.get("live2d_model_scale")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "live2d_model_scale must be a number"
    if value < 0.1 or value > 5.0:
        return "live2d_model_scale must be between 0.1 and 5.0"
    return None


def _validate_config_fields(data: dict[str, Any]) -> str | None:
    """Validate config field values. Returns error message or None."""
    if not isinstance(data, dict):
        return "Request body must be a JSON object"

    # --- Boolean fields (table-driven) ---
    for field in _BOOL_FIELDS:
        if err := _validate_bool(data, field):
            return err

    # --- Integer fields with range (table-driven) ---
    for field, (lo, hi) in _INT_RANGE_FIELDS.items():
        if err := _validate_int_range(data, field, lo, hi):
            return err

    # --- Enum string fields (table-driven) ---
    for field, allowed in _ENUM_FIELDS.items():
        if err := _validate_enum(data, field, allowed):
            return err

    # --- Model name strings ---
    for field in ("llm_model", "tts_model"):
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            return f"{field} must be a string or null"
        if isinstance(value, str) and len(value) > _MAX_MODEL_NAME_LENGTH:
            return f"{field} exceeds maximum length ({_MAX_MODEL_NAME_LENGTH})"

    # --- Language strings ---
    for field in ("source_language", "target_language"):
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            return f"{field} must be a string"

    # --- Prompts ---
    prompts = data.get("prompts")
    if prompts is not None:
        if not isinstance(prompts, dict):
            return "prompts must be a JSON object"
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in prompts.items()):
            return "prompts must be a mapping of string keys to string values"

    # --- Learner profile ---
    learner_profile = data.get("learner_profile")
    if learner_profile is not None:
        if not isinstance(learner_profile, str):
            return "learner_profile must be a string"
        if len(learner_profile) > _MAX_LEARNER_PROFILE_LENGTH:
            return f"learner_profile exceeds maximum length ({_MAX_LEARNER_PROFILE_LENGTH})"

    # --- Live2D model path ---
    live2d_model_path = data.get("live2d_model_path")
    if live2d_model_path is not None:
        if not isinstance(live2d_model_path, str):
            return "live2d_model_path must be a string"
        if len(live2d_model_path) > _MAX_PATH_LENGTH:
            return f"live2d_model_path exceeds maximum length ({_MAX_PATH_LENGTH})"

    # --- Live2D model position ---
    if err := _validate_live2d_model_position(data):
        return err

    # --- Live2D model scale ---
    if err := _validate_live2d_model_scale(data):
        return err

    return None
