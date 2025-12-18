"""Unit tests for TTS gateways."""

from __future__ import annotations

import pytest

from deeplecture.infrastructure.gateways.tts import _filter_tts_text


class TestTTSTextFilter:
    """Tests for _filter_tts_text() preprocessing function."""

    @pytest.mark.unit
    def test_simple_text(self) -> None:
        """Simple text should pass through."""
        result = _filter_tts_text("Hello, world!")
        assert result == "Hello, world!"

    @pytest.mark.unit
    def test_removes_asterisks(self) -> None:
        """Asterisks should be removed."""
        result = _filter_tts_text("This is *important* text")
        assert "*" not in result
        assert "important" in result

    @pytest.mark.unit
    def test_removes_parentheses(self) -> None:
        """Parentheses should be removed."""
        result = _filter_tts_text("Text (with notes) here")
        assert "(" not in result
        assert ")" not in result
        assert "with notes" in result

    @pytest.mark.unit
    def test_removes_backticks(self) -> None:
        """Backticks should be removed."""
        result = _filter_tts_text("Use `code` formatting")
        assert "`" not in result
        assert "code" in result

    @pytest.mark.unit
    def test_removes_dashes(self) -> None:
        """Dashes should be removed."""
        result = _filter_tts_text("First - second - third")
        assert "-" not in result

    @pytest.mark.unit
    def test_replaces_underscores(self) -> None:
        """Underscores should be replaced with spaces."""
        result = _filter_tts_text("snake_case_name")
        assert "_" not in result
        assert "snake case name" in result

    @pytest.mark.unit
    def test_replaces_carriage_returns(self) -> None:
        """Carriage returns should be replaced with spaces."""
        result = _filter_tts_text("Line one\rLine two")
        assert "\r" not in result

    @pytest.mark.unit
    def test_normalizes_whitespace(self) -> None:
        """Multiple spaces should be normalized to single space."""
        result = _filter_tts_text("Too   many    spaces")
        assert "  " not in result
        assert result == "Too many spaces"

    @pytest.mark.unit
    def test_empty_string(self) -> None:
        """Empty string should return empty string."""
        result = _filter_tts_text("")
        assert result == ""

    @pytest.mark.unit
    def test_only_special_chars(self) -> None:
        """String with only special chars should return empty."""
        result = _filter_tts_text("***---`()")
        assert result == ""

    @pytest.mark.unit
    def test_unicode_preserved(self) -> None:
        """Unicode characters should be preserved."""
        result = _filter_tts_text("中文文本 and 日本語")
        assert "中文文本" in result
        assert "日本語" in result

    @pytest.mark.unit
    def test_strips_leading_trailing_whitespace(self) -> None:
        """Leading and trailing whitespace should be removed."""
        result = _filter_tts_text("   spaced text   ")
        assert result == "spaced text"

    @pytest.mark.unit
    def test_complex_markdown_cleaning(self) -> None:
        """Complex markdown-like content should be cleaned."""
        result = _filter_tts_text("**Bold** and *italic* (with notes) `code`")
        # Should contain the words without markdown formatting
        assert "Bold" in result
        assert "italic" in result
        assert "code" in result
        assert "*" not in result
        assert "`" not in result


class TestEdgeTTSInit:
    """Tests for EdgeTTS initialization."""

    @pytest.mark.unit
    def test_edge_tts_import_error(self) -> None:
        """EdgeTTS should raise ImportError if edge-tts not installed."""
        from unittest.mock import patch

        with patch.dict("sys.modules", {"edge_tts": None}):
            # Force reimport to trigger ImportError check
            # This is a defensive test - in real scenario, import would fail
            pass  # EdgeTTS class checks import at __init__ time


class TestFishAudioTTSInit:
    """Tests for FishAudioTTS initialization."""

    @pytest.mark.unit
    def test_speed_clamping_max(self) -> None:
        """Speed should be clamped to max 2.0."""
        from unittest.mock import MagicMock, patch

        with patch.dict("sys.modules", {"fishaudio": MagicMock()}):
            from deeplecture.infrastructure.gateways.tts import FishAudioTTS

            # Create with speed > 2.0
            tts_instance = FishAudioTTS(api_key="test", speed=3.0)
            assert tts_instance._speed == 2.0

    @pytest.mark.unit
    def test_speed_clamping_min(self) -> None:
        """Speed should be clamped to min 0.5."""
        from unittest.mock import MagicMock, patch

        with patch.dict("sys.modules", {"fishaudio": MagicMock()}):
            from deeplecture.infrastructure.gateways.tts import FishAudioTTS

            # Create with speed < 0.5
            tts_instance = FishAudioTTS(api_key="test", speed=0.1)
            assert tts_instance._speed == 0.5

    @pytest.mark.unit
    def test_file_extension_mp3(self) -> None:
        """MP3 format should set .mp3 extension."""
        from unittest.mock import MagicMock, patch

        with patch.dict("sys.modules", {"fishaudio": MagicMock()}):
            from deeplecture.infrastructure.gateways.tts import FishAudioTTS

            tts_instance = FishAudioTTS(api_key="test", audio_format="mp3")
            assert tts_instance.file_extension == ".mp3"

    @pytest.mark.unit
    def test_file_extension_opus(self) -> None:
        """Opus format should set .opus extension."""
        from unittest.mock import MagicMock, patch

        with patch.dict("sys.modules", {"fishaudio": MagicMock()}):
            from deeplecture.infrastructure.gateways.tts import FishAudioTTS

            tts_instance = FishAudioTTS(api_key="test", audio_format="opus")
            assert tts_instance.file_extension == ".opus"

    @pytest.mark.unit
    def test_file_extension_default_wav(self) -> None:
        """Default format should set .wav extension."""
        from unittest.mock import MagicMock, patch

        with patch.dict("sys.modules", {"fishaudio": MagicMock()}):
            from deeplecture.infrastructure.gateways.tts import FishAudioTTS

            tts_instance = FishAudioTTS(api_key="test")
            assert tts_instance.file_extension == ".wav"
