"""Unit tests for QuizUseCase."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from deeplecture.domain import Segment
from deeplecture.use_cases.dto.quiz import (
    GenerateQuizRequest,
    QuizItem,
    QuizStats,
)
from deeplecture.use_cases.interfaces.prompt_registry import PromptSpec
from deeplecture.use_cases.quiz import QuizUseCase, validate_quiz_item

# =============================================================================
# Validation Tests
# =============================================================================


class TestValidateQuizItem:
    """Tests for validate_quiz_item() function."""

    @pytest.mark.unit
    def test_valid_item(self) -> None:
        """validate_quiz_item() should accept valid items."""
        item = {
            "stem": "What is 2 + 2?",
            "options": ["A. 3", "B. 4", "C. 5", "D. 6"],
            "answer_index": 1,
            "explanation": "2 + 2 = 4",
        }
        is_valid, error = validate_quiz_item(item)
        assert is_valid is True
        assert error == ""

    @pytest.mark.unit
    def test_wrong_option_count(self) -> None:
        """validate_quiz_item() should reject items with != 4 options."""
        item = {
            "stem": "Question?",
            "options": ["A", "B", "C"],  # Only 3 options
            "answer_index": 0,
            "explanation": "Explanation",
        }
        is_valid, error = validate_quiz_item(item)
        assert is_valid is False
        assert "4 items" in error

    @pytest.mark.unit
    def test_answer_index_out_of_range(self) -> None:
        """validate_quiz_item() should reject answer_index outside 0-3."""
        item = {
            "stem": "Question?",
            "options": ["A", "B", "C", "D"],
            "answer_index": 4,  # Out of range
            "explanation": "Explanation",
        }
        is_valid, error = validate_quiz_item(item)
        assert is_valid is False
        assert "0-3" in error

    @pytest.mark.unit
    def test_negative_answer_index(self) -> None:
        """validate_quiz_item() should reject negative answer_index."""
        item = {
            "stem": "Question?",
            "options": ["A", "B", "C", "D"],
            "answer_index": -1,
            "explanation": "Explanation",
        }
        is_valid, error = validate_quiz_item(item)
        assert is_valid is False
        assert "0-3" in error

    @pytest.mark.unit
    def test_duplicate_options(self) -> None:
        """validate_quiz_item() should reject duplicate options."""
        item = {
            "stem": "Question?",
            "options": ["A", "A", "B", "C"],  # Duplicate "A"
            "answer_index": 0,
            "explanation": "Explanation",
        }
        is_valid, error = validate_quiz_item(item)
        assert is_valid is False
        assert "duplicate" in error.lower()

    @pytest.mark.unit
    def test_missing_required_field(self) -> None:
        """validate_quiz_item() should reject items missing required fields."""
        item = {
            "stem": "Question?",
            "options": ["A", "B", "C", "D"],
            "answer_index": 0,
            # Missing "explanation"
        }
        is_valid, error = validate_quiz_item(item)
        assert is_valid is False
        assert "explanation" in error

    @pytest.mark.unit
    def test_empty_stem(self) -> None:
        """validate_quiz_item() should reject empty stem."""
        item = {
            "stem": "",  # Empty
            "options": ["A", "B", "C", "D"],
            "answer_index": 0,
            "explanation": "Explanation",
        }
        is_valid, error = validate_quiz_item(item)
        assert is_valid is False
        assert "stem" in error

    @pytest.mark.unit
    def test_string_answer_index(self) -> None:
        """validate_quiz_item() should reject non-integer answer_index."""
        item = {
            "stem": "Question?",
            "options": ["A", "B", "C", "D"],
            "answer_index": "0",  # String, not int
            "explanation": "Explanation",
        }
        is_valid, error = validate_quiz_item(item)
        assert is_valid is False
        assert "0-3" in error


# =============================================================================
# QuizItem DTO Tests
# =============================================================================


class TestQuizItemDTO:
    """Tests for QuizItem dataclass."""

    @pytest.mark.unit
    def test_to_dict(self) -> None:
        """QuizItem.to_dict() should serialize correctly."""
        item = QuizItem(
            stem="What is 2 + 2?",
            options=["A. 3", "B. 4", "C. 5", "D. 6"],
            answer_index=1,
            explanation="2 + 2 = 4",
            source_category="formula",
            source_tags=["math", "arithmetic"],
        )
        result = item.to_dict()
        assert result["stem"] == "What is 2 + 2?"
        assert result["options"] == ["A. 3", "B. 4", "C. 5", "D. 6"]
        assert result["answer_index"] == 1
        assert result["explanation"] == "2 + 2 = 4"
        assert result["source_category"] == "formula"
        assert result["source_tags"] == ["math", "arithmetic"]

    @pytest.mark.unit
    def test_from_dict(self) -> None:
        """QuizItem.from_dict() should parse correctly."""
        data = {
            "stem": "Question?",
            "options": ["A", "B", "C", "D"],
            "answer_index": 2,
            "explanation": "Answer is C",
            "source_category": "definition",
            "source_tags": ["vocab"],
        }
        item = QuizItem.from_dict(data)
        assert item.stem == "Question?"
        assert item.answer_index == 2
        assert item.source_category == "definition"


# =============================================================================
# QuizUseCase Tests
# =============================================================================


@pytest.fixture
def mock_quiz_storage() -> MagicMock:
    """Create mock quiz storage."""
    storage = MagicMock()
    storage.load.return_value = None
    storage.exists.return_value = False
    return storage


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage."""
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
    """Create mock LLM instance."""
    llm = MagicMock()
    # Mock for knowledge extraction (first call)
    extraction_response = json.dumps(
        [
            {
                "category": "formula",
                "content": "E = mc²",
                "criticality": "high",
                "tags": ["physics"],
            }
        ]
    )
    # Mock for quiz generation (second call)
    quiz_response = json.dumps(
        [
            {
                "stem": "What does E represent in E=mc²?",
                "options": ["A. Energy", "B. Mass", "C. Speed", "D. Distance"],
                "answer_index": 0,
                "explanation": "E represents Energy. B is wrong (m is mass), C is wrong (c is speed of light), D is wrong (not in formula).",
                "source_category": "formula",
                "source_tags": ["physics"],
            }
        ]
    )
    llm.complete.side_effect = [extraction_response, quiz_response]
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
def quiz_usecase(
    mock_quiz_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_llm_provider: MagicMock,
    mock_path_resolver: MagicMock,
    mock_prompt_registry: MagicMock,
    mock_metadata_storage: MagicMock,
    mock_pdf_text_extractor: MagicMock,
) -> QuizUseCase:
    """Create QuizUseCase with mocked dependencies."""
    return QuizUseCase(
        quiz_storage=mock_quiz_storage,
        subtitle_storage=mock_subtitle_storage,
        llm_provider=mock_llm_provider,
        path_resolver=mock_path_resolver,
        prompt_registry=mock_prompt_registry,
        metadata_storage=mock_metadata_storage,
        pdf_text_extractor=mock_pdf_text_extractor,
    )


class TestQuizUseCaseGet:
    """Tests for get() method."""

    @pytest.mark.unit
    def test_get_returns_none_when_not_found(
        self,
        quiz_usecase: QuizUseCase,
        mock_quiz_storage: MagicMock,
    ) -> None:
        """get() should return empty result when quiz doesn't exist."""
        mock_quiz_storage.load.return_value = None

        result = quiz_usecase.get("test-content-id", "en")

        assert result.content_id == "test-content-id"
        assert result.items == []

    @pytest.mark.unit
    def test_get_returns_stored_quiz(
        self,
        quiz_usecase: QuizUseCase,
        mock_quiz_storage: MagicMock,
    ) -> None:
        """get() should return stored quiz when it exists."""
        stored_data = {
            "items": [
                {
                    "stem": "Test question?",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 0,
                    "explanation": "A is correct",
                    "source_category": "definition",
                    "source_tags": [],
                }
            ],
            "language": "en",
        }
        mock_quiz_storage.load.return_value = (
            stored_data,
            datetime.now(timezone.utc),
        )

        result = quiz_usecase.get("test-content-id", "en")

        assert result.content_id == "test-content-id"
        assert len(result.items) == 1
        assert result.items[0].stem == "Test question?"


class TestQuizUseCaseGenerate:
    """Tests for generate() method."""

    @pytest.mark.unit
    def test_generate_creates_quiz(
        self,
        quiz_usecase: QuizUseCase,
        mock_quiz_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
        mock_prompt_registry: MagicMock,
    ) -> None:
        """generate() should create quiz from subtitles."""
        request = GenerateQuizRequest(
            content_id="test-content-id",
            language="en",
        )

        result = quiz_usecase.generate(request)

        assert result.content_id == "test-content-id"
        assert len(result.items) >= 1
        mock_quiz_storage.save.assert_called_once()
        mock_pdf_text_extractor.extract_text.assert_called()

        build_calls = mock_prompt_registry.get.return_value.build.call_args_list
        assert any(call.kwargs.get("coverage_mode") == "comprehensive" for call in build_calls)
        assert any(call.kwargs.get("question_count") == 6 for call in build_calls)

    @pytest.mark.unit
    def test_generate_filters_invalid_items(
        self,
        quiz_usecase: QuizUseCase,
        mock_llm: MagicMock,
    ) -> None:
        """generate() should filter out invalid quiz items."""
        # Return mix of valid and invalid items
        extraction_response = json.dumps(
            [{"category": "formula", "content": "Test", "criticality": "high", "tags": []}]
        )
        quiz_response = json.dumps(
            [
                {
                    "stem": "Valid question?",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 0,
                    "explanation": "Correct",
                },
                {
                    "stem": "Invalid - wrong option count",
                    "options": ["A", "B"],  # Only 2 options
                    "answer_index": 0,
                    "explanation": "Bad",
                },
                {
                    "stem": "Invalid - bad index",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 5,  # Out of range
                    "explanation": "Bad",
                },
            ]
        )
        mock_llm.complete.side_effect = [extraction_response, quiz_response]

        request = GenerateQuizRequest(
            content_id="test-content-id",
            language="en",
        )

        result = quiz_usecase.generate(request)

        # Only the valid item should remain
        assert len(result.items) == 1
        assert result.items[0].stem == "Valid question?"

    @pytest.mark.unit
    def test_generate_raises_when_no_context(
        self,
        quiz_usecase: QuizUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
    ) -> None:
        """generate() should raise when no content available."""
        mock_subtitle_storage.list_languages.return_value = []
        mock_pdf_text_extractor.extract_text.return_value = ""

        request = GenerateQuizRequest(
            content_id="empty-content-id",
            language="en",
        )

        with pytest.raises(ValueError, match="no transcript or slides"):
            quiz_usecase.generate(request)

    @pytest.mark.unit
    def test_generate_uses_slide_context_when_requested(
        self,
        quiz_usecase: QuizUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
        mock_path_resolver: MagicMock,
    ) -> None:
        """Mode 'slide' should generate quiz from PDF text when subtitles are missing."""
        mock_subtitle_storage.list_languages.return_value = []
        mock_path_resolver.build_content_path.side_effect = (
            lambda content_id, *parts: f"/tmp/{content_id}/{'/'.join(parts)}"
        )
        mock_pdf_text_extractor.extract_text.side_effect = (
            lambda path: "Slide text content" if path.endswith("source.pdf") else ""
        )

        request = GenerateQuizRequest(
            content_id="test-content-id",
            language="en",
            context_mode="slide",
        )

        result = quiz_usecase.generate(request)

        assert result.used_sources == ["slide"]
        assert len(result.items) >= 1

    @pytest.mark.unit
    def test_generate_raises_when_slide_requested_but_missing(
        self,
        quiz_usecase: QuizUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
    ) -> None:
        """Mode 'slide' should fail when no readable slide text exists."""
        mock_subtitle_storage.list_languages.return_value = []
        mock_pdf_text_extractor.extract_text.return_value = ""

        request = GenerateQuizRequest(
            content_id="empty-content-id",
            language="en",
            context_mode="slide",
        )

        with pytest.raises(ValueError, match="Requested slide context"):
            quiz_usecase.generate(request)


class TestQuizStats:
    """Tests for QuizStats."""

    @pytest.mark.unit
    def test_stats_to_dict(self) -> None:
        """QuizStats.to_dict() should serialize correctly."""
        stats = QuizStats(
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


class TestQuizAutoQuestionCount:
    """Tests for auto question count strategy."""

    @pytest.mark.unit
    def test_auto_question_count_has_minimum_floor(self) -> None:
        assert QuizUseCase._resolve_auto_question_count(0) == 6
        assert QuizUseCase._resolve_auto_question_count(3) == 6

    @pytest.mark.unit
    def test_auto_question_count_scales_and_caps(self) -> None:
        assert QuizUseCase._resolve_auto_question_count(10) == 15
        assert QuizUseCase._resolve_auto_question_count(100) == 40
