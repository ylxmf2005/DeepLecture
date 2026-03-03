"""Unit tests for PodcastUseCase."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from deeplecture.domain import Segment
from deeplecture.use_cases.dto.podcast import (
    DialogueItem,
    GeneratePodcastRequest,
    PodcastResult,
    PodcastSegment,
    PodcastStats,
)
from deeplecture.use_cases.interfaces.prompt_registry import PromptSpec
from deeplecture.use_cases.podcast import PodcastUseCase

# =============================================================================
# DTO Tests
# =============================================================================


class TestDialogueItemDTO:
    """Tests for DialogueItem dataclass."""

    @pytest.mark.unit
    def test_to_dict(self) -> None:
        item = DialogueItem(speaker="host", text="Welcome to our podcast!")
        result = item.to_dict()
        assert result["speaker"] == "host"
        assert result["text"] == "Welcome to our podcast!"

    @pytest.mark.unit
    def test_from_dict(self) -> None:
        data = {"speaker": "guest", "text": "Thanks for having me."}
        item = DialogueItem.from_dict(data)
        assert item.speaker == "guest"
        assert item.text == "Thanks for having me."

    @pytest.mark.unit
    def test_from_dict_defaults(self) -> None:
        data: dict[str, object] = {}
        item = DialogueItem.from_dict(data)
        assert item.speaker == "host"
        assert item.text == ""


class TestPodcastSegmentDTO:
    """Tests for PodcastSegment dataclass."""

    @pytest.mark.unit
    def test_to_dict(self) -> None:
        seg = PodcastSegment(
            speaker="host",
            text="Let's talk about physics.",
            start_time=0.0,
            end_time=3.5,
        )
        result = seg.to_dict()
        assert result["speaker"] == "host"
        assert result["start_time"] == 0.0
        assert result["end_time"] == 3.5

    @pytest.mark.unit
    def test_from_dict(self) -> None:
        data = {
            "speaker": "guest",
            "text": "Sure!",
            "start_time": 3.8,
            "end_time": 4.5,
        }
        seg = PodcastSegment.from_dict(data)
        assert seg.speaker == "guest"
        assert seg.start_time == 3.8
        assert seg.end_time == 4.5

    @pytest.mark.unit
    def test_from_dict_defaults(self) -> None:
        data: dict[str, object] = {}
        seg = PodcastSegment.from_dict(data)
        assert seg.speaker == "host"
        assert seg.start_time == 0.0
        assert seg.end_time == 0.0


class TestPodcastStats:
    """Tests for PodcastStats."""

    @pytest.mark.unit
    def test_stats_to_dict(self) -> None:
        stats = PodcastStats(
            total_dialogue_items=20,
            tts_success_count=18,
            tts_failure_count=2,
        )
        result = stats.to_dict()
        assert result["total_dialogue_items"] == 20
        assert result["tts_success_count"] == 18
        assert result["tts_failure_count"] == 2


class TestPodcastResult:
    """Tests for PodcastResult."""

    @pytest.mark.unit
    def test_empty_result(self) -> None:
        result = PodcastResult(content_id="cid", language="en")
        d = result.to_dict()
        assert d["content_id"] == "cid"
        assert d["segments"] == []
        assert d["title"] == ""

    @pytest.mark.unit
    def test_result_with_segments(self) -> None:
        seg = PodcastSegment(
            speaker="host",
            text="Hello",
            start_time=0.0,
            end_time=1.0,
        )
        result = PodcastResult(
            content_id="cid",
            language="en",
            title="Test Podcast",
            summary="A summary.",
            segments=[seg],
            duration=1.0,
        )
        d = result.to_dict()
        assert len(d["segments"]) == 1
        assert d["title"] == "Test Podcast"
        assert d["duration"] == 1.0


# =============================================================================
# PodcastUseCase Tests
# =============================================================================


@pytest.fixture
def mock_podcast_storage() -> MagicMock:
    storage = MagicMock()
    storage.load.return_value = None
    storage.exists.return_value = False
    storage.get_audio_path.return_value = "/tmp/test-content/podcast/en.m4a"
    return storage


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    storage = MagicMock()
    segments = [
        Segment(start=0.0, end=5.0, text="Introduction to relativity."),
        Segment(start=5.0, end=10.0, text="E equals mc squared."),
    ]

    def load_side_effect(content_id: str, language: str) -> list[Segment] | None:
        if content_id == "test-content-id" and language == "en_enhanced":
            return segments
        return None

    storage.load.side_effect = load_side_effect
    storage.list_languages.return_value = ["en_enhanced", "en"]
    return storage


@pytest.fixture
def mock_llm() -> MagicMock:
    llm = MagicMock()
    # Stage 1: Knowledge extraction
    extraction_response = json.dumps(
        [
            {
                "category": "formula",
                "content": "E = mc²",
                "criticality": "high",
                "tags": ["physics"],
                "source_start": 5.0,
            },
        ]
    )
    # Stage 2: Dialogue generation
    dialogue_response = json.dumps(
        {
            "title": "Understanding Relativity",
            "summary": "A chat about physics",
            "scratchpad": "Key points...",
            "dialogue": [
                {"speaker": "host", "text": "Welcome! Today we discuss E=mc²."},
                {"speaker": "guest", "text": "Thanks! It is a beautiful equation."},
                {"speaker": "host", "text": "Why is it so important?"},
                {"speaker": "guest", "text": "It shows mass and energy are equivalent."},
            ],
        }
    )
    # Stage 3: Dramatization
    dramatize_response = json.dumps(
        [
            {"speaker": "host", "text": "Hey everyone, welcome back! Today, we're diving into E equals mc squared."},
            {"speaker": "guest", "text": "Oh, thanks for having me! You know, it's really a beautiful equation."},
            {"speaker": "host", "text": "So, why is it so important, in your opinion?"},
            {
                "speaker": "guest",
                "text": "Well, because it shows that mass and energy are fundamentally the same thing!",
            },
        ]
    )
    llm.complete.side_effect = [extraction_response, dialogue_response, dramatize_response]
    return llm


@pytest.fixture
def mock_llm_provider(mock_llm: MagicMock) -> MagicMock:
    provider = MagicMock()
    provider.get.return_value = mock_llm
    return provider


@pytest.fixture
def mock_tts() -> MagicMock:
    tts = MagicMock()
    tts.synthesize.return_value = b"\x00" * 1000
    return tts


@pytest.fixture
def mock_tts_provider(mock_tts: MagicMock) -> MagicMock:
    provider = MagicMock()
    provider.get.return_value = mock_tts
    return provider


@pytest.fixture
def mock_audio_processor() -> MagicMock:
    processor = MagicMock()
    processor.transcode_to_wav.return_value = None
    processor.probe_duration_seconds.return_value = 2.5
    processor.generate_silence_wav.return_value = None
    processor.concat_wavs_to_m4a.return_value = None
    return processor


@pytest.fixture
def mock_file_storage() -> MagicMock:
    storage = MagicMock()
    storage.write_bytes.return_value = None
    storage.remove_file.return_value = None
    return storage


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    resolver = MagicMock()
    resolver.build_content_path.side_effect = lambda content_id, *parts: f"/tmp/{content_id}/{'/'.join(parts)}"
    resolver.ensure_temp_dir.return_value = "/tmp/podcast_work"
    return resolver


@pytest.fixture
def mock_prompt_registry() -> MagicMock:
    registry = MagicMock()
    builder = MagicMock()
    builder.build.return_value = PromptSpec(
        user_prompt="test user prompt",
        system_prompt="test system prompt",
    )
    registry.get.return_value = builder
    return registry


@pytest.fixture
def mock_parallel_runner() -> MagicMock:
    runner = MagicMock()
    runner.map_ordered.side_effect = lambda items, fn, **kw: [fn(item) for item in items]
    return runner


@pytest.fixture
def mock_metadata_storage() -> MagicMock:
    storage = MagicMock()
    storage.get.return_value = None
    return storage


@pytest.fixture
def mock_pdf_text_extractor() -> MagicMock:
    extractor = MagicMock()
    extractor.extract_text.return_value = ""
    return extractor


@pytest.fixture
def podcast_usecase(
    mock_podcast_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_llm_provider: MagicMock,
    mock_tts_provider: MagicMock,
    mock_audio_processor: MagicMock,
    mock_file_storage: MagicMock,
    mock_path_resolver: MagicMock,
    mock_prompt_registry: MagicMock,
    mock_parallel_runner: MagicMock,
    mock_metadata_storage: MagicMock,
    mock_pdf_text_extractor: MagicMock,
) -> PodcastUseCase:
    return PodcastUseCase(
        podcast_storage=mock_podcast_storage,
        subtitle_storage=mock_subtitle_storage,
        llm_provider=mock_llm_provider,
        tts_provider=mock_tts_provider,
        audio_processor=mock_audio_processor,
        file_storage=mock_file_storage,
        path_resolver=mock_path_resolver,
        prompt_registry=mock_prompt_registry,
        parallel_runner=mock_parallel_runner,
        metadata_storage=mock_metadata_storage,
        pdf_text_extractor=mock_pdf_text_extractor,
    )


class TestPodcastUseCaseGet:
    """Tests for get() method."""

    @pytest.mark.unit
    def test_get_returns_empty_when_not_found(
        self,
        podcast_usecase: PodcastUseCase,
        mock_podcast_storage: MagicMock,
    ) -> None:
        mock_podcast_storage.load.return_value = None
        result = podcast_usecase.get("test-content-id", "en")

        assert result.content_id == "test-content-id"
        assert result.segments == []

    @pytest.mark.unit
    def test_get_returns_stored_podcast(
        self,
        podcast_usecase: PodcastUseCase,
        mock_podcast_storage: MagicMock,
    ) -> None:
        stored_data = {
            "title": "Test Podcast",
            "summary": "About physics",
            "segments": [
                {
                    "speaker": "host",
                    "text": "Hello!",
                    "start_time": 0.0,
                    "end_time": 2.0,
                }
            ],
        }
        mock_podcast_storage.load.return_value = (
            stored_data,
            datetime.now(timezone.utc),
        )

        result = podcast_usecase.get("test-content-id", "en")

        assert result.content_id == "test-content-id"
        assert len(result.segments) == 1
        assert result.title == "Test Podcast"
        assert result.segments[0].speaker == "host"


class TestPodcastUseCaseGenerate:
    """Tests for generate() method."""

    @pytest.mark.unit
    def test_generate_raises_when_no_context(
        self,
        podcast_usecase: PodcastUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
    ) -> None:
        mock_subtitle_storage.list_languages.return_value = []
        mock_pdf_text_extractor.extract_text.return_value = ""

        request = GeneratePodcastRequest(
            content_id="empty-content-id",
            language="en",
        )

        with pytest.raises(ValueError, match="no transcript or slides"):
            podcast_usecase.generate(request)

    @pytest.mark.unit
    def test_generate_calls_three_stage_pipeline(
        self,
        podcast_usecase: PodcastUseCase,
        mock_llm: MagicMock,
    ) -> None:
        """generate() should call LLM three times (extraction, dialogue, dramatize)."""
        request = GeneratePodcastRequest(
            content_id="test-content-id",
            language="en",
        )

        podcast_usecase.generate(request)

        # 3 LLM calls: extraction, dialogue, dramatization
        assert mock_llm.complete.call_count == 3

    @pytest.mark.unit
    def test_generate_saves_result(
        self,
        podcast_usecase: PodcastUseCase,
        mock_podcast_storage: MagicMock,
    ) -> None:
        request = GeneratePodcastRequest(
            content_id="test-content-id",
            language="en",
        )

        podcast_usecase.generate(request)

        mock_podcast_storage.save.assert_called_once()
        call_args = mock_podcast_storage.save.call_args
        assert call_args[0][0] == "test-content-id"
        assert call_args[0][1] == "en"

    @pytest.mark.unit
    def test_generate_uses_parallel_tts(
        self,
        podcast_usecase: PodcastUseCase,
        mock_parallel_runner: MagicMock,
    ) -> None:
        """generate() should use parallel_runner for TTS synthesis."""
        request = GeneratePodcastRequest(
            content_id="test-content-id",
            language="en",
        )

        podcast_usecase.generate(request)

        mock_parallel_runner.map_ordered.assert_called()
        call_kwargs = mock_parallel_runner.map_ordered.call_args
        assert call_kwargs[1]["group"] == "podcast_tts"
