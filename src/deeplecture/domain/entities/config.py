"""Per-video/global configuration overrides (value object)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

NoteContextMode = Literal["subtitle", "slide", "both"]
DictionaryInteractionMode = Literal["hover", "click"]
ViewMode = Literal["normal", "widescreen", "web-fullscreen", "fullscreen"]


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_task_map(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, str] = {}
    for key, raw in value.items():
        text = _clean_str(raw)
        if text:
            out[str(key)] = text
    return out or None


@dataclass(frozen=True)
class ContentConfig:
    """Sparse configuration overrides.

    None fields mean 'inherit from global/default'.
    Supports both flat legacy keys and nested frontend-style keys.
    """

    source_language: str | None = None
    target_language: str | None = None
    llm_model: str | None = None
    tts_model: str | None = None
    llm_task_models: dict[str, str] | None = None
    tts_task_models: dict[str, str] | None = None
    prompts: dict[str, str] | None = None
    learner_profile: str | None = None
    note_context_mode: NoteContextMode | None = None

    auto_pause_on_leave: bool | None = None
    auto_resume_on_return: bool | None = None
    auto_switch_subtitles_on_leave: bool | None = None
    auto_switch_voiceover_on_leave: bool | None = None
    voiceover_auto_switch_threshold_ms: int | None = None
    summary_threshold_seconds: int | None = None
    subtitle_context_window_seconds: int | None = None
    subtitle_repeat_count: int | None = None

    subtitle_font_size: int | None = None
    subtitle_bottom_offset: int | None = None

    browser_notifications_enabled: bool | None = None
    toast_notifications_enabled: bool | None = None
    title_flash_enabled: bool | None = None

    live2d_enabled: bool | None = None
    live2d_model_path: str | None = None
    live2d_model_position: dict[str, Any] | None = None
    live2d_model_scale: float | None = None
    live2d_sync_with_video_audio: bool | None = None

    dictionary_enabled: bool | None = None
    dictionary_interaction_mode: DictionaryInteractionMode | None = None

    hide_sidebars: bool | None = None
    view_mode: ViewMode | None = None

    def get_llm_task_model(self, task_key: str) -> str | None:
        if self.llm_task_models and self.llm_task_models.get(task_key):
            return self.llm_task_models[task_key]
        return self.llm_model

    def get_tts_task_model(self, task_key: str) -> str | None:
        if self.tts_task_models and self.tts_task_models.get(task_key):
            return self.tts_task_models[task_key]
        return self.tts_model

    def to_sparse_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}

        playback: dict[str, Any] = {}
        if self.auto_pause_on_leave is not None:
            playback["auto_pause_on_leave"] = self.auto_pause_on_leave
        if self.auto_resume_on_return is not None:
            playback["auto_resume_on_return"] = self.auto_resume_on_return
        if self.auto_switch_subtitles_on_leave is not None:
            playback["auto_switch_subtitles_on_leave"] = self.auto_switch_subtitles_on_leave
        if self.auto_switch_voiceover_on_leave is not None:
            playback["auto_switch_voiceover_on_leave"] = self.auto_switch_voiceover_on_leave
        if self.voiceover_auto_switch_threshold_ms is not None:
            playback["voiceover_auto_switch_threshold_ms"] = self.voiceover_auto_switch_threshold_ms
        if self.summary_threshold_seconds is not None:
            playback["summary_threshold_seconds"] = self.summary_threshold_seconds
        if self.subtitle_context_window_seconds is not None:
            playback["subtitle_context_window_seconds"] = self.subtitle_context_window_seconds
        if self.subtitle_repeat_count is not None:
            playback["subtitle_repeat_count"] = self.subtitle_repeat_count
        if playback:
            out["playback"] = playback

        language: dict[str, Any] = {}
        if self.source_language is not None:
            language["original"] = self.source_language
        if self.target_language is not None:
            language["translated"] = self.target_language
        if language:
            out["language"] = language

        subtitle_display: dict[str, Any] = {}
        if self.subtitle_font_size is not None:
            subtitle_display["font_size"] = self.subtitle_font_size
        if self.subtitle_bottom_offset is not None:
            subtitle_display["bottom_offset"] = self.subtitle_bottom_offset
        if subtitle_display:
            out["subtitle_display"] = subtitle_display

        notifications: dict[str, Any] = {}
        if self.browser_notifications_enabled is not None:
            notifications["browser_notifications_enabled"] = self.browser_notifications_enabled
        if self.toast_notifications_enabled is not None:
            notifications["toast_notifications_enabled"] = self.toast_notifications_enabled
        if self.title_flash_enabled is not None:
            notifications["title_flash_enabled"] = self.title_flash_enabled
        if notifications:
            out["notifications"] = notifications

        live2d: dict[str, Any] = {}
        if self.live2d_enabled is not None:
            live2d["enabled"] = self.live2d_enabled
        if self.live2d_model_path is not None:
            live2d["model_path"] = self.live2d_model_path
        if self.live2d_model_position is not None:
            live2d["model_position"] = self.live2d_model_position
        if self.live2d_model_scale is not None:
            live2d["model_scale"] = self.live2d_model_scale
        if self.live2d_sync_with_video_audio is not None:
            live2d["sync_with_video_audio"] = self.live2d_sync_with_video_audio
        if live2d:
            out["live2d"] = live2d

        dictionary: dict[str, Any] = {}
        if self.dictionary_enabled is not None:
            dictionary["enabled"] = self.dictionary_enabled
        if self.dictionary_interaction_mode is not None:
            dictionary["interaction_mode"] = self.dictionary_interaction_mode
        if dictionary:
            out["dictionary"] = dictionary

        if self.hide_sidebars is not None:
            out["hide_sidebars"] = self.hide_sidebars
        if self.view_mode is not None:
            out["view_mode"] = self.view_mode
        if self.learner_profile is not None:
            out["learner_profile"] = self.learner_profile
        if self.note_context_mode is not None:
            out["note"] = {"context_mode": self.note_context_mode}

        ai: dict[str, Any] = {}
        if self.llm_model is not None:
            ai["llm_model"] = self.llm_model
        if self.tts_model is not None:
            ai["tts_model"] = self.tts_model
        if self.prompts:
            ai["prompts"] = self.prompts
        llm_scope: dict[str, Any] = {}
        if self.llm_model is not None:
            llm_scope["default_model"] = self.llm_model
        if self.llm_task_models:
            llm_scope["task_models"] = self.llm_task_models
        if llm_scope:
            ai["llm"] = llm_scope
        tts_scope: dict[str, Any] = {}
        if self.tts_model is not None:
            tts_scope["default_model"] = self.tts_model
        if self.tts_task_models:
            tts_scope["task_models"] = self.tts_task_models
        if tts_scope:
            ai["tts"] = tts_scope
        if ai:
            out["ai"] = ai

        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentConfig:
        if not isinstance(data, dict):
            return cls()

        ai = data.get("ai") if isinstance(data.get("ai"), dict) else {}
        llm_scope = ai.get("llm") if isinstance(ai.get("llm"), dict) else {}
        tts_scope = ai.get("tts") if isinstance(ai.get("tts"), dict) else {}
        language = data.get("language") if isinstance(data.get("language"), dict) else {}
        playback = data.get("playback") if isinstance(data.get("playback"), dict) else {}
        subtitle_display = data.get("subtitle_display") if isinstance(data.get("subtitle_display"), dict) else {}
        notifications = data.get("notifications") if isinstance(data.get("notifications"), dict) else {}
        live2d = data.get("live2d") if isinstance(data.get("live2d"), dict) else {}
        dictionary = data.get("dictionary") if isinstance(data.get("dictionary"), dict) else {}
        note = data.get("note") if isinstance(data.get("note"), dict) else {}

        llm_model = (
            _clean_str(ai.get("llm_model"))
            or _clean_str(ai.get("llmModel"))
            or _clean_str(llm_scope.get("default_model"))
            or _clean_str(llm_scope.get("defaultModel"))
            or _clean_str(data.get("llm_model"))
            or _clean_str(data.get("llmModel"))
        )
        tts_model = (
            _clean_str(ai.get("tts_model"))
            or _clean_str(ai.get("ttsModel"))
            or _clean_str(tts_scope.get("default_model"))
            or _clean_str(tts_scope.get("defaultModel"))
            or _clean_str(data.get("tts_model"))
            or _clean_str(data.get("ttsModel"))
        )

        llm_task_models = _clean_task_map(llm_scope.get("task_models")) or _clean_task_map(llm_scope.get("taskModels"))
        tts_task_models = _clean_task_map(tts_scope.get("task_models")) or _clean_task_map(tts_scope.get("taskModels"))

        prompts = ai.get("prompts") if isinstance(ai.get("prompts"), dict) else data.get("prompts")
        prompts = {str(k): str(v) for k, v in prompts.items() if _clean_str(v)} if isinstance(prompts, dict) else None

        return cls(
            source_language=_clean_str(language.get("original")) or _clean_str(data.get("source_language")),
            target_language=_clean_str(language.get("translated")) or _clean_str(data.get("target_language")),
            llm_model=llm_model,
            tts_model=tts_model,
            llm_task_models=llm_task_models,
            tts_task_models=tts_task_models,
            prompts=prompts,
            learner_profile=_clean_str(data.get("learner_profile")),
            note_context_mode=(note.get("context_mode") or data.get("note_context_mode")),
            auto_pause_on_leave=playback.get("auto_pause_on_leave", data.get("auto_pause_on_leave")),
            auto_resume_on_return=playback.get("auto_resume_on_return", data.get("auto_resume_on_return")),
            auto_switch_subtitles_on_leave=playback.get(
                "auto_switch_subtitles_on_leave", data.get("auto_switch_subtitles_on_leave")
            ),
            auto_switch_voiceover_on_leave=playback.get(
                "auto_switch_voiceover_on_leave", data.get("auto_switch_voiceover_on_leave")
            ),
            voiceover_auto_switch_threshold_ms=playback.get(
                "voiceover_auto_switch_threshold_ms", data.get("voiceover_auto_switch_threshold_ms")
            ),
            summary_threshold_seconds=playback.get("summary_threshold_seconds", data.get("summary_threshold_seconds")),
            subtitle_context_window_seconds=playback.get(
                "subtitle_context_window_seconds", data.get("subtitle_context_window_seconds")
            ),
            subtitle_repeat_count=playback.get("subtitle_repeat_count", data.get("subtitle_repeat_count")),
            subtitle_font_size=subtitle_display.get("font_size", data.get("subtitle_font_size")),
            subtitle_bottom_offset=subtitle_display.get("bottom_offset", data.get("subtitle_bottom_offset")),
            browser_notifications_enabled=notifications.get(
                "browser_notifications_enabled", data.get("browser_notifications_enabled")
            ),
            toast_notifications_enabled=notifications.get(
                "toast_notifications_enabled", data.get("toast_notifications_enabled")
            ),
            title_flash_enabled=notifications.get("title_flash_enabled", data.get("title_flash_enabled")),
            live2d_enabled=live2d.get("enabled", data.get("live2d_enabled")),
            live2d_model_path=_clean_str(live2d.get("model_path")) or _clean_str(data.get("live2d_model_path")),
            live2d_model_position=live2d.get("model_position", data.get("live2d_model_position")),
            live2d_model_scale=live2d.get("model_scale", data.get("live2d_model_scale")),
            live2d_sync_with_video_audio=live2d.get("sync_with_video_audio", data.get("live2d_sync_with_video_audio")),
            dictionary_enabled=dictionary.get("enabled", data.get("dictionary_enabled")),
            dictionary_interaction_mode=dictionary.get("interaction_mode", data.get("dictionary_interaction_mode")),
            hide_sidebars=data.get("hide_sidebars"),
            view_mode=data.get("view_mode"),
        )
