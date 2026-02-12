"""Configuration entities for global/per-content overrides."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _clean_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items()}


def _clean_str_mapping(value: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, raw in value.items():
        text = str(raw).strip() if raw is not None else ""
        if text:
            out[str(key)] = text
    return out


@dataclass(slots=True)
class ModelScopeConfig:
    """Model overrides for one provider type (llm or tts)."""

    default_model: str | None = None
    task_models: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ModelScopeConfig:
        if not isinstance(data, dict):
            return cls()
        default_raw = data.get("default_model")
        default_model = str(default_raw).strip() if default_raw else None
        return cls(
            default_model=default_model or None,
            task_models=_clean_str_mapping(data.get("task_models")),
        )

    def to_sparse_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.default_model:
            out["default_model"] = self.default_model
        if self.task_models:
            out["task_models"] = dict(self.task_models)
        return out


@dataclass(slots=True)
class AIConfig:
    """AI-related settings for runtime selection."""

    llm: ModelScopeConfig = field(default_factory=ModelScopeConfig)
    tts: ModelScopeConfig = field(default_factory=ModelScopeConfig)
    prompts: dict[str, str] = field(default_factory=dict)
    llm_model: str | None = None
    tts_model: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AIConfig:
        if not isinstance(data, dict):
            return cls()
        legacy_llm = data.get("llm_model")
        legacy_tts = data.get("tts_model")
        llm_model = str(legacy_llm).strip() if legacy_llm else None
        tts_model = str(legacy_tts).strip() if legacy_tts else None
        return cls(
            llm=ModelScopeConfig.from_dict(data.get("llm")),
            tts=ModelScopeConfig.from_dict(data.get("tts")),
            prompts=_clean_str_mapping(data.get("prompts")),
            llm_model=llm_model or None,
            tts_model=tts_model or None,
        )

    def to_sparse_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        llm_data = self.llm.to_sparse_dict()
        tts_data = self.tts.to_sparse_dict()
        if llm_data:
            out["llm"] = llm_data
        if tts_data:
            out["tts"] = tts_data
        if self.prompts:
            out["prompts"] = dict(self.prompts)
        if self.llm_model:
            out["llm_model"] = self.llm_model
        if self.tts_model:
            out["tts_model"] = self.tts_model
        return out

    def get_llm_task_model(self, task_key: str) -> str | None:
        return self.llm.task_models.get(task_key) or self.llm.default_model or self.llm_model

    def get_tts_task_model(self, task_key: str) -> str | None:
        return self.tts.task_models.get(task_key) or self.tts.default_model or self.tts_model


@dataclass(slots=True)
class ContentConfig:
    """Unified config payload for global defaults and per-content overrides."""

    playback: dict[str, Any] = field(default_factory=dict)
    language: dict[str, Any] = field(default_factory=dict)
    hide_sidebars: bool | None = None
    view_mode: str | None = None
    subtitle_display: dict[str, Any] = field(default_factory=dict)
    notifications: dict[str, Any] = field(default_factory=dict)
    live2d: dict[str, Any] = field(default_factory=dict)
    learner_profile: str | None = None
    note: dict[str, Any] = field(default_factory=dict)
    ai: AIConfig = field(default_factory=AIConfig)
    dictionary: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ContentConfig:
        if not isinstance(data, dict):
            return cls()
        ai_data = data.get("ai")
        if not isinstance(ai_data, dict):
            ai_data = {
                "llm_model": data.get("llm_model"),
                "tts_model": data.get("tts_model"),
                "prompts": data.get("prompts"),
            }
        note_data = _clean_mapping(data.get("note"))
        if "note_context_mode" in data and "context_mode" not in note_data:
            note_data["context_mode"] = data.get("note_context_mode")

        learner_raw = data.get("learner_profile")
        learner_profile = str(learner_raw) if isinstance(learner_raw, str) else None

        view_mode_raw = data.get("view_mode")
        view_mode = str(view_mode_raw).strip() if view_mode_raw else None

        return cls(
            playback=_clean_mapping(data.get("playback")),
            language=_clean_mapping(data.get("language")),
            hide_sidebars=data.get("hide_sidebars") if isinstance(data.get("hide_sidebars"), bool) else None,
            view_mode=view_mode or None,
            subtitle_display=_clean_mapping(data.get("subtitle_display")),
            notifications=_clean_mapping(data.get("notifications")),
            live2d=_clean_mapping(data.get("live2d")),
            learner_profile=learner_profile,
            note=note_data,
            ai=AIConfig.from_dict(ai_data),
            dictionary=_clean_mapping(data.get("dictionary")),
        )

    def to_sparse_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.playback:
            out["playback"] = dict(self.playback)
        if self.language:
            out["language"] = dict(self.language)
        if self.hide_sidebars is not None:
            out["hide_sidebars"] = self.hide_sidebars
        if self.view_mode:
            out["view_mode"] = self.view_mode
        if self.subtitle_display:
            out["subtitle_display"] = dict(self.subtitle_display)
        if self.notifications:
            out["notifications"] = dict(self.notifications)
        if self.live2d:
            out["live2d"] = dict(self.live2d)
        if self.learner_profile is not None:
            out["learner_profile"] = self.learner_profile
        if self.note:
            out["note"] = dict(self.note)
        ai_data = self.ai.to_sparse_dict()
        if ai_data:
            out["ai"] = ai_data
        if self.dictionary:
            out["dictionary"] = dict(self.dictionary)
        return out

    def to_dict(self) -> dict[str, Any]:
        return self.to_sparse_dict()
