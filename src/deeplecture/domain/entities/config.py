"""Per-video configuration overrides (value object)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Literal

NoteContextMode = Literal["subtitle", "slide", "both"]
DictionaryInteractionMode = Literal["hover", "click"]
ViewMode = Literal["normal", "widescreen", "web-fullscreen", "fullscreen"]


@dataclass(frozen=True)
class ContentConfig:
    """Sparse per-video configuration overrides.

    This is a value object: created, merged, and replaced but never mutated.
    None fields mean 'inherit from global/default'.
    """

    # --- AI / model ---
    source_language: str | None = None
    target_language: str | None = None
    llm_model: str | None = None
    tts_model: str | None = None
    prompts: dict[str, str] | None = None
    learner_profile: str | None = None
    note_context_mode: NoteContextMode | None = None

    # --- Playback ---
    auto_pause_on_leave: bool | None = None
    auto_resume_on_return: bool | None = None
    auto_switch_subtitles_on_leave: bool | None = None
    auto_switch_voiceover_on_leave: bool | None = None
    voiceover_auto_switch_threshold_ms: int | None = None
    summary_threshold_seconds: int | None = None
    subtitle_context_window_seconds: int | None = None
    subtitle_repeat_count: int | None = None

    # --- Subtitle display ---
    subtitle_font_size: int | None = None
    subtitle_bottom_offset: int | None = None

    # --- Notifications ---
    browser_notifications_enabled: bool | None = None
    toast_notifications_enabled: bool | None = None
    title_flash_enabled: bool | None = None

    # --- Live2D ---
    live2d_enabled: bool | None = None
    live2d_model_path: str | None = None
    live2d_model_position: dict | None = None  # {x: number, y: number}
    live2d_model_scale: float | None = None
    live2d_sync_with_video_audio: bool | None = None

    # --- Dictionary ---
    dictionary_enabled: bool | None = None
    dictionary_interaction_mode: DictionaryInteractionMode | None = None

    # --- View ---
    hide_sidebars: bool | None = None
    view_mode: ViewMode | None = None

    def to_sparse_dict(self) -> dict[str, Any]:
        """Return only non-None fields for JSON serialization."""
        return {f.name: getattr(self, f.name) for f in fields(self) if getattr(self, f.name) is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentConfig:
        """Create from sparse dict, ignoring unknown keys."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
