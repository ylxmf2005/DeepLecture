"""Configuration routes - read-only access to application settings."""

from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Flask, jsonify

from deeplecture.api.error_utils import api_success
from deeplecture.app_context import AppContext, get_app_context
from deeplecture.config.config import get_settings

logger = logging.getLogger(__name__)


def _ctx() -> AppContext:
    ctx = get_app_context()
    ctx.ensure_initialized()
    return ctx


def _get_language_settings() -> Dict[str, str]:
    """Get language settings from configuration."""
    settings = get_settings()
    return {
        "original_language": settings.subtitle.source_language,
        "ai_language": settings.subtitle.timeline.output_language,
        "translated_language": settings.subtitle.translation.target_language,
    }


def _get_llm_models_settings() -> Dict[str, Any]:
    """Read LLM model settings from configuration."""
    registry = _ctx().llm_factory.get_registry()
    return {
        "models": registry.list_models(),
        "task_models": registry.get_task_models(),
        "default": registry.get_default_model_name(),
    }


def _get_tts_provider_settings() -> Dict[str, Any]:
    """Read TTS provider settings from configuration."""
    registry = _ctx().tts_factory.get_registry()
    return {
        "models": registry.list_providers(),
        "task_models": registry.get_task_models(),
        "default": registry.get_default_provider_name(),
    }


def register_config_routes(app: Flask) -> None:
    """Register configuration-related routes (read-only)."""

    # RESTful routes with /api/config prefix
    @app.route("/api/config/llm-models", methods=["GET"])
    def get_llm_models_config():
        """Get available LLM models and task mappings."""
        return api_success(_get_llm_models_settings())

    @app.route("/api/config/tts-models", methods=["GET"])
    def get_tts_models_config():
        """Get available TTS models and task mappings."""
        return api_success(_get_tts_provider_settings())

    @app.route("/api/config/languages", methods=["GET"])
    def get_language_settings_config():
        """Get current language settings."""
        return api_success(_get_language_settings())
