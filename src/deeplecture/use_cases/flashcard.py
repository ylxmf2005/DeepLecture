"""Flashcard generation use case.

Two-stage LLM pipeline for creating active-recall flashcards:
1. Extraction: Reuse cheatsheet knowledge extraction (with timestamps)
2. Generation: Generate front/back card pairs from knowledge items
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from deeplecture.use_cases.dto.flashcard import (
    FlashcardItem,
    FlashcardResult,
    FlashcardStats,
    GeneratedFlashcardResult,
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
    from deeplecture.use_cases.dto.flashcard import GenerateFlashcardRequest
    from deeplecture.use_cases.interfaces import (
        LLMProtocol,
        LLMProviderProtocol,
        MetadataStorageProtocol,
        PathResolverProtocol,
        PdfTextExtractorProtocol,
    )
    from deeplecture.use_cases.interfaces.flashcard import FlashcardStorageProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol
    from deeplecture.use_cases.interfaces.subtitle import SubtitleStorageProtocol

logger = logging.getLogger(__name__)


def validate_flashcard_item(item: dict[str, Any]) -> tuple[bool, str]:
    """Validate a single flashcard item.

    Args:
        item: Flashcard item dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    front = item.get("front")
    if not front or not isinstance(front, str):
        return False, "missing or empty 'front'"

    back = item.get("back")
    if not back or not isinstance(back, str):
        return False, "missing or empty 'back'"

    ts = item.get("source_timestamp")
    if ts is not None and (not isinstance(ts, int | float) or ts < 0):
        return False, "invalid source_timestamp"

    return True, ""


class FlashcardUseCase:
    """
    Two-stage flashcard generation use case.

    Stage 1 (Extraction): Reuse cheatsheet's knowledge extraction
    Stage 2 (Generation): Generate front/back flashcard pairs

    Key difference from Quiz: no configurable card count —
    the model decides based on content density.
    """

    def __init__(
        self,
        *,
        flashcard_storage: FlashcardStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        llm_provider: LLMProviderProtocol,
        path_resolver: PathResolverProtocol,
        prompt_registry: PromptRegistryProtocol,
        metadata_storage: MetadataStorageProtocol | None = None,
        pdf_text_extractor: PdfTextExtractorProtocol | None = None,
    ) -> None:
        """Initialize FlashcardUseCase.

        Args:
            flashcard_storage: Storage for flashcard files
            subtitle_storage: Storage for subtitle files (context source)
            llm_provider: LLM provider for generation
            path_resolver: Path resolution service
            prompt_registry: Prompt registry for prompt selection
            metadata_storage: Content metadata storage for slide source resolution (optional)
            pdf_text_extractor: PDF text extraction service for slide context (optional)
        """
        self._flashcards = flashcard_storage
        self._subtitles = subtitle_storage
        self._llm_provider = llm_provider
        self._paths = path_resolver
        self._prompt_registry = prompt_registry
        self._metadata = metadata_storage
        self._pdf_text_extractor = pdf_text_extractor

    def get(self, content_id: str, language: str | None = None) -> FlashcardResult:
        """Get existing flashcards.

        Args:
            content_id: Content identifier
            language: Language filter (optional)

        Returns:
            FlashcardResult with items and metadata
        """
        result = self._flashcards.load(content_id, language)
        if result is None:
            return FlashcardResult(content_id=content_id, language=language or "", items=[])

        data, updated_at = result
        items = [FlashcardItem.from_dict(item) for item in data.get("items", [])]
        return FlashcardResult(
            content_id=content_id,
            language=data.get("language", language or ""),
            items=items,
            updated_at=updated_at,
        )

    def generate(
        self,
        request: GenerateFlashcardRequest,
    ) -> GeneratedFlashcardResult:
        """Generate flashcards using two-stage LLM pipeline.

        Stage 1: Extract KnowledgeItems from content (reuses cheatsheet extraction)
        Stage 2: Generate flashcard pairs from knowledge items

        Args:
            request: Generation request with parameters

        Returns:
            Generated flashcard result

        Raises:
            ValueError: If no content sources available
        """
        # Get LLM from provider
        llm = self._llm_provider.get(request.llm_model)

        # Load context from selected sources (subtitle/slide/both)
        context, used_sources = self._load_context(request)
        if not context.strip():
            raise ValueError(f"No content available for {request.content_id}")

        # Sanitize user instruction
        instruction = sanitize_question(request.user_instruction)

        # Stage 1: Extract knowledge items (reuses cheatsheet extraction)
        knowledge_items = self._extract_knowledge_items(
            context=context,
            language=request.language,
            subject_type=request.subject_type,
            user_instruction=instruction,
            llm=llm,
            prompts=request.prompts,
        )

        # Filter by criticality
        filtered_items = self._filter_by_criticality(knowledge_items, request.min_criticality)

        # Stage 2: Generate flashcards from knowledge items
        raw_flashcard_items = self._generate_flashcards(
            items=filtered_items,
            language=request.language,
            user_instruction=instruction,
            llm=llm,
            prompts=request.prompts,
        )

        # Validate and filter flashcard items
        valid_items, stats = self._validate_and_filter(raw_flashcard_items)

        # Save and return
        data = {
            "items": [item.to_dict() for item in valid_items],
            "language": request.language,
            "stats": stats.to_dict(),
        }
        updated_at = self._flashcards.save(request.content_id, request.language, data)

        return GeneratedFlashcardResult(
            content_id=request.content_id,
            language=request.language,
            items=valid_items,
            updated_at=updated_at,
            used_sources=used_sources,
            stats=stats,
        )

    def _load_context(
        self,
        request: GenerateFlashcardRequest,
    ) -> tuple[str, list[str]]:
        """Load content context from available sources.

        Uses timestamped subtitle context when subtitle source is selected.

        Args:
            request: Generation request

        Returns:
            Tuple of (context_text, list_of_sources_used)
        """
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
        """Load subtitle text with timestamp markers for knowledge extraction.

        Unlike the plain-text version used by Quiz/Cheatsheet, this method
        prefixes each segment with [HH:MM:SS] so the LLM can associate
        knowledge items with specific video positions.
        """
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
                raise ValueError("Cannot generate flashcards: no transcript or slides are available for this content.")
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
        """Stage 1: Extract structured knowledge items from content.

        Reuses cheatsheet extraction prompts for DRY compliance.

        Args:
            context: Source content text (with timestamp markers)
            language: Output language
            subject_type: Subject type hint
            user_instruction: Additional user guidance (sanitized)
            llm: LLM instance to use
            prompts: Prompt selection mapping

        Returns:
            List of extracted KnowledgeItems
        """
        from deeplecture.use_cases.dto.cheatsheet import KnowledgeItem

        impl_id = prompts.get("cheatsheet_extraction") if prompts else None
        prompt_builder = self._prompt_registry.get("cheatsheet_extraction", impl_id)
        coverage_instruction = (
            "Coverage priority: extract comprehensive knowledge points across the full lecture. "
            "Do not limit to one item per module, and split compound concepts into separate items."
        )
        combined_instruction = (
            f"{coverage_instruction}\n{user_instruction.strip()}" if user_instruction.strip() else coverage_instruction
        )
        spec = prompt_builder.build(
            context=context,
            language=language,
            subject_type=subject_type,
            user_instruction=combined_instruction,
            coverage_mode="comprehensive",
        )

        response = llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
        )

        # Parse JSON response
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

    def _generate_flashcards(
        self,
        items: list[KnowledgeItem],
        language: str,
        user_instruction: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[dict[str, Any]]:
        """Stage 2: Generate flashcard pairs from knowledge items.

        Args:
            items: Filtered knowledge items
            language: Output language
            user_instruction: Additional user guidance (sanitized)
            llm: LLM instance to use
            prompts: Prompt selection mapping

        Returns:
            List of raw flashcard item dictionaries
        """
        items_json = json.dumps(
            [item.to_dict() for item in items],
            ensure_ascii=False,
            indent=2,
        )

        impl_id = prompts.get("flashcard_generation") if prompts else None
        prompt_builder = self._prompt_registry.get("flashcard_generation", impl_id)
        spec = prompt_builder.build(
            knowledge_items_json=items_json,
            language=language,
            user_instruction=user_instruction,
        )

        response = llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
        )

        # Parse JSON response
        flashcard_data = parse_llm_json(response, default_type=list, context="flashcard generation")
        if not isinstance(flashcard_data, list):
            return []
        return flashcard_data

    def _validate_and_filter(
        self,
        raw_items: list[dict[str, Any]],
    ) -> tuple[list[FlashcardItem], FlashcardStats]:
        """Validate and filter flashcard items.

        Args:
            raw_items: Raw flashcard item dictionaries from LLM

        Returns:
            Tuple of (valid_items, stats)
        """
        valid_items: list[FlashcardItem] = []
        by_category: dict[str, int] = {}

        for raw_item in raw_items:
            is_valid, error = validate_flashcard_item(raw_item)
            if is_valid:
                item = FlashcardItem.from_dict(raw_item)
                valid_items.append(item)
                if item.source_category:
                    by_category[item.source_category] = by_category.get(item.source_category, 0) + 1
            else:
                logger.debug("Filtered invalid flashcard item: %s", error)

        stats = FlashcardStats(
            total_items=len(raw_items),
            valid_items=len(valid_items),
            filtered_items=len(raw_items) - len(valid_items),
            by_category=by_category,
        )

        return valid_items, stats
