"""Task/model mapping and runtime model resolution utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.domain.entities.config import ContentConfig

# Canonical task keys used by backend routing/use cases
TASK_KEYS: tuple[str, ...] = (
    "subtitle_translation",
    "timeline_generation",
    "video_generation",
    "voiceover_generation",
    "note_generation",
    "quiz_generation",
    "cheatsheet_generation",
    "slide_explanation",
    "ask_video",
)

TASK_KEY_ALIASES: dict[str, str] = {
    "slide_lecture": "video_generation",
    "voiceover": "voiceover_generation",
    "subtitle_timeline": "timeline_generation",
    "subtitle_enhancement": "subtitle_translation",
}


def normalize_task_key(task_key: str) -> str:
    """Normalize legacy/alias task key to canonical key."""
    key = (task_key or "").strip()
    if not key:
        return key
    return TASK_KEY_ALIASES.get(key, key)


@dataclass(slots=True)
class ResolvedModels:
    """Resolved models for one task execution."""

    llm_model: str | None
    tts_model: str | None


class TaskModelResolver:
    """Resolves task-specific llm/tts models with priority layers."""

    def __init__(self, *, yaml_llm_task_models: dict[str, str], yaml_tts_task_models: dict[str, str]) -> None:
        self._yaml_llm = {normalize_task_key(k): v for k, v in yaml_llm_task_models.items() if v}
        self._yaml_tts = {normalize_task_key(k): v for k, v in yaml_tts_task_models.items() if v}

    def resolve(
        self,
        *,
        task_key: str,
        requested_llm_model: str | None,
        requested_tts_model: str | None,
        content_config: ContentConfig | None,
        global_config: ContentConfig | None,
    ) -> ResolvedModels:
        """Resolve models by priority.

        Priority: explicit request > per-content config > global config > yaml task models > None
        """
        key = normalize_task_key(task_key)

        llm_model = self._first_non_empty(
            requested_llm_model,
            content_config.ai.get_llm_task_model(key) if content_config else None,
            global_config.ai.get_llm_task_model(key) if global_config else None,
            self._yaml_llm.get(key),
            self._yaml_llm.get("default"),
        )
        tts_model = self._first_non_empty(
            requested_tts_model,
            content_config.ai.get_tts_task_model(key) if content_config else None,
            global_config.ai.get_tts_task_model(key) if global_config else None,
            self._yaml_tts.get(key),
            self._yaml_tts.get("default"),
        )
        return ResolvedModels(llm_model=llm_model, tts_model=tts_model)

    @staticmethod
    def _first_non_empty(*values: str | None) -> str | None:
        for value in values:
            if value and str(value).strip():
                return str(value).strip()
        return None
