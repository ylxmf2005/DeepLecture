"""Unit tests for content config API validation."""

from __future__ import annotations

import pytest

from deeplecture.presentation.api.routes.content_config import _validate_config_fields


class TestValidateConfigFields:
    """Tests for _validate_config_fields validation logic."""

    # -------------------------------------------------------------------
    # Happy path
    # -------------------------------------------------------------------

    @pytest.mark.unit
    def test_empty_dict_is_valid(self) -> None:
        assert _validate_config_fields({}) is None

    @pytest.mark.unit
    def test_all_valid_fields(self) -> None:
        data = {
            "source_language": "ja",
            "auto_pause_on_leave": True,
            "subtitle_font_size": 16,
            "live2d_model_scale": 1.5,
            "view_mode": "widescreen",
            "dictionary_interaction_mode": "hover",
            "live2d_model_position": {"x": 10, "y": 20},
        }
        assert _validate_config_fields(data) is None

    # -------------------------------------------------------------------
    # Boolean validation
    # -------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "field",
        [
            "auto_pause_on_leave",
            "auto_resume_on_return",
            "auto_switch_subtitles_on_leave",
            "auto_switch_voiceover_on_leave",
            "browser_notifications_enabled",
            "toast_notifications_enabled",
            "title_flash_enabled",
            "live2d_enabled",
            "live2d_sync_with_video_audio",
            "dictionary_enabled",
            "hide_sidebars",
        ],
    )
    def test_bool_field_rejects_non_bool(self, field: str) -> None:
        err = _validate_config_fields({field: "yes"})
        assert err is not None
        assert field in err
        assert "boolean" in err

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "field",
        [
            "auto_pause_on_leave",
            "browser_notifications_enabled",
            "live2d_enabled",
            "hide_sidebars",
        ],
    )
    def test_bool_field_accepts_true_false(self, field: str) -> None:
        assert _validate_config_fields({field: True}) is None
        assert _validate_config_fields({field: False}) is None

    @pytest.mark.unit
    def test_bool_field_rejects_int(self) -> None:
        """Integers (including 0/1) are not valid booleans."""
        err = _validate_config_fields({"auto_pause_on_leave": 1})
        assert err is not None
        assert "boolean" in err

    # -------------------------------------------------------------------
    # Integer range validation
    # -------------------------------------------------------------------

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "field,lo,hi",
        [
            ("voiceover_auto_switch_threshold_ms", 0, 60_000),
            ("summary_threshold_seconds", 0, 3600),
            ("subtitle_context_window_seconds", 0, 300),
            ("subtitle_repeat_count", 1, 10),
            ("subtitle_font_size", 8, 72),
            ("subtitle_bottom_offset", 0, 500),
        ],
    )
    def test_int_field_rejects_out_of_range(self, field: str, lo: int, hi: int) -> None:
        err_below = _validate_config_fields({field: lo - 1})
        assert err_below is not None
        assert "between" in err_below

        err_above = _validate_config_fields({field: hi + 1})
        assert err_above is not None
        assert "between" in err_above

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "field,lo,hi",
        [
            ("subtitle_font_size", 8, 72),
            ("subtitle_repeat_count", 1, 10),
        ],
    )
    def test_int_field_accepts_bounds(self, field: str, lo: int, hi: int) -> None:
        assert _validate_config_fields({field: lo}) is None
        assert _validate_config_fields({field: hi}) is None

    @pytest.mark.unit
    def test_int_field_rejects_string(self) -> None:
        err = _validate_config_fields({"subtitle_font_size": "16"})
        assert err is not None
        assert "integer" in err

    @pytest.mark.unit
    def test_int_field_rejects_float(self) -> None:
        err = _validate_config_fields({"subtitle_font_size": 16.5})
        assert err is not None
        assert "integer" in err

    @pytest.mark.unit
    def test_int_field_rejects_bool(self) -> None:
        """Booleans should not pass integer validation (bool is subclass of int)."""
        err = _validate_config_fields({"subtitle_font_size": True})
        assert err is not None
        assert "integer" in err

    # -------------------------------------------------------------------
    # Enum validation
    # -------------------------------------------------------------------

    @pytest.mark.unit
    def test_view_mode_rejects_invalid(self) -> None:
        err = _validate_config_fields({"view_mode": "maximized"})
        assert err is not None
        assert "view_mode" in err
        assert "must be one of" in err

    @pytest.mark.unit
    def test_view_mode_accepts_valid(self) -> None:
        for mode in ("normal", "widescreen", "web-fullscreen", "fullscreen"):
            assert _validate_config_fields({"view_mode": mode}) is None

    @pytest.mark.unit
    def test_dictionary_interaction_mode_rejects_invalid(self) -> None:
        err = _validate_config_fields({"dictionary_interaction_mode": "double-click"})
        assert err is not None
        assert "dictionary_interaction_mode" in err

    @pytest.mark.unit
    def test_dictionary_interaction_mode_accepts_valid(self) -> None:
        for mode in ("hover", "click"):
            assert _validate_config_fields({"dictionary_interaction_mode": mode}) is None

    @pytest.mark.unit
    def test_note_context_mode_rejects_invalid(self) -> None:
        err = _validate_config_fields({"note_context_mode": "all"})
        assert err is not None
        assert "note_context_mode" in err

    # -------------------------------------------------------------------
    # Float validation (live2d_model_scale)
    # -------------------------------------------------------------------

    @pytest.mark.unit
    def test_scale_rejects_out_of_range(self) -> None:
        err_lo = _validate_config_fields({"live2d_model_scale": 0.05})
        assert err_lo is not None
        assert "between" in err_lo

        err_hi = _validate_config_fields({"live2d_model_scale": 6.0})
        assert err_hi is not None
        assert "between" in err_hi

    @pytest.mark.unit
    def test_scale_accepts_int(self) -> None:
        """Integer values are accepted for scale (2 -> 2.0)."""
        assert _validate_config_fields({"live2d_model_scale": 2}) is None

    @pytest.mark.unit
    def test_scale_rejects_string(self) -> None:
        err = _validate_config_fields({"live2d_model_scale": "1.5"})
        assert err is not None
        assert "number" in err

    @pytest.mark.unit
    def test_scale_rejects_bool(self) -> None:
        err = _validate_config_fields({"live2d_model_scale": True})
        assert err is not None
        assert "number" in err

    # -------------------------------------------------------------------
    # Live2D model position validation
    # -------------------------------------------------------------------

    @pytest.mark.unit
    def test_position_rejects_non_dict(self) -> None:
        err = _validate_config_fields({"live2d_model_position": [10, 20]})
        assert err is not None
        assert "JSON object" in err

    @pytest.mark.unit
    def test_position_rejects_missing_keys(self) -> None:
        err = _validate_config_fields({"live2d_model_position": {"x": 10}})
        assert err is not None
        assert "must contain x and y" in err

    @pytest.mark.unit
    def test_position_rejects_non_numeric(self) -> None:
        err = _validate_config_fields({"live2d_model_position": {"x": "10", "y": 20}})
        assert err is not None
        assert "numbers" in err

    @pytest.mark.unit
    def test_position_accepts_valid(self) -> None:
        assert _validate_config_fields({"live2d_model_position": {"x": 0, "y": 0}}) is None
        assert _validate_config_fields({"live2d_model_position": {"x": 10.5, "y": -20.3}}) is None

    # -------------------------------------------------------------------
    # None values should be accepted (means "unset/inherit")
    # -------------------------------------------------------------------

    @pytest.mark.unit
    def test_none_values_accepted(self) -> None:
        """All fields accept None (meaning 'inherit from global')."""
        data = {
            "auto_pause_on_leave": None,
            "subtitle_font_size": None,
            "view_mode": None,
            "live2d_model_scale": None,
            "live2d_model_position": None,
        }
        assert _validate_config_fields(data) is None

    # -------------------------------------------------------------------
    # Existing field validation (regression)
    # -------------------------------------------------------------------

    @pytest.mark.unit
    def test_learner_profile_too_long(self) -> None:
        err = _validate_config_fields({"learner_profile": "x" * 2001})
        assert err is not None
        assert "maximum length" in err

    @pytest.mark.unit
    def test_llm_model_non_string(self) -> None:
        err = _validate_config_fields({"llm_model": 123})
        assert err is not None
        assert "string" in err
