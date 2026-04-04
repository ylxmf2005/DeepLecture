"""Unit tests for SubtitleUseCase."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deeplecture.config import SubtitleEnhanceTranslateConfig
from deeplecture.domain import ContentMetadata, Segment
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.subtitle import (
    ASRTranscriptionResult,
    GenerateSubtitleRequest,
    SubtitleResult,
)
from deeplecture.use_cases.subtitle import SubtitleUseCase


@pytest.fixture
def mock_metadata_storage() -> MagicMock:
    """Create mock metadata storage."""
    return MagicMock()


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage."""
    return MagicMock()


@pytest.fixture
def mock_asr() -> MagicMock:
    """Create mock ASR service."""
    return MagicMock()


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Create mock LLM provider."""
    provider = MagicMock()
    provider.get.return_value = MagicMock()
    return provider


@pytest.fixture
def mock_prompt_registry() -> MagicMock:
    """Create mock prompt registry."""
    return MagicMock()


@pytest.fixture
def mock_parallel_runner() -> MagicMock:
    """Create mock parallel runner."""
    runner = MagicMock()
    # Default: execute tasks sequentially
    runner.run.side_effect = lambda tasks: [task() for task in tasks]
    return runner


@pytest.fixture
def config() -> SubtitleEnhanceTranslateConfig:
    """Create default config."""
    return SubtitleEnhanceTranslateConfig()


@pytest.fixture
def usecase(
    mock_metadata_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_asr: MagicMock,
    mock_llm_provider: MagicMock,
    mock_prompt_registry: MagicMock,
    mock_parallel_runner: MagicMock,
    config: SubtitleEnhanceTranslateConfig,
) -> SubtitleUseCase:
    """Create SubtitleUseCase with mocked dependencies."""
    return SubtitleUseCase(
        metadata_storage=mock_metadata_storage,
        subtitle_storage=mock_subtitle_storage,
        asr=mock_asr,
        llm_provider=mock_llm_provider,
        prompt_registry=mock_prompt_registry,
        config=config,
        parallel_runner=mock_parallel_runner,
    )


@pytest.fixture
def sample_metadata() -> ContentMetadata:
    """Create sample content metadata."""
    from deeplecture.domain import ContentType

    return ContentMetadata(
        id="test-content-id",
        type=ContentType.VIDEO,
        original_filename="test.mp4",
        source_file="/tmp/test.mp4",
    )


@pytest.fixture
def sample_segments() -> list[Segment]:
    """Create sample ASR segments."""
    return [
        Segment(start=0.0, end=2.5, text="Hello, world."),
        Segment(start=2.5, end=5.0, text="This is a test."),
        Segment(start=5.0, end=7.5, text="Goodbye."),
    ]


class TestSubtitleUseCaseGenerate:
    """Tests for generate() method."""

    @pytest.mark.unit
    def test_generate_success(
        self,
        usecase: SubtitleUseCase,
        mock_metadata_storage: MagicMock,
        mock_subtitle_storage: MagicMock,
        mock_asr: MagicMock,
        sample_metadata: ContentMetadata,
        sample_segments: list[Segment],
    ) -> None:
        """generate() should transcribe audio and save subtitles."""
        mock_metadata_storage.get.return_value = sample_metadata
        mock_asr.transcribe.return_value = ASRTranscriptionResult(
            segments=sample_segments,
            resolved_language="en",
        )

        request = GenerateSubtitleRequest(
            content_id="test-content-id",
            language="en",
        )
        result = usecase.generate(request)

        assert result.content_id == "test-content-id"
        assert result.language == "en"
        assert len(result.segments) == 3
        mock_asr.transcribe.assert_called_once()
        mock_subtitle_storage.save.assert_called_once_with("test-content-id", sample_segments, "en")

    @pytest.mark.unit
    def test_generate_content_not_found(
        self,
        usecase: SubtitleUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """generate() should raise when content doesn't exist."""
        mock_metadata_storage.get.return_value = None

        request = GenerateSubtitleRequest(
            content_id="nonexistent-id",
            language="en",
        )

        with pytest.raises(ContentNotFoundError):
            usecase.generate(request)

    @pytest.mark.unit
    def test_generate_updates_metadata_status(
        self,
        usecase: SubtitleUseCase,
        mock_metadata_storage: MagicMock,
        mock_asr: MagicMock,
        sample_metadata: ContentMetadata,
        sample_segments: list[Segment],
    ) -> None:
        """generate() should update metadata status to READY."""
        mock_metadata_storage.get.return_value = sample_metadata
        mock_asr.transcribe.return_value = ASRTranscriptionResult(
            segments=sample_segments,
            resolved_language="en",
        )

        request = GenerateSubtitleRequest(
            content_id="test-content-id",
            language="en",
        )
        usecase.generate(request)

        # Called twice: processing -> ready
        assert mock_metadata_storage.save.call_count == 2

        # Last call should have status='ready'
        final_metadata = mock_metadata_storage.save.call_args_list[-1][0][0]
        assert final_metadata.subtitle_status == "ready"
        assert final_metadata.detected_source_language is None

    @pytest.mark.unit
    def test_generate_persists_detected_source_language_for_auto(
        self,
        usecase: SubtitleUseCase,
        mock_metadata_storage: MagicMock,
        mock_asr: MagicMock,
        sample_metadata: ContentMetadata,
        sample_segments: list[Segment],
    ) -> None:
        """Auto-detect runs should persist the resolved language on metadata."""
        mock_metadata_storage.get.return_value = sample_metadata
        mock_asr.transcribe.return_value = ASRTranscriptionResult(
            segments=sample_segments,
            resolved_language="ja",
        )

        result = usecase.generate(
            GenerateSubtitleRequest(
                content_id="test-content-id",
                language="auto",
            )
        )

        assert result.language == "ja"
        final_metadata = mock_metadata_storage.save.call_args_list[-1][0][0]
        assert final_metadata.detected_source_language == "ja"


class TestSubtitleUseCaseGetSubtitles:
    """Tests for get_subtitles() method."""

    @pytest.mark.unit
    def test_get_subtitles_success(
        self,
        usecase: SubtitleUseCase,
        mock_subtitle_storage: MagicMock,
        sample_segments: list[Segment],
    ) -> None:
        """get_subtitles() should return subtitles when they exist."""
        mock_subtitle_storage.load.return_value = sample_segments

        result = usecase.get_subtitles("test-content-id", "en")

        assert result is not None
        assert result.content_id == "test-content-id"
        assert result.language == "en"
        assert len(result.segments) == 3
        mock_subtitle_storage.load.assert_called_once_with("test-content-id", "en")

    @pytest.mark.unit
    def test_get_subtitles_not_found(
        self,
        usecase: SubtitleUseCase,
        mock_subtitle_storage: MagicMock,
    ) -> None:
        """get_subtitles() should return None when not found."""
        mock_subtitle_storage.load.return_value = None

        result = usecase.get_subtitles("test-content-id", "en")

        assert result is None


class TestSubtitleUseCaseConvertSrtToVtt:
    """Tests for convert_srt_to_vtt() static method."""

    @pytest.mark.unit
    def test_convert_srt_to_vtt_basic(self) -> None:
        """convert_srt_to_vtt() should convert SRT timestamps to VTT format."""
        srt_content = """1
00:00:00,000 --> 00:00:02,500
Hello, world.

2
00:00:02,500 --> 00:00:05,000
This is a test.
"""
        vtt_content = SubtitleUseCase.convert_srt_to_vtt(srt_content)

        assert "WEBVTT" in vtt_content
        assert "00:00:00.000" in vtt_content
        assert "00:00:02.500" in vtt_content
        # SRT uses comma, VTT uses period
        assert "," not in vtt_content.replace("Hello, world.", "")

    @pytest.mark.unit
    def test_convert_srt_to_vtt_empty(self) -> None:
        """convert_srt_to_vtt() should handle empty content."""
        vtt_content = SubtitleUseCase.convert_srt_to_vtt("")

        assert "WEBVTT" in vtt_content


class TestSubtitleResult:
    """Tests for SubtitleResult DTO."""

    @pytest.mark.unit
    def test_subtitle_result_to_srt(
        self,
        sample_segments: list[Segment],
    ) -> None:
        """SubtitleResult.to_srt() should format segments as SRT."""
        result = SubtitleResult(
            content_id="test",
            language="en",
            segments=sample_segments,
        )

        srt = result.to_srt()

        assert "1\n" in srt
        assert "Hello, world." in srt
        assert "-->" in srt

    @pytest.mark.unit
    def test_subtitle_result_to_vtt(
        self,
        sample_segments: list[Segment],
    ) -> None:
        """SubtitleResult.to_vtt() should format segments as VTT."""
        result = SubtitleResult(
            content_id="test",
            language="en",
            segments=sample_segments,
        )

        vtt = result.to_vtt()

        assert "WEBVTT" in vtt
        assert "Hello, world." in vtt
