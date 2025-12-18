"""Config routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint

from deeplecture.config import get_settings
from deeplecture.di import get_container
from deeplecture.presentation.api.shared import handle_errors, success

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("config", __name__)


@bp.route("/config", methods=["GET"])
@handle_errors
def get_app_config() -> Response:
    """Get unified application configuration.

    Returns:
        - llm: Available LLM models and default
        - tts: Available TTS models and default
        - prompts: Available prompt implementations per function
    """
    container = get_container()
    llm_provider = container.llm_provider
    tts_provider = container.tts_provider
    prompt_registry = container.prompt_registry

    # LLM models (name is the unique identifier)
    llm_models = [{"id": m.name, "name": m.name, "provider": m.provider} for m in llm_provider.list_models()]
    llm_default = llm_provider.get_default_model_name()

    # TTS models (name is the unique identifier)
    tts_models = [{"id": m.name, "name": m.name, "provider": m.provider} for m in tts_provider.list_models()]
    tts_default = tts_provider.get_default_model_name()

    # Prompts
    prompts_data: dict[str, dict] = {}
    for func_id in prompt_registry.list_func_ids():
        implementations = prompt_registry.list_implementations(func_id)
        default_impl = prompt_registry.get_default_impl_id(func_id)
        prompts_data[func_id] = {
            "options": [
                {
                    "id": impl.impl_id,
                    "name": impl.name,
                    "description": impl.description,
                    "isDefault": impl.is_default,
                }
                for impl in implementations
            ],
            "defaultImplId": default_impl,
        }

    return success(
        {
            "llm": {
                "models": llm_models,
                "defaultModel": llm_default,
            },
            "tts": {
                "models": tts_models,
                "defaultModel": tts_default,
            },
            "prompts": prompts_data,
        }
    )


@bp.route("/languages", methods=["GET"])
@handle_errors
def get_languages() -> Response:
    """Get available language options."""
    languages = [
        {"value": "en", "label": "English"},
        {"value": "zh", "label": "Chinese"},
        {"value": "ja", "label": "日本語"},
        {"value": "ko", "label": "한국어"},
        {"value": "es", "label": "Español"},
        {"value": "fr", "label": "Français"},
        {"value": "de", "label": "Deutsch"},
    ]

    return success({"languages": languages})


@bp.route("/note-defaults", methods=["GET"])
@handle_errors
def get_note_defaults() -> Response:
    """Get default note generation settings."""
    settings = get_settings()
    note_config = settings.note

    return success(
        {
            "default_context_mode": note_config.default_context_mode,
        }
    )
