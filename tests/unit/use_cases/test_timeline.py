"""Unit tests for TimelineUseCase."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deeplecture.config import TimelineConfig
from deeplecture.domain import ContentMetadata, ContentType, Segment
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.timeline import (
    GenerateTimelineRequest,
)
from deeplecture.use_cases.timeline import TimelineUseCase


@pytest.fixture
def mock_metadata_storage() -> MagicMock:
    """Create mock metadata storage."""
    storage = MagicMock()
    storage.get.return_value = ContentMetadata(
        id="test-content-id",
        type=ContentType.VIDEO,
        original_filename="test.mp4",
        source_file="/tmp/test.mp4",
    )
    return storage


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage."""
    storage = MagicMock()
    storage.load.return_value = [
        Segment(start=0.0, end=5.0, text="Introduction to the topic."),
        Segment(start=5.0, end=10.0, text="First point of discussion."),
        Segment(start=10.0, end=15.0, text="Second point of discussion."),
    ]
    return storage


@pytest.fixture
def mock_timeline_storage() -> MagicMock:
    """Create mock timeline storage."""
    return MagicMock()


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create mock LLM service."""
    llm = MagicMock()
    llm.complete.return_value = """{
        "segments": [
            {"title": "Introduction", "start_id": 1, "end_id": 1},
            {"title": "Main Content", "start_id": 2, "end_id": 3}
        ]
    }"""
    return llm


@pytest.fixture
def mock_parallel_runner() -> MagicMock:
    """Create mock parallel runner."""
    runner = MagicMock()
    runner.run.side_effect = lambda tasks: [task() for task in tasks]
    return runner


@pytest.fixture
def config() -> TimelineConfig:
    """Create default config."""
    return TimelineConfig()


@pytest.fixture
def usecase(
    mock_metadata_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_timeline_storage: MagicMock,
    mock_llm: MagicMock,
    config: TimelineConfig,
    mock_parallel_runner: MagicMock,
) -> TimelineUseCase:
    """Create TimelineUseCase with mocked dependencies."""
    return TimelineUseCase(
        metadata_storage=mock_metadata_storage,
        subtitle_storage=mock_subtitle_storage,
        timeline_storage=mock_timeline_storage,
        llm=mock_llm,
        config=config,
        parallel_runner=mock_parallel_runner,
    )


class TestTimelineUseCaseGetTimeline:
    """Tests for get_timeline() method."""

    @pytest.mark.unit
    def test_get_timeline_success(
        self,
        usecase: TimelineUseCase,
        mock_timeline_storage: MagicMock,
    ) -> None:
        """get_timeline() should return timeline when it exists."""
        mock_timeline_storage.load.return_value = {
            "status": "ready",
            "timeline": [
                {
                    "title": "Introduction",
                    "startTime": 0.0,
                    "endTime": 5.0,
                    "content": "Overview of the topic",
                },
            ],
        }

        result = usecase.get_timeline("test-content-id", "en")

        assert result is not None
        assert result.content_id == "test-content-id"
        assert result.cached is True
        assert result.status == "ready"

    @pytest.mark.unit
    def test_get_timeline_not_found(
        self,
        usecase: TimelineUseCase,
        mock_timeline_storage: MagicMock,
    ) -> None:
        """get_timeline() should return None when not found."""
        mock_timeline_storage.load.return_value = None

        result = usecase.get_timeline("test-content-id", "en")

        assert result is None


class TestTimelineUseCaseGenerate:
    """Tests for generate() method."""

    @pytest.mark.unit
    def test_generate_content_not_found(
        self,
        usecase: TimelineUseCase,
        mock_metadata_storage: MagicMock,
    ) -> None:
        """generate() should raise when content doesn't exist."""
        mock_metadata_storage.get.return_value = None

        request = GenerateTimelineRequest(
            content_id="nonexistent-id",
            language="en",
        )

        with pytest.raises(ContentNotFoundError):
            usecase.generate(request)

    @pytest.mark.unit
    def test_generate_returns_cached_when_not_forced(
        self,
        usecase: TimelineUseCase,
        mock_timeline_storage: MagicMock,
    ) -> None:
        """generate() should return cached timeline when force=False."""
        mock_timeline_storage.load.return_value = {
            "status": "ready",
            "timeline": [
                {
                    "title": "Cached Entry",
                    "startTime": 0.0,
                    "endTime": 5.0,
                    "content": "Cached content",
                },
            ],
        }

        request = GenerateTimelineRequest(
            content_id="test-content-id",
            language="en",
            force=False,
        )
        result = usecase.generate(request)

        assert result.cached is True
        mock_timeline_storage.save.assert_not_called()
