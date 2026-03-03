"""Test paper generation use case.

Two-stage LLM pipeline for creating exam-style open-ended questions:
1. Extraction: Reuse cheatsheet knowledge extraction (with timestamps)
2. Generation: Generate test paper questions from knowledge items
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from deeplecture.use_cases.dto.test_paper import (
    VALID_BLOOM_LEVELS,
    GeneratedTestPaperResult,
    TestPaperResult,
    TestPaperStats,
    TestQuestion,
)
from deeplecture.use_cases.shared.context import extract_first_available_slide_text
from deeplecture.use_cases.shared.llm_json import parse_llm_json
from deeplecture.use_cases.shared.prompt_safety import sanitize_question
from deeplecture.use_cases.shared.subtitle import (
    load_first_available_subtitle_segments,
    prioritize_subtitle_languages,
)

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.cheatsheet import KnowledgeItem
    from deeplecture.use_cases.dto.test_paper import GenerateTestPaperRequest
    from deeplecture.use_cases.interfaces import (
        LLMProtocol,
        LLMProviderProtocol,
        MetadataStorageProtocol,
        PathResolverProtocol,
        PdfTextExtractorProtocol,
    )
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol
    from deeplecture.use_cases.interfaces.subtitle import SubtitleStorageProtocol
    from deeplecture.use_cases.interfaces.test_paper import TestPaperStorageProtocol

logger = logging.getLogger(__name__)


def validate_test_question(item: dict[str, Any]) -> tuple[bool, str]:
    """Validate a single test paper question item."""
    required = ["question_type", "stem", "reference_answer", "scoring_criteria", "bloom_level"]
    for field in required:
        if field not in item:
            return False, f"missing required field: {field}"

    question_type = item.get("question_type")
    if not isinstance(question_type, str) or not question_type.strip():
        return False, "question_type must be a non-empty string"

    stem = item.get("stem")
    if not isinstance(stem, str) or len(stem.strip()) < 10:
        return False, "stem must be at least 10 characters"

    reference_answer = item.get("reference_answer")
    if not isinstance(reference_answer, str) or len(reference_answer.strip()) < 20:
        return False, "reference_answer must be at least 20 characters"

    scoring_criteria = item.get("scoring_criteria")
    if not isinstance(scoring_criteria, list) or len(scoring_criteria) < 1:
        return False, "scoring_criteria must contain at least 1 item"
    if not all(isinstance(point, str) and point.strip() for point in scoring_criteria):
        return False, "scoring_criteria items must be non-empty strings"

    bloom_level = item.get("bloom_level")
    if not isinstance(bloom_level, str):
        return False, "bloom_level must be a string"
    normalized = bloom_level.strip().lower()
    if normalized not in VALID_BLOOM_LEVELS:
        return False, f"invalid bloom_level: {bloom_level!r}"

    ts = item.get("source_timestamp")
    if ts is not None and (not isinstance(ts, int | float) or ts < 0):
        return False, "invalid source_timestamp"

    return True, ""


class TestPaperUseCase:
    """Two-stage test paper generation use case."""

    def __init__(
        self,
        *,
        test_paper_storage: TestPaperStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        llm_provider: LLMProviderProtocol,
        path_resolver: PathResolverProtocol,
        prompt_registry: PromptRegistryProtocol,
        metadata_storage: MetadataStorageProtocol | None = None,
        pdf_text_extractor: PdfTextExtractorProtocol | None = None,
    ) -> None:
        self._test_papers = test_paper_storage
        self._subtitles = subtitle_storage
        self._llm_provider = llm_provider
        self._paths = path_resolver
        self._prompt_registry = prompt_registry
        self._metadata = metadata_storage
        self._pdf_text_extractor = pdf_text_extractor

    def get(self, content_id: str, language: str | None = None) -> TestPaperResult:
        """Get existing test paper."""
        result = self._test_papers.load(content_id, language)
        if result is None:
            return TestPaperResult(content_id=content_id, language=language or "", questions=[])

        data, updated_at = result
        questions = [TestQuestion.from_dict(item) for item in data.get("questions", [])]
        return TestPaperResult(
            content_id=content_id,
            language=data.get("language", language or ""),
            questions=questions,
            updated_at=updated_at,
        )

    def generate(self, request: GenerateTestPaperRequest) -> GeneratedTestPaperResult:
        """Generate test paper using two-stage LLM pipeline."""
        llm = self._llm_provider.get(request.llm_model)

        context, used_sources = self._load_context(request)
        if not context.strip():
            raise ValueError(f"No content available for {request.content_id}")

        instruction = sanitize_question(request.user_instruction)

        knowledge_items = self._extract_knowledge_items(
            context=context,
            language=request.language,
            subject_type=request.subject_type,
            user_instruction=instruction,
            llm=llm,
            prompts=request.prompts,
        )

        filtered_items = self._filter_by_criticality(knowledge_items, request.min_criticality)

        raw_questions = self._generate_test_paper(
            items=filtered_items,
            language=request.language,
            user_instruction=instruction,
            llm=llm,
            prompts=request.prompts,
        )

        valid_questions, stats = self._validate_and_filter(raw_questions)

        data = {
            "questions": [question.to_dict() for question in valid_questions],
            "language": request.language,
            "stats": stats.to_dict(),
        }
        updated_at = self._test_papers.save(request.content_id, request.language, data)

        return GeneratedTestPaperResult(
            content_id=request.content_id,
            language=request.language,
            questions=valid_questions,
            updated_at=updated_at,
            used_sources=used_sources,
            stats=stats,
        )

    def _load_context(self, request: GenerateTestPaperRequest) -> tuple[str, list[str]]:
        """Load content context from available sources."""
        mode = (request.context_mode or "both").strip().lower()
        used_sources: list[str] = []
        context_parts: list[str] = []

        subtitle_text = self._load_subtitle_context_with_timestamps(request.content_id)
        slide_text = self._load_slide_context(request.content_id)

        use_subtitle, use_slide = self._select_sources(
            mode=mode,
            has_subtitle=bool(subtitle_text),
            has_slide=bool(slide_text),
        )

        if use_subtitle and subtitle_text:
            context_parts.append(subtitle_text)
            used_sources.append("subtitle")

        if use_slide and slide_text:
            context_parts.append(slide_text)
            used_sources.append("slide")

        return "\n\n".join(context_parts), used_sources

    def _load_subtitle_context_with_timestamps(self, content_id: str) -> str:
        """Load subtitle text with timestamp markers for knowledge extraction."""
        candidate_languages = prioritize_subtitle_languages(
            self._subtitles.list_languages(content_id),
        )

        loaded = load_first_available_subtitle_segments(
            self._subtitles,
            content_id=content_id,
            candidate_languages=candidate_languages,
        )
        if loaded:
            _lang_used, segments = loaded
            lines: list[str] = []
            for seg in segments:
                text = seg.text.replace("\n", " ").strip()
                if text:
                    total_secs = int(seg.start)
                    hours, remainder = divmod(total_secs, 3600)
                    minutes, secs = divmod(remainder, 60)
                    lines.append(f"[{hours:02d}:{minutes:02d}:{secs:02d}] {text}")
            if lines:
                return "\n".join(lines)

        return ""

    def _load_slide_context(self, content_id: str) -> str:
        """Load slide/PDF text from best available candidate path."""
        metadata = self._metadata.get(content_id) if self._metadata else None
        return extract_first_available_slide_text(
            content_id,
            metadata=metadata,
            path_resolver=self._paths,
            pdf_text_extractor=self._pdf_text_extractor,
        )

    @staticmethod
    def _select_sources(
        *,
        mode: str,
        has_subtitle: bool,
        has_slide: bool,
    ) -> tuple[bool, bool]:
        """Select context sources based on requested mode and availability."""
        if mode == "subtitle":
            if not has_subtitle:
                raise ValueError("Requested subtitle context, but no subtitles are available.")
            return True, False

        if mode == "slide":
            if not has_slide:
                raise ValueError("Requested slide context, but no slide deck is available.")
            return False, True

        if mode == "both":
            if not has_subtitle and not has_slide:
                raise ValueError("Cannot generate test paper: no transcript or slides are available for this content.")
            return has_subtitle, has_slide

        raise ValueError("Unsupported context_mode. Allowed values are 'subtitle', 'slide', or 'both'.")

    def _extract_knowledge_items(
        self,
        context: str,
        language: str,
        subject_type: str,
        user_instruction: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[KnowledgeItem]:
        """Stage 1: Extract structured knowledge items from content."""
        from deeplecture.use_cases.dto.cheatsheet import KnowledgeItem

        impl_id = prompts.get("cheatsheet_extraction") if prompts else None
        prompt_builder = self._prompt_registry.get("cheatsheet_extraction", impl_id)
        spec = prompt_builder.build(
            context=context,
            language=language,
            subject_type=subject_type,
            user_instruction=user_instruction,
            coverage_mode="exam_focused",
        )

        response = llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
        )

        items_data = parse_llm_json(response, default_type=list, context="knowledge extraction")

        return [
            KnowledgeItem(
                category=item.get("category", "note"),
                content=item.get("content", ""),
                criticality=item.get("criticality", "medium"),
                tags=item.get("tags", []),
                source_start=item.get("source_start"),
            )
            for item in items_data
            if isinstance(item, dict) and item.get("content")
        ]

    def _filter_by_criticality(
        self,
        items: list[KnowledgeItem],
        min_criticality: str,
    ) -> list[KnowledgeItem]:
        """Filter items by minimum criticality level."""
        levels = {"high": 3, "medium": 2, "low": 1}
        min_level = levels.get(min_criticality, 2)

        return [item for item in items if levels.get(item.criticality, 2) >= min_level]

    def _generate_test_paper(
        self,
        items: list[KnowledgeItem],
        language: str,
        user_instruction: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[dict[str, Any]]:
        """Stage 2: Generate test paper questions from knowledge items."""
        items_json = json.dumps(
            [item.to_dict() for item in items],
            ensure_ascii=False,
            indent=2,
        )

        impl_id = prompts.get("test_paper_generation") if prompts else None
        prompt_builder = self._prompt_registry.get("test_paper_generation", impl_id)
        spec = prompt_builder.build(
            knowledge_items_json=items_json,
            language=language,
            user_instruction=user_instruction,
        )

        response = llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
        )

        data = parse_llm_json(response, default_type=list, context="test paper generation")
        if not isinstance(data, list):
            return []
        return data

    def _validate_and_filter(
        self,
        raw_items: list[dict[str, Any]],
    ) -> tuple[list[TestQuestion], TestPaperStats]:
        """Validate and filter test paper questions."""
        valid_questions: list[TestQuestion] = []
        by_category: dict[str, int] = {}
        by_bloom_level: dict[str, int] = {}
        by_question_type: dict[str, int] = {}

        for raw_item in raw_items:
            is_valid, error = validate_test_question(raw_item)
            if not is_valid:
                logger.debug("Filtered invalid test question: %s", error)
                continue

            normalized = raw_item.copy()
            normalized["bloom_level"] = str(normalized["bloom_level"]).strip().lower()

            question = TestQuestion.from_dict(normalized)
            valid_questions.append(question)

            if question.source_category:
                by_category[question.source_category] = by_category.get(question.source_category, 0) + 1

            by_bloom_level[question.bloom_level] = by_bloom_level.get(question.bloom_level, 0) + 1
            by_question_type[question.question_type] = by_question_type.get(question.question_type, 0) + 1

        stats = TestPaperStats(
            total_questions=len(raw_items),
            valid_questions=len(valid_questions),
            filtered_questions=len(raw_items) - len(valid_questions),
            by_category=by_category,
            by_bloom_level=by_bloom_level,
            by_question_type=by_question_type,
        )

        return valid_questions, stats
