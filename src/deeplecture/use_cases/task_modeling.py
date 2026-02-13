"""Task/model mapping and runtime model resolution utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.domain.entities.config import ContentConfig

# Tasks that support per-task LLM model selection
LLM_TASK_KEYS: tuple[str, ...] = (
    "subtitle_translation",
    "timeline_generation",
    "video_generation",
    "note_generation",
    "quiz_generation",
    "cheatsheet_generation",
    "slide_explanation",
    "ask_video",
)

# Tasks that support per-task TTS model selection
TTS_TASK_KEYS: tuple[str, ...] = (
    "video_generation",
    "voiceover_generation",
)

# Canonical task keys exposed to frontend settings UI
TASK_KEYS: tuple[str, ...] = tuple(dict.fromkeys((*LLM_TASK_KEYS, *TTS_TASK_KEYS)))

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
            self._resolve_llm_from_config(content_config, key),
            self._resolve_llm_from_config(global_config, key),
            self._yaml_llm.get(key),
            self._yaml_llm.get("default"),
        )
        tts_model = self._first_non_empty(
            requested_tts_model,
            self._resolve_tts_from_config(content_config, key),
            self._resolve_tts_from_config(global_config, key),
            self._yaml_tts.get(key),
            self._yaml_tts.get("default"),
        )
        return ResolvedModels(llm_model=llm_model, tts_model=tts_model)

    @classmethod
    def _resolve_llm_from_config(cls, config: ContentConfig | None, task_key: str) -> str | None:
        if config is None:
            return None
        return cls._first_non_empty(
            cls._task_map_value(config.llm_task_models, task_key),
            config.llm_model,
        )

    @classmethod
    def _resolve_tts_from_config(cls, config: ContentConfig | None, task_key: str) -> str | None:
        if config is None:
            return None
        return cls._first_non_empty(
            cls._task_map_value(config.tts_task_models, task_key),
            config.tts_model,
        )

    @staticmethod
    def _task_map_value(task_map: dict[str, str] | None, task_key: str) -> str | None:
        if not task_map:
            return None

        direct = task_map.get(task_key)
        if direct and str(direct).strip():
            return str(direct).strip()

        # Backward compatibility: stored keys may be legacy aliases.
        for raw_key, value in task_map.items():
            if normalize_task_key(raw_key) != task_key:
                continue
            if value and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _first_non_empty(*values: str | None) -> str | None:
        for value in values:
            if value and str(value).strip():
                return str(value).strip()
        return None
