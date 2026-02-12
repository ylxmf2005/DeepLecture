"""Model resolution helpers for API routes."""

from __future__ import annotations

from deeplecture.domain.entities.config import ContentConfig


def resolve_models_for_task(
    *,
    container: object,
    content_id: str | None,
    task_key: str,
    llm_model: str | None,
    tts_model: str | None,
) -> tuple[str | None, str | None]:
    """Resolve llm/tts models for a task and validate model ids."""
    global_cfg = container.global_config_storage.load()  # type: ignore[attr-defined]
    if global_cfg is None:
        global_cfg = ContentConfig()

    content_cfg: ContentConfig | None = None
    if content_id:
        content_cfg = container.content_config_storage.load(content_id)  # type: ignore[attr-defined]

    resolved = container.task_model_resolver.resolve(  # type: ignore[attr-defined]
        task_key=task_key,
        requested_llm_model=llm_model,
        requested_tts_model=tts_model,
        content_config=content_cfg,
        global_config=global_cfg,
    )

    if resolved.llm_model:
        container.llm_provider.get(resolved.llm_model)  # type: ignore[attr-defined]
    if resolved.tts_model:
        container.tts_provider.get(resolved.tts_model)  # type: ignore[attr-defined]

    return resolved.llm_model, resolved.tts_model
