"""Unit tests for FFmpegAudioProcessor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deeplecture.infrastructure.gateways.ffmpeg_audio import (
    FFmpegAudioProcessor,
    _validate_concat_path,
)


class TestAttempoFilterBuilder:
    """Tests for _build_atempo_filter() internal method."""

    @pytest.fixture
    def processor(self) -> FFmpegAudioProcessor:
        """Create processor for testing."""
        return FFmpegAudioProcessor()

    @pytest.mark.unit
    def test_no_filter_for_1x_speed(self, processor: FFmpegAudioProcessor) -> None:
        """Speed 1.0 should produce empty filter string."""
        result = processor._build_atempo_filter(1.0)
        assert result == ""

    @pytest.mark.unit
    def test_near_1x_speed(self, processor: FFmpegAudioProcessor) -> None:
        """Speed very close to 1.0 should produce empty filter string."""
        result = processor._build_atempo_filter(1.0005)
        assert result == ""

    @pytest.mark.unit
    def test_simple_speedup(self, processor: FFmpegAudioProcessor) -> None:
        """Speed 1.5x should produce single atempo filter."""
        result = processor._build_atempo_filter(1.5)
        assert "atempo=1.5" in result
        assert result.count("atempo") == 1

    @pytest.mark.unit
    def test_2x_speed(self, processor: FFmpegAudioProcessor) -> None:
        """Speed 2.0x should produce single atempo=2.0 filter."""
        result = processor._build_atempo_filter(2.0)
        # Implementation formats with 6 decimals: "atempo=2.000000"
        assert result.startswith("atempo=2.0")
        assert result.count("atempo") == 1

    @pytest.mark.unit
    def test_speed_above_2x(self, processor: FFmpegAudioProcessor) -> None:
        """Speed > 2.0x should chain multiple atempo filters."""
        result = processor._build_atempo_filter(3.0)
        assert "atempo=2.0" in result
        assert result.count(",") >= 1  # At least one comma = chained filters

    @pytest.mark.unit
    def test_4x_speed(self, processor: FFmpegAudioProcessor) -> None:
        """Speed 4.0x should use two atempo=2.0 filters."""
        result = processor._build_atempo_filter(4.0)
        # Implementation formats with 6 decimals: "atempo=2.000000,atempo=2.000000"
        assert "atempo=2.0" in result
        assert result.count("atempo") == 2
        assert "," in result  # Chained filters

    @pytest.mark.unit
    def test_slowdown(self, processor: FFmpegAudioProcessor) -> None:
        """Speed < 1.0 should produce atempo filter with value < 1."""
        result = processor._build_atempo_filter(0.75)
        assert "atempo=0.75" in result

    @pytest.mark.unit
    def test_speed_below_0_5(self, processor: FFmpegAudioProcessor) -> None:
        """Speed < 0.5x should chain multiple atempo filters."""
        result = processor._build_atempo_filter(0.3)
        assert "atempo=0.5" in result
        assert result.count(",") >= 1


class TestConcatPathValidation:
    """Tests for _validate_concat_path() security function."""

    @pytest.mark.unit
    def test_valid_path(self) -> None:
        """Normal path should pass validation."""
        _validate_concat_path("/tmp/audio.wav")  # Should not raise

    @pytest.mark.unit
    def test_path_with_newline(self) -> None:
        """Path with newline should raise ValueError."""
        with pytest.raises(ValueError, match="contains newline"):
            _validate_concat_path("/tmp/file\n.wav")

    @pytest.mark.unit
    def test_path_with_carriage_return(self) -> None:
        """Path with carriage return should raise ValueError."""
        with pytest.raises(ValueError, match="contains newline"):
            _validate_concat_path("/tmp/file\r.wav")

    @pytest.mark.unit
    def test_path_with_unicode(self) -> None:
        """Path with Unicode characters should pass."""
        _validate_concat_path("/tmp/讲座音频.wav")  # Should not raise


class TestFFmpegAudioProcessorInit:
    """Tests for FFmpegAudioProcessor initialization."""

    @pytest.mark.unit
    def test_default_paths(self) -> None:
        """Default initialization should use 'ffmpeg' and 'ffprobe'."""
        processor = FFmpegAudioProcessor()
        assert processor._ffmpeg == "ffmpeg"
        assert processor._ffprobe == "ffprobe"

    @pytest.mark.unit
    def test_custom_paths(self) -> None:
        """Custom paths should be accepted."""
        processor = FFmpegAudioProcessor(
            ffmpeg_path="/usr/local/bin/ffmpeg",
            ffprobe_path="/usr/local/bin/ffprobe",
        )
        assert processor._ffmpeg == "/usr/local/bin/ffmpeg"
        assert processor._ffprobe == "/usr/local/bin/ffprobe"


class TestFFmpegProbeDuration:
    """Tests for probe_duration_seconds() with mocked subprocess."""

    @pytest.mark.unit
    def test_probe_success(self) -> None:
        """Successful probe should return duration."""
        processor = FFmpegAudioProcessor()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="123.456\n", returncode=0)

            result = processor.probe_duration_seconds("/tmp/test.wav")

            assert result == 123.456
            mock_run.assert_called_once()

    @pytest.mark.unit
    def test_probe_failure(self) -> None:
        """Failed probe should raise RuntimeError."""
        processor = FFmpegAudioProcessor()

        with patch("subprocess.run") as mock_run:
            from subprocess import CalledProcessError

            mock_run.side_effect = CalledProcessError(1, ["ffprobe"], stderr=b"error")

            with pytest.raises(RuntimeError, match="Failed to probe"):
                processor.probe_duration_seconds("/tmp/test.wav")

    @pytest.mark.unit
    def test_probe_timeout(self) -> None:
        """Probe timeout should raise RuntimeError."""
        processor = FFmpegAudioProcessor()

        with patch("subprocess.run") as mock_run:
            from subprocess import TimeoutExpired

            mock_run.side_effect = TimeoutExpired(["ffprobe"], 30)

            with pytest.raises(RuntimeError, match="timed out"):
                processor.probe_duration_seconds("/tmp/test.wav")


class TestFFmpegConcatenation:
    """Tests for concatenation methods."""

    @pytest.mark.unit
    def test_concat_empty_list(self) -> None:
        """Empty input list should raise ValueError."""
        processor = FFmpegAudioProcessor()

        with pytest.raises(ValueError, match="No audio files"):
            processor.concat_wavs_to_wav([], "/tmp/output.wav")

    @pytest.mark.unit
    def test_concat_to_m4a_empty_list(self) -> None:
        """Empty input list should raise ValueError."""
        processor = FFmpegAudioProcessor()

        with pytest.raises(ValueError, match="No audio files"):
            processor.concat_wavs_to_m4a([], "/tmp/output.m4a")
