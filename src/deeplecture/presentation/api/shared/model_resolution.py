"""Model resolution helpers for API routes."""

from __future__ import annotations

import logging

from deeplecture.domain.entities.config import ContentConfig

logger = logging.getLogger(__name__)


def _normalize_model_name(model_name: str | None) -> str | None:
    if model_name is None:
        return None
    normalized = str(model_name).strip()
    return normalized or None


def _is_unknown_model_error(exc: ValueError, *, kind: str) -> bool:
    return str(exc).startswith(f"Unknown {kind} model:")


def _validate_or_fallback_model(
    *,
    provider: object,
    model_name: str | None,
    requested_model: str | None,
    task_key: str,
    kind: str,
) -> str | None:
    if not model_name:
        return None

    try:
        provider.get(model_name)  # type: ignore[attr-defined]
        return model_name
    except ValueError as exc:
        # Keep explicit request errors strict; only stale persisted config should auto-fallback.
        if requested_model and model_name == requested_model:
            raise
        if not _is_unknown_model_error(exc, kind=kind):
            raise

        logger.warning(
            "Unknown %s model %r resolved for task %s; falling back to provider default",
            kind,
            model_name,
            task_key,
        )
        provider.get()  # type: ignore[attr-defined]
        return None


def resolve_models_for_task(
    *,
    container: object,
    content_id: str | None,
    task_key: str,
    llm_model: str | None,
    tts_model: str | None,
) -> tuple[str | None, str | None]:
    """Resolve llm/tts models for a task and validate model ids."""
    requested_llm_model = _normalize_model_name(llm_model)
    requested_tts_model = _normalize_model_name(tts_model)

    global_cfg = container.global_config_storage.load()  # type: ignore[attr-defined]
    if global_cfg is None:
        global_cfg = ContentConfig()

    content_cfg: ContentConfig | None = None
    if content_id:
        content_cfg = container.content_config_storage.load(content_id)  # type: ignore[attr-defined]

    resolved = container.task_model_resolver.resolve(  # type: ignore[attr-defined]
        task_key=task_key,
        requested_llm_model=requested_llm_model,
        requested_tts_model=requested_tts_model,
        content_config=content_cfg,
        global_config=global_cfg,
    )

    resolved_llm_model = _validate_or_fallback_model(
        provider=container.llm_provider,  # type: ignore[attr-defined]
        model_name=resolved.llm_model,
        requested_model=requested_llm_model,
        task_key=task_key,
        kind="LLM",
    )
    resolved_tts_model = _validate_or_fallback_model(
        provider=container.tts_provider,  # type: ignore[attr-defined]
        model_name=resolved.tts_model,
        requested_model=requested_tts_model,
        task_key=task_key,
        kind="TTS",
    )

    return resolved_llm_model, resolved_tts_model
