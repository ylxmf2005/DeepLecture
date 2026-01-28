"""Unit tests for QuizUseCase."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from deeplecture.use_cases.dto.quiz import (
    GenerateQuizRequest,
    QuizItem,
    QuizStats,
)
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
    storage.load.return_value = (
        [
            {"start": 0.0, "end": 5.0, "text": "Introduction to relativity."},
            {"start": 5.0, "end": 10.0, "text": "E equals mc squared."},
        ],
        datetime.now(timezone.utc),
    )
    return storage


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create mock LLM provider."""
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
    llm.complete = AsyncMock(side_effect=[extraction_response, quiz_response])
    return llm


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    """Create mock path resolver."""
    return MagicMock()


@pytest.fixture
def quiz_usecase(
    mock_quiz_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_llm: MagicMock,
    mock_path_resolver: MagicMock,
) -> QuizUseCase:
    """Create QuizUseCase with mocked dependencies."""
    return QuizUseCase(
        quiz_storage=mock_quiz_storage,
        subtitle_storage=mock_subtitle_storage,
        llm_provider=mock_llm,
        path_resolver=mock_path_resolver,
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
    ) -> None:
        """generate() should create quiz from subtitles."""
        import asyncio

        request = GenerateQuizRequest(
            content_id="test-content-id",
            language="en",
            question_count=5,
        )

        result = asyncio.get_event_loop().run_until_complete(quiz_usecase.generate(request))

        assert result.content_id == "test-content-id"
        assert len(result.items) >= 1
        mock_quiz_storage.save.assert_called_once()

    @pytest.mark.unit
    def test_generate_filters_invalid_items(
        self,
        quiz_usecase: QuizUseCase,
        mock_llm: MagicMock,
    ) -> None:
        """generate() should filter out invalid quiz items."""
        import asyncio

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
        mock_llm.complete = AsyncMock(side_effect=[extraction_response, quiz_response])

        request = GenerateQuizRequest(
            content_id="test-content-id",
            language="en",
            question_count=3,
        )

        result = asyncio.get_event_loop().run_until_complete(quiz_usecase.generate(request))

        # Only the valid item should remain
        assert len(result.items) == 1
        assert result.items[0].stem == "Valid question?"

    @pytest.mark.unit
    def test_generate_raises_when_no_context(
        self,
        quiz_usecase: QuizUseCase,
        mock_subtitle_storage: MagicMock,
    ) -> None:
        """generate() should raise when no content available."""
        import asyncio

        mock_subtitle_storage.load.return_value = None

        request = GenerateQuizRequest(
            content_id="empty-content-id",
            language="en",
        )

        with pytest.raises(ValueError, match="No content available"):
            asyncio.get_event_loop().run_until_complete(quiz_usecase.generate(request))


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
