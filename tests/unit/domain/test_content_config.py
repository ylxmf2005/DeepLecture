"""Unit tests for ContentConfig domain entity."""

import pytest

from deeplecture.domain.entities.config import ContentConfig


class TestContentConfig:
    """Tests for ContentConfig value object."""

    @pytest.mark.unit
    def test_to_sparse_dict_excludes_none(self) -> None:
        """to_sparse_dict should exclude None fields."""
        config = ContentConfig(source_language="ja", llm_model="claude-3-5-sonnet")
        result = config.to_sparse_dict()
        assert result == {"source_language": "ja", "llm_model": "claude-3-5-sonnet"}

    @pytest.mark.unit
    def test_to_sparse_dict_empty(self) -> None:
        """to_sparse_dict on empty config returns empty dict."""
        config = ContentConfig()
        assert config.to_sparse_dict() == {}

    @pytest.mark.unit
    def test_to_sparse_dict_includes_prompts(self) -> None:
        """to_sparse_dict should include prompts when set."""
        config = ContentConfig(prompts={"timeline_segmentation": "concise_v2"})
        result = config.to_sparse_dict()
        assert result == {"prompts": {"timeline_segmentation": "concise_v2"}}

    @pytest.mark.unit
    def test_from_dict_basic(self) -> None:
        """from_dict should create config from sparse dict."""
        config = ContentConfig.from_dict({"source_language": "en", "llm_model": "gpt-4o"})
        assert config.source_language == "en"
        assert config.llm_model == "gpt-4o"
        assert config.target_language is None

    @pytest.mark.unit
    def test_from_dict_ignores_unknown_keys(self) -> None:
        """from_dict should silently ignore unknown keys."""
        config = ContentConfig.from_dict(
            {
                "source_language": "en",
                "unknown_key": "should_be_ignored",
                "another_unknown": 42,
            }
        )
        assert config.source_language == "en"
        assert config.to_sparse_dict() == {"source_language": "en"}

    @pytest.mark.unit
    def test_from_dict_empty(self) -> None:
        """from_dict with empty dict returns all-None config."""
        config = ContentConfig.from_dict({})
        assert config == ContentConfig()
        assert config.to_sparse_dict() == {}

    @pytest.mark.unit
    def test_from_dict_with_prompts(self) -> None:
        """from_dict should handle prompts dict."""
        config = ContentConfig.from_dict(
            {
                "prompts": {"quiz": "detailed_v1", "note": "concise_v2"},
            }
        )
        assert config.prompts == {"quiz": "detailed_v1", "note": "concise_v2"}

    @pytest.mark.unit
    def test_frozen(self) -> None:
        """ContentConfig should be immutable (frozen dataclass)."""
        config = ContentConfig(source_language="en")
        with pytest.raises(AttributeError):
            config.source_language = "ja"  # type: ignore[misc]

    @pytest.mark.unit
    def test_roundtrip(self) -> None:
        """to_sparse_dict -> from_dict should roundtrip."""
        original = ContentConfig(
            source_language="ja",
            target_language="en",
            llm_model="claude-3-5-sonnet",
            prompts={"timeline": "concise"},
            note_context_mode="slide",
        )
        sparse = original.to_sparse_dict()
        restored = ContentConfig.from_dict(sparse)
        assert restored == original

    @pytest.mark.unit
    def test_note_context_mode_literal(self) -> None:
        """note_context_mode should accept valid literal values."""
        for mode in ("subtitle", "slide", "both"):
            config = ContentConfig(note_context_mode=mode)  # type: ignore[arg-type]
            assert config.note_context_mode == mode

    @pytest.mark.unit
    def test_to_sparse_dict_preserves_empty_string(self) -> None:
        """to_sparse_dict includes empty strings (not None)."""
        config = ContentConfig(learner_profile="")
        result = config.to_sparse_dict()
        assert "learner_profile" in result
        assert result["learner_profile"] == ""

    # -----------------------------------------------------------------------
    # New fields: playback
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_playback_fields_sparse_dict(self) -> None:
        """Playback fields appear in to_sparse_dict when set."""
        config = ContentConfig(
            auto_pause_on_leave=True,
            auto_resume_on_return=False,
            voiceover_auto_switch_threshold_ms=5000,
            subtitle_repeat_count=3,
        )
        sparse = config.to_sparse_dict()
        assert sparse == {
            "auto_pause_on_leave": True,
            "auto_resume_on_return": False,
            "voiceover_auto_switch_threshold_ms": 5000,
            "subtitle_repeat_count": 3,
        }

    @pytest.mark.unit
    def test_playback_fields_from_dict(self) -> None:
        """Playback fields can be loaded via from_dict."""
        config = ContentConfig.from_dict(
            {
                "auto_switch_subtitles_on_leave": True,
                "auto_switch_voiceover_on_leave": False,
                "summary_threshold_seconds": 120,
                "subtitle_context_window_seconds": 30,
            }
        )
        assert config.auto_switch_subtitles_on_leave is True
        assert config.auto_switch_voiceover_on_leave is False
        assert config.summary_threshold_seconds == 120
        assert config.subtitle_context_window_seconds == 30

    # -----------------------------------------------------------------------
    # New fields: subtitle display
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_subtitle_display_fields(self) -> None:
        """Subtitle display fields roundtrip correctly."""
        original = ContentConfig(subtitle_font_size=20, subtitle_bottom_offset=50)
        sparse = original.to_sparse_dict()
        restored = ContentConfig.from_dict(sparse)
        assert restored == original
        assert restored.subtitle_font_size == 20
        assert restored.subtitle_bottom_offset == 50

    # -----------------------------------------------------------------------
    # New fields: notifications
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_notification_fields(self) -> None:
        """Notification boolean fields roundtrip correctly."""
        original = ContentConfig(
            browser_notifications_enabled=True,
            toast_notifications_enabled=False,
            title_flash_enabled=True,
        )
        sparse = original.to_sparse_dict()
        restored = ContentConfig.from_dict(sparse)
        assert restored == original

    # -----------------------------------------------------------------------
    # New fields: Live2D
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_live2d_fields(self) -> None:
        """Live2D fields roundtrip correctly."""
        original = ContentConfig(
            live2d_enabled=True,
            live2d_model_path="/models/haru.model3.json",
            live2d_model_position={"x": 100, "y": 200},
            live2d_model_scale=1.5,
            live2d_sync_with_video_audio=False,
        )
        sparse = original.to_sparse_dict()
        assert sparse["live2d_model_position"] == {"x": 100, "y": 200}
        assert sparse["live2d_model_scale"] == 1.5
        restored = ContentConfig.from_dict(sparse)
        assert restored == original

    # -----------------------------------------------------------------------
    # New fields: dictionary
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_dictionary_fields(self) -> None:
        """Dictionary fields roundtrip correctly."""
        original = ContentConfig(
            dictionary_enabled=True,
            dictionary_interaction_mode="hover",
        )
        sparse = original.to_sparse_dict()
        restored = ContentConfig.from_dict(sparse)
        assert restored == original
        assert restored.dictionary_interaction_mode == "hover"

    # -----------------------------------------------------------------------
    # New fields: view
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_view_fields(self) -> None:
        """View fields roundtrip correctly."""
        original = ContentConfig(hide_sidebars=True, view_mode="widescreen")
        sparse = original.to_sparse_dict()
        restored = ContentConfig.from_dict(sparse)
        assert restored == original
        assert restored.view_mode == "widescreen"

    # -----------------------------------------------------------------------
    # Comprehensive roundtrip with all fields
    # -----------------------------------------------------------------------

    @pytest.mark.unit
    def test_roundtrip_all_fields(self) -> None:
        """Full roundtrip with every field populated."""
        original = ContentConfig(
            # AI / model
            source_language="ja",
            target_language="en",
            llm_model="claude-3-5-sonnet",
            tts_model="alloy",
            prompts={"timeline": "concise"},
            learner_profile="graduate student",
            note_context_mode="both",
            # Playback
            auto_pause_on_leave=True,
            auto_resume_on_return=True,
            auto_switch_subtitles_on_leave=False,
            auto_switch_voiceover_on_leave=True,
            voiceover_auto_switch_threshold_ms=3000,
            summary_threshold_seconds=60,
            subtitle_context_window_seconds=15,
            subtitle_repeat_count=2,
            # Subtitle display
            subtitle_font_size=18,
            subtitle_bottom_offset=40,
            # Notifications
            browser_notifications_enabled=True,
            toast_notifications_enabled=False,
            title_flash_enabled=True,
            # Live2D
            live2d_enabled=True,
            live2d_model_path="/models/haru.model3.json",
            live2d_model_position={"x": 50, "y": 100},
            live2d_model_scale=2.0,
            live2d_sync_with_video_audio=True,
            # Dictionary
            dictionary_enabled=True,
            dictionary_interaction_mode="click",
            # View
            hide_sidebars=False,
            view_mode="fullscreen",
        )
        sparse = original.to_sparse_dict()
        restored = ContentConfig.from_dict(sparse)
        assert restored == original
        # Verify field count matches (none should be None)
        from dataclasses import fields as dc_fields

        for f in dc_fields(original):
            assert getattr(restored, f.name) is not None

    @pytest.mark.unit
    def test_from_dict_new_fields_mixed_with_unknown(self) -> None:
        """from_dict picks known new fields and ignores unknown ones."""
        config = ContentConfig.from_dict(
            {
                "live2d_enabled": True,
                "subtitle_font_size": 24,
                "nonexistent_field": "ignored",
            }
        )
        assert config.live2d_enabled is True
        assert config.subtitle_font_size == 24
        assert config.to_sparse_dict() == {
            "live2d_enabled": True,
            "subtitle_font_size": 24,
        }
