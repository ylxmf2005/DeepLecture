"""Unit tests for TestPaperUseCase."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from deeplecture.domain import Segment
from deeplecture.use_cases.dto.test_paper import (
    GenerateTestPaperRequest,
)
from deeplecture.use_cases.dto.test_paper import (
    TestPaperStats as PaperStats,
)
from deeplecture.use_cases.dto.test_paper import (
    TestQuestion as PaperQuestion,
)
from deeplecture.use_cases.interfaces.prompt_registry import PromptSpec
from deeplecture.use_cases.test_paper import TestPaperUseCase as PaperUseCase
from deeplecture.use_cases.test_paper import validate_test_question


class TestValidateTestQuestion:
    """Tests for validate_test_question() function."""

    @pytest.mark.unit
    def test_valid_item(self) -> None:
        item = {
            "question_type": "short_answer",
            "stem": "Explain why mass-energy equivalence matters in physics.",
            "reference_answer": "Mass-energy equivalence explains that mass can be converted to energy, which underpins nuclear reactions and modern physics.",
            "scoring_criteria": ["Defines equivalence", "Gives concrete implication"],
            "bloom_level": "analyze",
            "source_timestamp": 120.0,
        }

        is_valid, error = validate_test_question(item)

        assert is_valid is True
        assert error == ""

    @pytest.mark.unit
    def test_missing_required_field(self) -> None:
        item = {
            "question_type": "essay",
            "stem": "Compare A and B concepts in detail.",
            "reference_answer": "Detailed answer here with enough length for validation.",
            "scoring_criteria": ["Point 1"],
            # bloom_level missing
        }

        is_valid, error = validate_test_question(item)

        assert is_valid is False
        assert "bloom_level" in error

    @pytest.mark.unit
    def test_rejects_short_stem(self) -> None:
        item = {
            "question_type": "essay",
            "stem": "Too short",
            "reference_answer": "This reference answer is long enough to pass reference length checks.",
            "scoring_criteria": ["Point 1"],
            "bloom_level": "apply",
        }

        is_valid, error = validate_test_question(item)

        assert is_valid is False
        assert "stem" in error

    @pytest.mark.unit
    def test_rejects_short_reference_answer(self) -> None:
        item = {
            "question_type": "essay",
            "stem": "Explain the practical effects of this principle in realistic settings.",
            "reference_answer": "Too short.",
            "scoring_criteria": ["Point 1"],
            "bloom_level": "apply",
        }

        is_valid, error = validate_test_question(item)

        assert is_valid is False
        assert "reference_answer" in error

    @pytest.mark.unit
    def test_rejects_invalid_bloom_level(self) -> None:
        item = {
            "question_type": "essay",
            "stem": "Explain the practical effects of this principle in realistic settings.",
            "reference_answer": "A valid long reference answer that clearly explains practical effects in detail.",
            "scoring_criteria": ["Point 1"],
            "bloom_level": "master",
        }

        is_valid, error = validate_test_question(item)

        assert is_valid is False
        assert "bloom_level" in error

    @pytest.mark.unit
    def test_accepts_bloom_level_case_insensitive(self) -> None:
        item = {
            "question_type": "essay",
            "stem": "Analyze the tradeoffs between these two implementation strategies carefully.",
            "reference_answer": "This reference answer is intentionally long to pass validation and includes reasoning details.",
            "scoring_criteria": ["Point 1", "Point 2"],
            "bloom_level": "  AnALyZe  ",
        }

        is_valid, error = validate_test_question(item)

        assert is_valid is True
        assert error == ""

    @pytest.mark.unit
    def test_rejects_empty_scoring_criteria(self) -> None:
        item = {
            "question_type": "essay",
            "stem": "Explain the practical effects of this principle in realistic settings.",
            "reference_answer": "A valid long reference answer that clearly explains practical effects in detail.",
            "scoring_criteria": [],
            "bloom_level": "apply",
        }

        is_valid, error = validate_test_question(item)

        assert is_valid is False
        assert "scoring_criteria" in error


class TestTestQuestionDTO:
    """Tests for TestQuestion dataclass."""

    @pytest.mark.unit
    def test_to_dict(self) -> None:
        question = PaperQuestion(
            question_type="case_analysis",
            stem="Analyze this case and propose a justified solution.",
            reference_answer="A complete reference answer with structured reasoning and evidence.",
            scoring_criteria=["Identifies core issue", "Proposes justified solution"],
            bloom_level="evaluate",
            source_timestamp=42.0,
            source_category="concept",
            source_tags=["analysis", "reasoning"],
        )

        result = question.to_dict()

        assert result["question_type"] == "case_analysis"
        assert result["stem"].startswith("Analyze this case")
        assert result["reference_answer"].startswith("A complete reference answer")
        assert result["scoring_criteria"] == ["Identifies core issue", "Proposes justified solution"]
        assert result["bloom_level"] == "evaluate"
        assert result["source_timestamp"] == 42.0
        assert result["source_category"] == "concept"
        assert result["source_tags"] == ["analysis", "reasoning"]

    @pytest.mark.unit
    def test_from_dict(self) -> None:
        data = {
            "question_type": "short_answer",
            "stem": "What is X and why does it matter?",
            "reference_answer": "X matters because it changes system behavior under constraints.",
            "scoring_criteria": ["Defines X", "Explains impact"],
            "bloom_level": "understand",
            "source_timestamp": 18.0,
            "source_category": "definition",
            "source_tags": ["fundamentals"],
        }

        question = PaperQuestion.from_dict(data)

        assert question.question_type == "short_answer"
        assert question.bloom_level == "understand"
        assert question.source_timestamp == 18.0

    @pytest.mark.unit
    def test_from_dict_defaults(self) -> None:
        data = {
            "question_type": "essay",
            "stem": "Discuss implications.",
            "reference_answer": "Long enough reference answer for default-field checks.",
            "scoring_criteria": ["One point"],
            "bloom_level": "analyze",
        }

        question = PaperQuestion.from_dict(data)

        assert question.source_timestamp is None
        assert question.source_category is None
        assert question.source_tags == []


@pytest.fixture
def mock_test_paper_storage() -> MagicMock:
    storage = MagicMock()
    storage.load.return_value = None
    storage.exists.return_value = False
    return storage


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    storage = MagicMock()
    segments = [
        Segment(start=0.0, end=5.0, text="Introduction to relativity."),
        Segment(start=120.0, end=125.0, text="Mass-energy equivalence implications."),
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

    extraction_response = json.dumps(
        [
            {
                "category": "concept",
                "content": "Mass-energy equivalence",
                "criticality": "high",
                "tags": ["physics"],
                "source_start": 120.0,
            },
            {
                "category": "application",
                "content": "Nuclear energy applications",
                "criticality": "medium",
                "tags": ["engineering"],
                "source_start": 180.0,
            },
        ]
    )

    generation_response = json.dumps(
        [
            {
                "question_type": "short_answer",
                "stem": "Explain mass-energy equivalence and give one practical implication.",
                "reference_answer": "Mass-energy equivalence means mass can be converted into energy. A practical implication is energy release in nuclear fission and fusion processes.",
                "scoring_criteria": [
                    "Defines equivalence correctly",
                    "Provides one practical implication",
                ],
                "bloom_level": "understand",
                "source_timestamp": 120.0,
                "source_category": "concept",
                "source_tags": ["physics"],
            },
            {
                "question_type": "essay",
                "stem": "Evaluate the ethical and technical tradeoffs of nuclear energy adoption.",
                "reference_answer": "A strong answer compares safety, waste, climate impact, and reliability, and then justifies a balanced policy recommendation.",
                "scoring_criteria": [
                    "Discusses both ethical and technical dimensions",
                    "Compares competing tradeoffs",
                    "Provides justified conclusion",
                ],
                "bloom_level": "evaluate",
                "source_timestamp": 180.0,
                "source_category": "application",
                "source_tags": ["engineering", "policy"],
            },
        ]
    )

    llm.complete.side_effect = [extraction_response, generation_response]
    return llm


@pytest.fixture
def mock_llm_provider(mock_llm: MagicMock) -> MagicMock:
    provider = MagicMock()
    provider.get.return_value = mock_llm
    return provider


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    return MagicMock()


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
def test_paper_usecase(
    mock_test_paper_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_llm_provider: MagicMock,
    mock_path_resolver: MagicMock,
    mock_prompt_registry: MagicMock,
    mock_metadata_storage: MagicMock,
    mock_pdf_text_extractor: MagicMock,
) -> PaperUseCase:
    return PaperUseCase(
        test_paper_storage=mock_test_paper_storage,
        subtitle_storage=mock_subtitle_storage,
        llm_provider=mock_llm_provider,
        path_resolver=mock_path_resolver,
        prompt_registry=mock_prompt_registry,
        metadata_storage=mock_metadata_storage,
        pdf_text_extractor=mock_pdf_text_extractor,
    )


class TestTestPaperUseCaseGet:
    @pytest.mark.unit
    def test_get_returns_empty_when_not_found(
        self,
        test_paper_usecase: PaperUseCase,
        mock_test_paper_storage: MagicMock,
    ) -> None:
        mock_test_paper_storage.load.return_value = None

        result = test_paper_usecase.get("test-content-id", "en")

        assert result.content_id == "test-content-id"
        assert result.questions == []

    @pytest.mark.unit
    def test_get_returns_stored_test_paper(
        self,
        test_paper_usecase: PaperUseCase,
        mock_test_paper_storage: MagicMock,
    ) -> None:
        stored_data = {
            "questions": [
                {
                    "question_type": "short_answer",
                    "stem": "What is gravity?",
                    "reference_answer": "Gravity is a force of attraction between masses in classical mechanics.",
                    "scoring_criteria": ["Defines gravity"],
                    "bloom_level": "understand",
                }
            ],
            "language": "en",
        }
        mock_test_paper_storage.load.return_value = (stored_data, datetime.now(timezone.utc))

        result = test_paper_usecase.get("test-content-id", "en")

        assert result.content_id == "test-content-id"
        assert len(result.questions) == 1
        assert result.questions[0].question_type == "short_answer"


class TestTestPaperUseCaseGenerate:
    @pytest.mark.unit
    def test_generate_creates_test_paper(
        self,
        test_paper_usecase: PaperUseCase,
        mock_test_paper_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
        mock_prompt_registry: MagicMock,
    ) -> None:
        request = GenerateTestPaperRequest(
            content_id="test-content-id",
            language="en",
        )

        result = test_paper_usecase.generate(request)

        assert result.content_id == "test-content-id"
        assert len(result.questions) == 2
        mock_test_paper_storage.save.assert_called_once()
        mock_pdf_text_extractor.extract_text.assert_called()

        build_calls = mock_prompt_registry.get.return_value.build.call_args_list
        assert any(call.kwargs.get("coverage_mode") == "exam_focused" for call in build_calls)

    @pytest.mark.unit
    def test_generate_filters_invalid_questions(
        self,
        test_paper_usecase: PaperUseCase,
        mock_llm: MagicMock,
    ) -> None:
        extraction_response = json.dumps(
            [{"category": "formula", "content": "Test", "criticality": "high", "tags": []}]
        )
        generation_response = json.dumps(
            [
                {
                    "question_type": "short_answer",
                    "stem": "Explain this concept with one practical implication.",
                    "reference_answer": "A sufficiently long reference answer that explains the concept and implication clearly.",
                    "scoring_criteria": ["Point 1"],
                    "bloom_level": "understand",
                },
                {
                    "question_type": "essay",
                    "stem": "Too short",
                    "reference_answer": "A sufficiently long reference answer for this invalid item.",
                    "scoring_criteria": ["Point 1"],
                    "bloom_level": "analyze",
                },
            ]
        )
        mock_llm.complete.side_effect = [extraction_response, generation_response]

        request = GenerateTestPaperRequest(
            content_id="test-content-id",
            language="en",
        )

        result = test_paper_usecase.generate(request)

        assert len(result.questions) == 1
        assert result.stats.filtered_questions == 1

    @pytest.mark.unit
    def test_generate_raises_when_no_context(
        self,
        test_paper_usecase: PaperUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
    ) -> None:
        mock_subtitle_storage.list_languages.return_value = []
        mock_pdf_text_extractor.extract_text.return_value = ""

        request = GenerateTestPaperRequest(
            content_id="empty-content-id",
            language="en",
        )

        with pytest.raises(ValueError, match="no transcript or slides"):
            test_paper_usecase.generate(request)

    @pytest.mark.unit
    def test_generate_uses_slide_context_when_requested(
        self,
        test_paper_usecase: PaperUseCase,
        mock_subtitle_storage: MagicMock,
        mock_pdf_text_extractor: MagicMock,
        mock_path_resolver: MagicMock,
    ) -> None:
        mock_subtitle_storage.list_languages.return_value = []
        mock_path_resolver.build_content_path.side_effect = (
            lambda content_id, *parts: f"/tmp/{content_id}/{'/'.join(parts)}"
        )
        mock_pdf_text_extractor.extract_text.side_effect = (
            lambda path: "Slide text content" if path.endswith("source.pdf") else ""
        )

        request = GenerateTestPaperRequest(
            content_id="test-content-id",
            language="en",
            context_mode="slide",
        )

        result = test_paper_usecase.generate(request)

        assert result.used_sources == ["slide"]
        assert len(result.questions) >= 1

    @pytest.mark.unit
    def test_generate_uses_both_sources_when_available(
        self,
        test_paper_usecase: PaperUseCase,
        mock_pdf_text_extractor: MagicMock,
        mock_path_resolver: MagicMock,
    ) -> None:
        mock_path_resolver.build_content_path.side_effect = (
            lambda content_id, *parts: f"/tmp/{content_id}/{'/'.join(parts)}"
        )
        mock_pdf_text_extractor.extract_text.side_effect = (
            lambda path: "Slide text content" if path.endswith("source.pdf") else ""
        )

        request = GenerateTestPaperRequest(
            content_id="test-content-id",
            language="en",
            context_mode="both",
        )

        result = test_paper_usecase.generate(request)

        assert "subtitle" in result.used_sources
        assert "slide" in result.used_sources

    @pytest.mark.unit
    def test_generate_passes_user_instruction_to_stage2(
        self,
        test_paper_usecase: PaperUseCase,
        mock_prompt_registry: MagicMock,
    ) -> None:
        request = GenerateTestPaperRequest(
            content_id="test-content-id",
            language="en",
            user_instruction="Focus on comparative analysis.",
        )

        test_paper_usecase.generate(request)

        build_calls = mock_prompt_registry.get.return_value.build.call_args_list
        assert any(call.kwargs.get("user_instruction") == "Focus on comparative analysis." for call in build_calls)


class TestTestPaperStats:
    @pytest.mark.unit
    def test_stats_to_dict(self) -> None:
        stats = PaperStats(
            total_questions=10,
            valid_questions=8,
            filtered_questions=2,
            by_category={"concept": 3, "application": 5},
            by_bloom_level={"understand": 2, "analyze": 3, "evaluate": 3},
            by_question_type={"short_answer": 4, "essay": 4},
        )

        result = stats.to_dict()

        assert result["total_questions"] == 10
        assert result["valid_questions"] == 8
        assert result["filtered_questions"] == 2
        assert result["by_bloom_level"]["evaluate"] == 3
        assert result["by_question_type"]["essay"] == 4
