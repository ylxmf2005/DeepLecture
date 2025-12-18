"""Unit tests for VoiceoverUseCase."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deeplecture.config import VoiceoverConfig
from deeplecture.domain.entities import Segment
from deeplecture.use_cases.dto.voiceover import GenerateVoiceoverRequest
from deeplecture.use_cases.voiceover import VoiceoverUseCase


@pytest.fixture
def mock_audio() -> MagicMock:
    """Create mock audio processor."""
    return MagicMock()


@pytest.fixture
def mock_file_storage() -> MagicMock:
    """Create mock file storage."""
    storage = MagicMock()
    return storage


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage."""
    return MagicMock()


@pytest.fixture
def mock_tts_factory() -> MagicMock:
    """Create mock TTS factory."""
    return MagicMock()


@pytest.fixture
def mock_parallel_runner() -> MagicMock:
    """Create mock parallel runner."""
    return MagicMock()


@pytest.fixture
def config() -> VoiceoverConfig:
    """Create default config."""
    return VoiceoverConfig()


@pytest.fixture
def usecase(
    mock_audio: MagicMock,
    mock_file_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_tts_factory,
    mock_parallel_runner: MagicMock,
    config: VoiceoverConfig,
) -> VoiceoverUseCase:
    """Create VoiceoverUseCase with mocked dependencies."""
    return VoiceoverUseCase(
        audio=mock_audio,
        file_storage=mock_file_storage,
        subtitle_storage=mock_subtitle_storage,
        tts_factory=mock_tts_factory,
        parallel_runner=mock_parallel_runner,
        config=config,
    )


class TestVoiceoverUseCaseGenerate:
    """Tests for generate() method."""

    @pytest.mark.unit
    def test_generate_raises_on_missing_subtitles(
        self,
        usecase: VoiceoverUseCase,
        mock_subtitle_storage: MagicMock,
    ) -> None:
        """generate() should raise when subtitles cannot be loaded."""
        mock_subtitle_storage.load.return_value = None

        request = GenerateVoiceoverRequest(
            content_id="c1",
            video_path="/tmp/test.mp4",
            output_dir="/tmp/output",
            language="en",
            subtitle_language="en",
        )

        with pytest.raises(ValueError, match="No valid subtitle segments"):
            usecase.generate(request)

    @pytest.mark.unit
    def test_generate_creates_output_directory(
        self,
        usecase: VoiceoverUseCase,
        mock_file_storage: MagicMock,
        mock_subtitle_storage: MagicMock,
    ) -> None:
        """generate() should create output directory."""
        mock_subtitle_storage.load.return_value = None

        request = GenerateVoiceoverRequest(
            content_id="c1",
            video_path="/tmp/test.mp4",
            output_dir="/tmp/voiceover_output",
            language="en",
            subtitle_language="en",
        )

        with pytest.raises(ValueError):
            usecase.generate(request)

        mock_file_storage.makedirs.assert_called_with("/tmp/voiceover_output")

    @pytest.mark.unit
    def test_fallback_to_base_when_enhanced_has_empty_text(
        self,
        usecase: VoiceoverUseCase,
        mock_subtitle_storage: MagicMock,
        mock_file_storage: MagicMock,
        mock_audio: MagicMock,
        mock_parallel_runner: MagicMock,
    ) -> None:
        """Fallback to base subtitles when enhanced exists but has all empty text."""
        # Enhanced subtitles exist but have empty text
        enhanced_segments = [
            Segment(start=0.0, end=1.0, text="   "),
            Segment(start=1.0, end=2.0, text="\n\t"),
        ]
        # Base subtitles have valid content
        base_segments = [
            Segment(start=0.0, end=1.0, text="Hello"),
            Segment(start=1.0, end=2.0, text="World"),
        ]

        def load_side_effect(content_id: str, language: str):
            if language == "en_enhanced":
                return enhanced_segments
            if language == "en":
                return base_segments
            return None

        mock_subtitle_storage.load.side_effect = load_side_effect
        mock_audio.probe_duration_seconds.return_value = 5.0
        mock_parallel_runner.map_ordered.return_value = ["/tmp/seg1.wav", "/tmp/seg2.wav"]
        mock_file_storage.file_exists.return_value = True

        request = GenerateVoiceoverRequest(
            content_id="c1",
            video_path="/tmp/test.mp4",
            output_dir="/tmp/output",
            language="en",
            subtitle_language="en",
        )

        # Should NOT raise - should fallback to base subtitles
        try:
            usecase.generate(request)
        except ValueError as e:
            pytest.fail(f"Should fallback to base subtitles, but raised: {e}")
        except RuntimeError:
            # Other runtime errors (TTS, concat) are expected in this minimal mock setup
            pass

        # Verify both enhanced and base were checked
        assert mock_subtitle_storage.load.call_count >= 2
        calls = [c[0] for c in mock_subtitle_storage.load.call_args_list]
        assert ("c1", "en_enhanced") in calls
        assert ("c1", "en") in calls
