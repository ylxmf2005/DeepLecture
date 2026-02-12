"""Quiz generation use case.

Two-stage LLM pipeline for creating MCQ quizzes:
1. Extraction: Reuse cheatsheet knowledge extraction
2. Generation: Generate MCQs with misconception-based distractors
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from deeplecture.use_cases.dto.quiz import (
    GeneratedQuizResult,
    QuizItem,
    QuizResult,
    QuizStats,
)
from deeplecture.use_cases.prompts.cheatsheet import build_cheatsheet_extraction_prompts
from deeplecture.use_cases.prompts.quiz import build_quiz_generation_prompts

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.cheatsheet import KnowledgeItem
    from deeplecture.use_cases.dto.quiz import GenerateQuizRequest
    from deeplecture.use_cases.interfaces import (
        LLMProtocol,
        LLMProviderProtocol,
        PathResolverProtocol,
        QuizStorageProtocol,
        SubtitleStorageProtocol,
    )

logger = logging.getLogger(__name__)


def validate_quiz_item(item: dict[str, Any]) -> tuple[bool, str]:
    """Validate a single quiz item.

    Args:
        item: Quiz item dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    # 1. Check options count
    options = item.get("options", [])
    if len(options) != 4:
        return False, "options must have exactly 4 items"

    # 2. Check answer_index range
    answer_index = item.get("answer_index")
    if not isinstance(answer_index, int) or not 0 <= answer_index <= 3:
        return False, "answer_index must be 0-3"

    # 3. Check for duplicate options
    if len(set(options)) != len(options):
        return False, "duplicate options detected"

    # 4. Check required fields (use 'in' to handle 0 and empty strings correctly)
    required = ["stem", "options", "answer_index", "explanation"]
    for field in required:
        if field not in item or (field != "answer_index" and not item[field]):
            return False, f"missing required field: {field}"

    return True, ""


class QuizUseCase:
    """
    Two-stage quiz generation use case.

    Stage 1 (Extraction): Reuse cheatsheet's knowledge extraction
    Stage 2 (Generation): Generate MCQs with validated distractors

    This approach:
    - Enables DRY by reusing knowledge extraction
    - Ensures quality through validation
    - Provides misconception-diverse distractors
    """

    def __init__(
        self,
        *,
        quiz_storage: QuizStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        llm_provider: LLMProviderProtocol,
        path_resolver: PathResolverProtocol,
    ) -> None:
        """Initialize QuizUseCase.

        Args:
            quiz_storage: Storage for quiz files
            subtitle_storage: Storage for subtitle files (context source)
            llm_provider: LLM provider for generation
            path_resolver: Path resolution service
        """
        self._quizzes = quiz_storage
        self._subtitles = subtitle_storage
        self._llm = llm_provider
        self._paths = path_resolver

    def get(self, content_id: str, language: str | None = None) -> QuizResult:
        """Get existing quiz.

        Args:
            content_id: Content identifier
            language: Language filter (optional)

        Returns:
            QuizResult with items and metadata
        """
        result = self._quizzes.load(content_id, language)
        if result is None:
            return QuizResult(content_id=content_id, language=language or "", items=[])

        data, updated_at = result
        items = [QuizItem.from_dict(item) for item in data.get("items", [])]
        return QuizResult(
            content_id=content_id,
            language=data.get("language", language or ""),
            items=items,
            updated_at=updated_at,
        )

    def save(self, content_id: str, language: str, items: list[QuizItem]) -> QuizResult:
        """Save quiz items.

        Args:
            content_id: Content identifier
            language: Quiz language
            items: Quiz items to save

        Returns:
            QuizResult with saved items and timestamp
        """
        data = {
            "items": [item.to_dict() for item in items],
            "language": language,
        }
        updated_at = self._quizzes.save(content_id, language, data)
        return QuizResult(
            content_id=content_id,
            language=language,
            items=items,
            updated_at=updated_at,
        )

    async def generate(
        self,
        request: GenerateQuizRequest,
    ) -> GeneratedQuizResult:
        """Generate quiz using two-stage LLM pipeline.

        Stage 1: Extract KnowledgeItems from content (reuses cheatsheet extraction)
        Stage 2: Generate MCQs from knowledge items

        Args:
            request: Generation request with parameters

        Returns:
            Generated quiz result

        Raises:
            ValueError: If no content sources available
        """
        # Load context (subtitles for now, can extend to slides)
        llm = self._llm.get(request.llm_model)
        context, used_sources = await self._load_context(request)
        if not context.strip():
            raise ValueError(f"No content available for {request.content_id}")

        # Stage 1: Extract knowledge items (reuses cheatsheet extraction)
        knowledge_items = await self._extract_knowledge_items(
            llm=llm,
            context=context,
            language=request.language,
            subject_type=request.subject_type,
            user_instruction=request.user_instruction,
        )

        # Filter by criticality
        filtered_items = self._filter_by_criticality(knowledge_items, request.min_criticality)

        # Stage 2: Generate quiz from knowledge items
        raw_quiz_items = await self._generate_quiz(
            llm=llm,
            items=filtered_items,
            language=request.language,
            question_count=request.question_count,
            user_instruction=request.user_instruction,
        )

        # Validate and filter quiz items
        valid_items, stats = self._validate_and_filter(raw_quiz_items)

        # Save and return
        data = {
            "items": [item.to_dict() for item in valid_items],
            "language": request.language,
            "stats": stats.to_dict(),
        }
        updated_at = self._quizzes.save(request.content_id, request.language, data)

        return GeneratedQuizResult(
            content_id=request.content_id,
            language=request.language,
            items=valid_items,
            updated_at=updated_at,
            used_sources=used_sources,
            stats=stats,
        )

    async def _load_context(
        self,
        request: GenerateQuizRequest,
    ) -> tuple[str, list[str]]:
        """Load content context from available sources.

        Args:
            request: Generation request

        Returns:
            Tuple of (context_text, list_of_sources_used)
        """
        used_sources: list[str] = []
        context_parts: list[str] = []

        # Try subtitle
        if request.context_mode in ("auto", "subtitle", "both"):
            subtitle_result = self._subtitles.load(request.content_id)
            if subtitle_result:
                segments, _ = subtitle_result
                if segments:
                    text = "\n".join(seg.get("text", "") for seg in segments if seg.get("text"))
                    if text.strip():
                        context_parts.append(text)
                        used_sources.append("subtitle")

        # TODO: Add slide text extraction when available

        return "\n\n".join(context_parts), used_sources

    async def _extract_knowledge_items(
        self,
        llm: LLMProtocol,
        context: str,
        language: str,
        subject_type: str,
        user_instruction: str,
    ) -> list[KnowledgeItem]:
        """Stage 1: Extract structured knowledge items from content.

        Reuses cheatsheet extraction prompts for DRY compliance.

        Args:
            context: Source content text
            language: Output language
            subject_type: Subject type hint
            user_instruction: Additional user guidance

        Returns:
            List of extracted KnowledgeItems
        """
        from deeplecture.use_cases.dto.cheatsheet import KnowledgeItem

        system_prompt, user_prompt = build_cheatsheet_extraction_prompts(
            context=context,
            language=language,
            subject_type=subject_type,
            user_instruction=user_instruction,
        )

        response = await llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Parse JSON response
        try:
            items_data = json.loads(response)
            if not isinstance(items_data, list):
                items_data = [items_data]
        except json.JSONDecodeError:
            logger.warning("Failed to parse extraction response as JSON, using fallback")
            items_data = [
                {
                    "category": "note",
                    "content": response,
                    "criticality": "medium",
                    "tags": [],
                }
            ]

        return [
            KnowledgeItem(
                category=item.get("category", "note"),
                content=item.get("content", ""),
                criticality=item.get("criticality", "medium"),
                tags=item.get("tags", []),
            )
            for item in items_data
            if item.get("content")
        ]

    def _filter_by_criticality(
        self,
        items: list[KnowledgeItem],
        min_criticality: str,
    ) -> list[KnowledgeItem]:
        """Filter items by minimum criticality level.

        Args:
            items: List of knowledge items
            min_criticality: Minimum level to include

        Returns:
            Filtered list
        """
        levels = {"high": 3, "medium": 2, "low": 1}
        min_level = levels.get(min_criticality, 2)

        return [item for item in items if levels.get(item.criticality, 2) >= min_level]

    async def _generate_quiz(
        self,
        llm: LLMProtocol,
        items: list[KnowledgeItem],
        language: str,
        question_count: int,
        user_instruction: str,
    ) -> list[dict[str, Any]]:
        """Stage 2: Generate quiz questions from knowledge items.

        Args:
            items: Filtered knowledge items
            language: Output language
            question_count: Number of questions to generate
            user_instruction: Additional user guidance

        Returns:
            List of raw quiz item dictionaries
        """
        items_json = json.dumps(
            [item.to_dict() for item in items],
            ensure_ascii=False,
            indent=2,
        )

        system_prompt, user_prompt = build_quiz_generation_prompts(
            knowledge_items_json=items_json,
            language=language,
            question_count=question_count,
            user_instruction=user_instruction,
        )

        response = await llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Parse JSON response
        try:
            quiz_data = json.loads(response)
            if not isinstance(quiz_data, list):
                quiz_data = [quiz_data]
            return quiz_data
        except json.JSONDecodeError:
            logger.warning("Failed to parse quiz response as JSON")
            return []

    def _validate_and_filter(
        self,
        raw_items: list[dict[str, Any]],
    ) -> tuple[list[QuizItem], QuizStats]:
        """Validate and filter quiz items.

        Args:
            raw_items: Raw quiz item dictionaries from LLM

        Returns:
            Tuple of (valid_items, stats)
        """
        valid_items: list[QuizItem] = []
        by_category: dict[str, int] = {}

        for raw_item in raw_items:
            is_valid, error = validate_quiz_item(raw_item)
            if is_valid:
                item = QuizItem.from_dict(raw_item)
                valid_items.append(item)
                if item.source_category:
                    by_category[item.source_category] = by_category.get(item.source_category, 0) + 1
            else:
                logger.debug("Filtered invalid quiz item: %s", error)

        stats = QuizStats(
            total_items=len(raw_items),
            valid_items=len(valid_items),
            filtered_items=len(raw_items) - len(valid_items),
            by_category=by_category,
        )

        return valid_items, stats
