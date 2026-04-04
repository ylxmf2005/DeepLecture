"""Unit tests for WhisperASR gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from deeplecture.infrastructure.gateways.whisper import WHISPER_MODELS, WhisperASR


class TestWhisperSRTParsing:
    """Tests for SRT parsing logic."""

    @pytest.fixture
    def asr(self) -> WhisperASR:
        """Create WhisperASR instance (without ensuring ready)."""
        return WhisperASR(auto_download=False)

    @pytest.mark.unit
    def test_parse_simple_srt(self, asr: WhisperASR) -> None:
        """Simple SRT should be parsed correctly."""
        srt_content = """1
00:00:00,000 --> 00:00:02,500
Hello, welcome to the lecture.

2
00:00:02,500 --> 00:00:05,000
This is the introduction.
"""
        segments = asr._parse_srt(srt_content)

        assert len(segments) == 2
        assert segments[0].start == 0.0
        assert segments[0].end == 2.5
        assert segments[0].text == "Hello, welcome to the lecture."
        assert segments[1].start == 2.5
        assert segments[1].end == 5.0

    @pytest.mark.unit
    def test_parse_empty_srt(self, asr: WhisperASR) -> None:
        """Empty SRT should return empty list."""
        segments = asr._parse_srt("")
        assert segments == []

    @pytest.mark.unit
    def test_parse_multiline_text(self, asr: WhisperASR) -> None:
        """Multiline subtitle text should be preserved."""
        srt_content = """1
00:00:00,000 --> 00:00:03,000
First line
Second line

"""
        segments = asr._parse_srt(srt_content)

        assert len(segments) == 1
        assert "First line" in segments[0].text
        assert "Second line" in segments[0].text

    @pytest.mark.unit
    def test_parse_time_conversion(self, asr: WhisperASR) -> None:
        """Time strings should be converted to seconds correctly."""
        assert asr._parse_time("00:00:00,000") == 0.0
        assert asr._parse_time("00:00:01,000") == 1.0
        assert asr._parse_time("00:01:00,000") == 60.0
        assert asr._parse_time("01:00:00,000") == 3600.0
        assert asr._parse_time("00:00:00,500") == 0.5
        assert asr._parse_time("01:30:45,250") == 5445.25

    @pytest.mark.unit
    def test_parse_resolved_language_from_json(self, asr: WhisperASR, test_data_dir: Path) -> None:
        """Whisper JSON output should expose the resolved language."""
        json_path = test_data_dir / "whisper.json"
        json_path.write_text('{"result": {"language": "ja"}}', encoding="utf-8")

        assert asr._parse_resolved_language(json_path) == "ja"

    @pytest.mark.unit
    def test_parse_resolved_language_requires_value(self, asr: WhisperASR, test_data_dir: Path) -> None:
        """Missing language in whisper JSON should raise a runtime error."""
        json_path = test_data_dir / "whisper-empty.json"
        json_path.write_text('{"result": {}}', encoding="utf-8")

        with pytest.raises(RuntimeError, match="did not return a language"):
            asr._parse_resolved_language(json_path)


class TestWhisperHardwareDetection:
    """Tests for hardware detection."""

    @pytest.mark.unit
    def test_detect_hardware_returns_dict(self) -> None:
        """Hardware detection should return expected keys."""
        asr = WhisperASR(auto_download=False)
        hw = asr._hw_info

        assert "platform" in hw
        assert "machine" in hw
        assert "has_metal" in hw
        assert "has_cuda" in hw
        assert "cpu_count" in hw

    @pytest.mark.unit
    def test_cpu_count_positive(self) -> None:
        """CPU count should be positive."""
        asr = WhisperASR(auto_download=False)
        assert asr._hw_info["cpu_count"] >= 1


class TestWhisperModelConfig:
    """Tests for model configuration."""

    @pytest.mark.unit
    def test_known_models_have_checksums(self) -> None:
        """All known models should have SHA256 checksums."""
        for model_name, info in WHISPER_MODELS.items():
            assert "url" in info, f"Model {model_name} missing URL"
            assert "sha256" in info, f"Model {model_name} missing SHA256"
            assert len(info["sha256"]) == 64, f"Model {model_name} has invalid SHA256 length"

    @pytest.mark.unit
    def test_default_model(self) -> None:
        """Default model should be large-v3-turbo."""
        asr = WhisperASR(auto_download=False)
        assert asr._model_name == "large-v3-turbo"

    @pytest.mark.unit
    def test_custom_model_name(self) -> None:
        """Custom model name should be accepted."""
        asr = WhisperASR(model_name="tiny", auto_download=False)
        assert asr._model_name == "tiny"


class TestWhisperSHA256:
    """Tests for SHA256 checksum computation."""

    @pytest.mark.unit
    def test_compute_sha256(self, test_data_dir: Path) -> None:
        """SHA256 should be computed correctly."""
        # Create test file with known content
        test_file = test_data_dir / "test.bin"
        test_file.write_bytes(b"test content")

        # Expected SHA256 of "test content"
        expected = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"

        result = WhisperASR._compute_sha256(test_file)
        assert result == expected

    @pytest.mark.unit
    def test_compute_sha256_empty_file(self, test_data_dir: Path) -> None:
        """SHA256 of empty file should be correct."""
        test_file = test_data_dir / "empty.bin"
        test_file.write_bytes(b"")

        # SHA256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        result = WhisperASR._compute_sha256(test_file)
        assert result == expected


class TestWhisperInit:
    """Tests for WhisperASR initialization."""

    @pytest.mark.unit
    def test_auto_download_default(self) -> None:
        """Auto download should be True by default."""
        asr = WhisperASR()
        assert asr._auto_download is True

    @pytest.mark.unit
    def test_auto_download_disabled(self) -> None:
        """Auto download can be disabled."""
        asr = WhisperASR(auto_download=False)
        assert asr._auto_download is False
        assert asr._ready is False

    @pytest.mark.unit
    def test_custom_whisper_cpp_dir(self, test_data_dir: Path) -> None:
        """Custom whisper.cpp directory should be accepted."""
        custom_dir = test_data_dir / "custom_whisper"
        asr = WhisperASR(whisper_cpp_dir=custom_dir, auto_download=False)

        assert asr._whisper_cpp_dir == custom_dir
