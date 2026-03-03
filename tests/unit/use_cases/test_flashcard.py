"""Unit tests for FlashcardUseCase."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from deeplecture.domain import Segment
from deeplecture.use_cases.dto.flashcard import (
    FlashcardItem,
    FlashcardStats,
    GenerateFlashcardRequest,
)
from deeplecture.use_cases.flashcard import FlashcardUseCase, validate_flashcard_item
from deeplecture.use_cases.interfaces.prompt_registry import PromptSpec

# =============================================================================
# Validation Tests
# =============================================================================


class TestValidateFlashcardItem:
    """Tests for validate_flashcard_item() function."""

    @pytest.mark.unit
    def test_valid_item(self) -> None:
        """validate_flashcard_item() should accept valid items."""
        item = {
            "front": "What is E=mc²?",
            "back": "Mass-energy equivalence.",
            "source_timestamp": 135.0,
            "source_category": "formula",
        }
        is_valid, error = validate_flashcard_item(item)
        assert is_valid is True
        assert error == ""

    @pytest.mark.unit
    def test_valid_item_without_timestamp(self) -> None:
        """validate_flashcard_item() should accept items with null timestamp."""
        item = {
            "front": "What is photosynthesis?",
            "back": "The process by which plants convert light into energy.",
            "source_timestamp": None,
        }
        is_valid, error = validate_flashcard_item(item)
        assert is_valid is True
        assert error == ""

    @pytest.mark.unit
    def test_missing_front(self) -> None:
        """validate_flashcard_item() should reject items with missing front."""
        item = {"back": "An answer", "source_timestamp": 0.0}
        is_valid, error = validate_flashcard_item(item)
        assert is_valid is False
        assert "front" in error

    @pytest.mark.unit
    def test_empty_front(self) -> None:
        """validate_flashcard_item() should reject items with empty front."""
        item = {"front": "", "back": "An answer"}
        is_valid, error = validate_flashcard_item(item)
        assert is_valid is False
        assert "front" in error

    @pytest.mark.unit
    def test_missing_back(self) -> None:
        """validate_flashcard_item() should reject items with missing back."""
        item = {"front": "A question?"}
        is_valid, error = validate_flashcard_item(item)
        assert is_valid is False
        assert "back" in error

    @pytest.mark.unit
    def test_negative_timestamp(self) -> None:
        """validate_flashcard_item() should reject negative timestamps."""
        item = {
            "front": "Question?",
            "back": "Answer",
            "source_timestamp": -5.0,
        }
        is_valid, error = validate_flashcard_item(item)
        assert is_valid is False
        assert "source_timestamp" in error

    @pytest.mark.unit
    def test_string_timestamp(self) -> None:
        """validate_flashcard_item() should reject non-numeric timestamps."""
        item = {
            "front": "Question?",
            "back": "Answer",
            "source_timestamp": "00:01:30",
        }
        is_valid, error = validate_flashcard_item(item)
        assert is_valid is False
        assert "source_timestamp" in error


# =============================================================================
# FlashcardItem DTO Tests
# =============================================================================


class TestFlashcardItemDTO:
    """Tests for FlashcardItem dataclass."""

    @pytest.mark.unit
    def test_to_dict(self) -> None:
        """FlashcardItem.to_dict() should serialize correctly."""
        item = FlashcardItem(
            front="What is 2 + 2?",
            back="4",
            source_timestamp=10.0,
            source_category="formula",
        )
        result = item.to_dict()
        assert result["front"] == "What is 2 + 2?"
        assert result["back"] == "4"
        assert result["source_timestamp"] == 10.0
        assert result["source_category"] == "formula"

    @pytest.mark.unit
    def test_from_dict(self) -> None:
        """FlashcardItem.from_dict() should parse correctly."""
        data = {
            "front": "Question?",
            "back": "Answer",
            "source_timestamp": 42.0,
            "source_category": "definition",
        }
        item = FlashcardItem.from_dict(data)
        assert item.front == "Question?"
        assert item.back == "Answer"
        assert item.source_timestamp == 42.0
        assert item.source_category == "definition"

    @pytest.mark.unit
    def test_from_dict_defaults(self) -> None:
        """FlashcardItem.from_dict() should handle missing optional fields."""
        data = {"front": "Q?", "back": "A"}
        item = FlashcardItem.from_dict(data)
        assert item.source_timestamp is None
        assert item.source_category is None


# =============================================================================
# FlashcardStats Tests
# =============================================================================


class TestFlashcardStats:
    """Tests for FlashcardStats."""

    @pytest.mark.unit
    def test_stats_to_dict(self) -> None:
        """FlashcardStats.to_dict() should serialize correctly."""
        stats = FlashcardStats(
            total_items=10,
            valid_items=8,
            filtered_items=2,
            by_category={"formula": 3, "definition": 5},
        )
        result = stats.to_dict()
        assert result["total_items"] == 10
        assert result["valid_items"] == 8
        assert result["filtered_items"] == 2
        assert result["by_category"]["formula"] == 3


# =============================================================================
# FlashcardUseCase Tests
# =============================================================================


@pytest.fixture
def mock_flashcard_storage() -> MagicMock:
    """Create mock flashcard storage."""
    storage = MagicMock()
    storage.load.return_value = None
    storage.exists.return_value = False
    return storage


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage with timestamped segments."""
    storage = MagicMock()
    segments = [
        Segment(start=0.0, end=5.0, text="Introduction to relativity."),
        Segment(start=5.0, end=10.0, text="E equals mc squared."),
        Segment(start=135.0, end=140.0, text="This is the mass-energy equivalence."),
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
    """Create mock LLM instance for two-stage pipeline."""
    llm = MagicMock()
    # Stage 1: Knowledge extraction (with source_start timestamps)
    extraction_response = json.dumps(
        [
            {
                "category": "formula",
                "content": "E = mc²",
                "criticality": "high",
                "tags": ["physics"],
                "source_start": 5.0,
            },
            {
                "category": "definition",
                "content": "Mass-energy equivalence",
                "criticality": "medium",
                "tags": ["physics"],
                "source_start": 135.0,
            },
        ]
    )
    # Stage 2: Flashcard generation
    flashcard_response = json.dumps(
        [
            {
                "front": "What is the formula for mass-energy equivalence?",
                "back": "E = mc², where E is energy, m is mass, and c is the speed of light.",
                "source_timestamp": 5.0,
                "source_category": "formula",
            },
            {
                "front": "What does mass-energy equivalence mean?",
                "back": "It means mass and energy are interchangeable — mass can be converted to energy and vice versa.",
                "source_timestamp": 135.0,
                "source_category": "definition",
            },
        ]
    )
    llm.complete.side_effect = [extraction_response, flashcard_response]
    return llm


@pytest.fixture
def mock_llm_provider(mock_llm: MagicMock) -> MagicMock:
    """Create mock LLM provider."""
    provider = MagicMock()
    provider.get.return_value = mock_llm
    return provider


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    """Create mock path resolver."""
    return MagicMock()


@pytest.fixture
def mock_metadata_storage() -> MagicMock:
    """Create mock metadata storage."""
    storage = MagicMock()
    storage.get.return_value = None
    return storage


@pytest.fixture
def mock_pdf_text_extractor() -> MagicMock:
    """Create mock PDF text extractor."""
    extractor = MagicMock()
    extractor.extract_text.return_value = ""
    return extractor


@pytest.fixture
def mock_prompt_registry() -> MagicMock:
    """Create mock prompt registry."""
    registry = MagicMock()
    builder = MagicMock()
    builder.build.return_value = PromptSpec(
        user_prompt="test user prompt",
        system_prompt="test system prompt",
    )
    registry.get.return_value = builder
    return registry


@pytest.fixture
def flashcard_usecase(
    mock_flashcard_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_llm_provider: MagicMock,
    mock_path_resolver: MagicMock,
    mock_prompt_registry: MagicMock,
    mock_metadata_storage: MagicMock,
    mock_pdf_text_extractor: MagicMock,
) -> FlashcardUseCase:
    """Create FlashcardUseCase with mocked dependencies."""
    return FlashcardUseCase(
        flashcard_storage=mock_flashcard_storage,
        subtitle_storage=mock_subtitle_storage,
        llm_provider=mock_llm_provider,
        path_resolver=mock_path_resolver,
        prompt_registry=mock_prompt_registry,
        metadata_storage=mock_metadata_storage,
        pdf_text_extractor=mock_pdf_text_extractor,
    )


class TestFlashcardUseCaseGet:
    """Tests for get() method."""

    @pytest.mark.unit
    def test_get_returns_empty_when_not_found(
        self,
        flashcard_usecase: FlashcardUseCase,
        mock_flashcard_storage: MagicMock,
    ) -> None:
        """get() should return empty result when flashcards don't exist."""
        mock_flashcard_storage.load.return_value = None

        result = flashcard_usecase.get("test-content-id", "en")

        assert result.content_id == "test-content-id"
        assert result.items == []

    @pytest.mark.unit
    def test_get_returns_stored_flashcards(
        self,
        flashcard_usecase: FlashcardUseCase,
        mock_flashcard_storage: MagicMock,
    ) -> None:
        """get() should return stored flashcards when they exist."""
        stored_data = {
            "items": [
                {
                    "front": "What is gravity?",
                    "back": "A fundamental force of attraction between masses.",
                    "source_timestamp": 42.0,
                    "source_category": "definition",
                }
            ],
            "language": "en",
        }
        mock_flashcard_storage.load.return_value = (
            stored_data,
            datetime.now(timezone.utc),
        )

        result = flashcard_usecase.get("test-content-id", "en")

        assert result.content_id == "test-content-id"
        assert len(result.items) == 1
        assert result.items[0].front == "What is gravity?"
        assert result.items[0].source_timestamp == 42.0


class TestFlashcardUseCaseGenerate:
    """Tests for generate() method."""

    @pytest.mark.unit
    def test_generate_creates_flashcards(
        self,
        flashcard_usecase: FlashcardUseCase,
        mock_flashcard_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
        mock_prompt_registry: MagicMock,
    ) -> None:
        """generate() should create flashcards from subtitles."""
        request = GenerateFlashcardRequest(
            content_id="test-content-id",
            language="en",
        )

        result = flashcard_usecase.generate(request)

        assert result.content_id == "test-content-id"
        assert len(result.items) == 2
        assert result.items[0].source_timestamp == 5.0
        assert result.items[1].source_timestamp == 135.0
        mock_flashcard_storage.save.assert_called_once()

        build_calls = mock_prompt_registry.get.return_value.build.call_args_list
        assert any(call.kwargs.get("coverage_mode") == "comprehensive" for call in build_calls)

    @pytest.mark.unit
    def test_generate_filters_invalid_items(
        self,
        flashcard_usecase: FlashcardUseCase,
        mock_llm: MagicMock,
    ) -> None:
        """generate() should filter out invalid flashcard items."""
        extraction_response = json.dumps(
            [{"category": "formula", "content": "Test", "criticality": "high", "tags": []}]
        )
        flashcard_response = json.dumps(
            [
                {
                    "front": "Valid question?",
                    "back": "Valid answer.",
                    "source_timestamp": 10.0,
                    "source_category": "formula",
                },
                {
                    "front": "",  # Empty front — invalid
                    "back": "Some answer",
                },
                {
                    "front": "Another question?",
                    "back": "",  # Empty back — invalid
                },
            ]
        )
        mock_llm.complete.side_effect = [extraction_response, flashcard_response]

        request = GenerateFlashcardRequest(
            content_id="test-content-id",
            language="en",
        )

        result = flashcard_usecase.generate(request)

        assert len(result.items) == 1
        assert result.items[0].front == "Valid question?"
        assert result.stats.filtered_items == 2

    @pytest.mark.unit
    def test_generate_raises_when_no_context(
        self,
        flashcard_usecase: FlashcardUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
    ) -> None:
        """generate() should raise when no content available."""
        mock_subtitle_storage.list_languages.return_value = []
        mock_pdf_text_extractor.extract_text.return_value = ""

        request = GenerateFlashcardRequest(
            content_id="empty-content-id",
            language="en",
        )

        with pytest.raises(ValueError, match="no transcript or slides"):
            flashcard_usecase.generate(request)

    @pytest.mark.unit
    def test_generate_uses_slide_context(
        self,
        flashcard_usecase: FlashcardUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
        mock_path_resolver: MagicMock,
    ) -> None:
        """Mode 'slide' should generate from PDF when subtitles missing."""
        mock_subtitle_storage.list_languages.return_value = []
        mock_path_resolver.build_content_path.side_effect = (
            lambda content_id, *parts: f"/tmp/{content_id}/{'/'.join(parts)}"
        )
        mock_pdf_text_extractor.extract_text.side_effect = (
            lambda path: "Slide text content" if path.endswith("source.pdf") else ""
        )

        request = GenerateFlashcardRequest(
            content_id="test-content-id",
            language="en",
            context_mode="slide",
        )

        result = flashcard_usecase.generate(request)

        assert result.used_sources == ["slide"]
        assert len(result.items) >= 1

    @pytest.mark.unit
    def test_generate_raises_when_slide_missing(
        self,
        flashcard_usecase: FlashcardUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
    ) -> None:
        """Mode 'slide' should fail when no slides exist."""
        mock_subtitle_storage.list_languages.return_value = []
        mock_pdf_text_extractor.extract_text.return_value = ""

        request = GenerateFlashcardRequest(
            content_id="empty-content-id",
            language="en",
            context_mode="slide",
        )

        with pytest.raises(ValueError, match="Requested slide context"):
            flashcard_usecase.generate(request)

    @pytest.mark.unit
    def test_generate_criticality_filtering(
        self,
        flashcard_usecase: FlashcardUseCase,
        mock_llm: MagicMock,
    ) -> None:
        """generate() should respect min_criticality filter."""
        extraction_response = json.dumps(
            [
                {"category": "formula", "content": "High", "criticality": "high", "tags": []},
                {"category": "note", "content": "Low", "criticality": "low", "tags": []},
            ]
        )
        flashcard_response = json.dumps(
            [
                {
                    "front": "High-criticality question?",
                    "back": "High-criticality answer.",
                    "source_timestamp": None,
                    "source_category": "formula",
                }
            ]
        )
        mock_llm.complete.side_effect = [extraction_response, flashcard_response]

        request = GenerateFlashcardRequest(
            content_id="test-content-id",
            language="en",
            min_criticality="high",
        )

        result = flashcard_usecase.generate(request)

        # The "low" item should be filtered out before Stage 2
        assert len(result.items) >= 1


class TestFlashcardTimestamps:
    """Tests for timestamp handling in flashcard generation."""

    @pytest.mark.unit
    def test_subtitle_context_has_timestamps(
        self,
        flashcard_usecase: FlashcardUseCase,
    ) -> None:
        """_load_subtitle_context_with_timestamps() should format segments with [HH:MM:SS]."""
        text = flashcard_usecase._load_subtitle_context_with_timestamps("test-content-id")

        assert "[00:00:00]" in text
        assert "[00:00:05]" in text
        assert "[00:02:15]" in text
        assert "Introduction to relativity." in text

    @pytest.mark.unit
    def test_subtitle_context_empty_for_missing_content(
        self,
        flashcard_usecase: FlashcardUseCase,
    ) -> None:
        """_load_subtitle_context_with_timestamps() should return empty for missing content."""
        text = flashcard_usecase._load_subtitle_context_with_timestamps("nonexistent-id")

        assert text == ""
