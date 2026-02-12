"""Global configuration routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    cfg = ContentConfig.from_dict(payload)
    container = get_container()

    llm_valid = {item.name for item in container.llm_provider.list_models()}
    tts_valid = {item.name for item in container.tts_provider.list_models()}

    for model_name in [cfg.ai.llm.default_model, cfg.ai.llm_model, *cfg.ai.llm.task_models.values()]:
        if model_name and model_name not in llm_valid:
            raise ValueError(f"Unknown LLM model in global config: {model_name}")
    for model_name in [cfg.ai.tts.default_model, cfg.ai.tts_model, *cfg.ai.tts.task_models.values()]:
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
