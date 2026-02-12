"""Cheatsheet generation use case.

Two-stage LLM pipeline for creating high-density exam cheatsheets:
1. Extraction: Parse content into structured KnowledgeItems
2. Rendering: Convert items to scannable Markdown format
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deeplecture.use_cases.dto.cheatsheet import (
    CheatsheetResult,
    CheatsheetStats,
    GeneratedCheatsheetResult,
    KnowledgeItem,
)
from deeplecture.use_cases.shared.llm_json import parse_llm_json
from deeplecture.use_cases.shared.prompt_safety import sanitize_question
from deeplecture.use_cases.shared.subtitle import (
    load_first_available_subtitle_segments,
    prioritize_subtitle_languages,
)

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.cheatsheet import GenerateCheatsheetRequest
    from deeplecture.use_cases.interfaces import (
        LLMProtocol,
        LLMProviderProtocol,
        PathResolverProtocol,
    )
    from deeplecture.use_cases.interfaces.cheatsheet import CheatsheetStorageProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol
    from deeplecture.use_cases.interfaces.subtitle import SubtitleStorageProtocol

logger = logging.getLogger(__name__)


class CheatsheetUseCase:
    """
    Two-stage cheatsheet generation use case.

    Stage 1 (Extraction): LLM extracts structured KnowledgeItems from content
    Stage 2 (Rendering): LLM renders items into scannable Markdown cheatsheet

    This approach balances:
    - Information density (filtering by criticality)
    - Scannable format (tables, formulas, bullet points)
    - Cost control (two focused stages vs. one large prompt)
    """

    def __init__(
        self,
        *,
        cheatsheet_storage: CheatsheetStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        path_resolver: PathResolverProtocol,
        llm_provider: LLMProviderProtocol,
        prompt_registry: PromptRegistryProtocol,
    ) -> None:
        """Initialize CheatsheetUseCase.

        Args:
            cheatsheet_storage: Storage for cheatsheet files
            subtitle_storage: Storage for subtitle files (context source)
            path_resolver: Path resolution service
            llm_provider: LLM provider for generation
            prompt_registry: Prompt registry for prompt selection
        """
        self._cheatsheets = cheatsheet_storage
        self._subtitles = subtitle_storage
        self._paths = path_resolver
        self._llm_provider = llm_provider
        self._prompt_registry = prompt_registry

    def get(self, content_id: str) -> CheatsheetResult:
        """Get existing cheatsheet.

        Args:
            content_id: Content identifier

        Returns:
            CheatsheetResult with content and metadata
        """
        result = self._cheatsheets.load(content_id)
        if result is None:
            return CheatsheetResult(content_id=content_id, content="", updated_at=None)

        content, updated_at = result
        return CheatsheetResult(
            content_id=content_id,
            content=content,
            updated_at=updated_at,
        )

    def save(self, content_id: str, content: str) -> CheatsheetResult:
        """Save cheatsheet content.

        Args:
            content_id: Content identifier
            content: Markdown content to save

        Returns:
            CheatsheetResult with saved content and timestamp
        """
        updated_at = self._cheatsheets.save(content_id, content)
        return CheatsheetResult(
            content_id=content_id,
            content=content,
            updated_at=updated_at,
        )

    def generate(
        self,
        request: GenerateCheatsheetRequest,
    ) -> GeneratedCheatsheetResult:
        """Generate cheatsheet using two-stage LLM pipeline.

        Stage 1: Extract KnowledgeItems from content
        Stage 2: Render items into scannable Markdown

        Args:
            request: Generation request with parameters

        Returns:
            Generated cheatsheet result

        Raises:
            ValueError: If no content sources available
        """
        # Get LLM from provider
        llm = self._llm_provider.get(request.llm_model)

        # Load context (subtitles)
        context, used_sources = self._load_context(request)
        if not context.strip():
            raise ValueError(f"No content available for {request.content_id}")

        # Sanitize user instruction
        instruction = sanitize_question(request.user_instruction)

        # Stage 1: Extract knowledge items
        items = self._extract_knowledge_items(
            context=context,
            language=request.language,
            subject_type=request.subject_type,
            user_instruction=instruction,
            llm=llm,
            prompts=request.prompts,
        )

        # Filter by criticality
        filtered_items = self._filter_by_criticality(items, request.min_criticality)

        # Stage 2: Render to Markdown
        cheatsheet_content = self._render_cheatsheet(
            items=filtered_items,
            language=request.language,
            target_pages=request.target_pages,
            min_criticality=request.min_criticality,
            llm=llm,
            prompts=request.prompts,
        )

        # Save and return
        updated_at = self._cheatsheets.save(request.content_id, cheatsheet_content)

        # Build stats
        stats = self._build_stats(filtered_items)

        return GeneratedCheatsheetResult(
            content_id=request.content_id,
            content=cheatsheet_content,
            updated_at=updated_at,
            used_sources=used_sources,
            stats=stats,
        )

    def _load_context(
        self,
        request: GenerateCheatsheetRequest,
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
            subtitle_text = self._load_subtitle_context(request.content_id)
            if subtitle_text:
                context_parts.append(subtitle_text)
                used_sources.append("subtitle")

        return "\n\n".join(context_parts), used_sources

    def _load_subtitle_context(self, content_id: str) -> str:
        """Load subtitle text from best available source."""
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
            lines = [seg.text.replace("\n", " ").strip() for seg in segments if seg.text.strip()]
            if lines:
                return "\n".join(lines)

        return ""

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

        Args:
            context: Source content text
            language: Output language
            subject_type: Subject type hint
            user_instruction: Additional user guidance (sanitized)
            llm: LLM instance to use
            prompts: Prompt selection mapping

        Returns:
            List of extracted KnowledgeItems
        """
        impl_id = prompts.get("cheatsheet_extraction") if prompts else None
        prompt_builder = self._prompt_registry.get("cheatsheet_extraction", impl_id)
        spec = prompt_builder.build(
            context=context,
            language=language,
            subject_type=subject_type,
            user_instruction=user_instruction,
        )

        response = llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
        )

        # Parse JSON response
        items_data = parse_llm_json(response, default_type=list, context="cheatsheet extraction")

        return [
            KnowledgeItem(
                category=item.get("category", "note"),
                content=item.get("content", ""),
                criticality=item.get("criticality", "medium"),
                tags=item.get("tags", []),
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

    def _render_cheatsheet(
        self,
        items: list[KnowledgeItem],
        language: str,
        target_pages: int,
        min_criticality: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> str:
        """Stage 2: Render knowledge items into scannable Markdown.

        Args:
            items: Filtered knowledge items
            language: Output language
            target_pages: Target length in pages
            min_criticality: Criticality filter used
            llm: LLM instance to use
            prompts: Prompt selection mapping

        Returns:
            Rendered Markdown cheatsheet
        """
        import json

        items_json = json.dumps(
            [item.to_dict() for item in items],
            ensure_ascii=False,
            indent=2,
        )

        impl_id = prompts.get("cheatsheet_rendering") if prompts else None
        prompt_builder = self._prompt_registry.get("cheatsheet_rendering", impl_id)
        spec = prompt_builder.build(
            knowledge_items_json=items_json,
            language=language,
            target_pages=target_pages,
            min_criticality=min_criticality,
        )

        return llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
        )

    def _build_stats(self, items: list[KnowledgeItem]) -> CheatsheetStats:
        """Build statistics from knowledge items.

        Args:
            items: List of knowledge items

        Returns:
            Statistics about the items
        """
        by_category: dict[str, int] = {}
        for item in items:
            by_category[item.category] = by_category.get(item.category, 0) + 1

        return CheatsheetStats(
            total_items=len(items),
            by_category=by_category,
        )
