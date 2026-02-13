"""Global configuration routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import Blueprint, request

from deeplecture.di import get_container
from deeplecture.domain.entities.config import ContentConfig
from deeplecture.presentation.api.shared import handle_errors, success

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("global_config", __name__)


@bp.route("/global-config", methods=["GET"])
@handle_errors
def get_global_config() -> Response:
    container = get_container()
    cfg = container.global_config_storage.load()
    return success(cfg.to_sparse_dict() if cfg else {})


@bp.route("/global-config", methods=["PUT"])
@handle_errors
def put_global_config() -> Response:
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    container = get_container()

    existing_cfg = container.global_config_storage.load()
    merged_payload = _merge_sparse(existing_cfg.to_sparse_dict() if existing_cfg else {}, payload)
    cfg = ContentConfig.from_dict(merged_payload)

    llm_valid = {item.name for item in container.llm_provider.list_models()}
    tts_valid = {item.name for item in container.tts_provider.list_models()}

    for model_name in [cfg.llm_model, *(cfg.llm_task_models or {}).values()]:
        if model_name and model_name not in llm_valid:
            raise ValueError(f"Unknown LLM model in global config: {model_name}")
    for model_name in [cfg.tts_model, *(cfg.tts_task_models or {}).values()]:
        if model_name and model_name not in tts_valid:
            raise ValueError(f"Unknown TTS model in global config: {model_name}")

    container.global_config_storage.save(cfg)
    return success(cfg.to_sparse_dict())


@bp.route("/global-config", methods=["DELETE"])
@handle_errors
def delete_global_config() -> Response:
    container = get_container()
    container.global_config_storage.delete()
    return success({"deleted": True})


_REPLACE_DICT_PATHS = {
    ("ai", "prompts"),
    ("ai", "llm", "task_models"),
    ("ai", "llm", "taskModels"),
    ("ai", "tts", "task_models"),
    ("ai", "tts", "taskModels"),
}


def _merge_sparse(existing: dict[str, Any], incoming: dict[str, Any], path: tuple[str, ...] = ()) -> dict[str, Any]:
    """Merge sparse config patches into existing config.

    - Missing fields in incoming keep existing values.
    - Explicit null in incoming clears the field.
    - Some dictionary fields are replace-on-write (prompts/task_models).
    """
    out = dict(existing)

    for raw_key, value in incoming.items():
        key = str(raw_key)
        current_path = (*path, key)

        if value is None:
            out.pop(key, None)
            continue

        if isinstance(value, dict):
            if current_path in _REPLACE_DICT_PATHS:
                out[key] = value
                continue
            previous = out.get(key)
            if isinstance(previous, dict):
                out[key] = _merge_sparse(previous, value, current_path)
            else:
                out[key] = value
            continue

        out[key] = value

    return out
