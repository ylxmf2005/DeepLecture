"""Cheatsheet generation and management use case."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deeplecture.domain import FeatureStatus, FeatureType
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.prompts.cheatsheet_prompt import (
    build_cheatsheet_extraction_prompts,
    build_cheatsheet_rendering_prompts,
)
from deeplecture.use_cases.dto.cheatsheet import (
    CheatsheetResult,
    CheatsheetStats,
    GeneratedCheatsheetResult,
    KnowledgeItem,
    SaveCheatsheetRequest,
)
from deeplecture.use_cases.shared.llm_json import parse_llm_json
from deeplecture.use_cases.shared.prompt_safety import normalize_llm_markdown
from deeplecture.use_cases.shared.subtitle import (
    load_first_available_subtitle_segments,
    prioritize_subtitle_languages,
)

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.cheatsheet import GenerateCheatsheetRequest
    from deeplecture.use_cases.interfaces import (
        CheatsheetStorageProtocol,
        LLMProtocol,
        MetadataStorageProtocol,
        PathResolverProtocol,
        PdfTextExtractorProtocol,
        SubtitleStorageProtocol,
    )
    from deeplecture.use_cases.interfaces.llm_provider import LLMProviderProtocol

logger = logging.getLogger(__name__)


class CheatsheetUseCase:
    """
    Cheatsheet generation and management.

    Two-stage pipeline:
    1. Extraction: Extract KnowledgeItems from subtitle/slide context
    2. Rendering: Render items into scannable Markdown format
    """

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        cheatsheet_storage: CheatsheetStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol | None = None,
        path_resolver: PathResolverProtocol,
        llm_provider: LLMProviderProtocol,
        pdf_text_extractor: PdfTextExtractorProtocol | None = None,
    ) -> None:
        """
        Initialize CheatsheetUseCase.

        Args:
            metadata_storage: Content metadata storage
            cheatsheet_storage: Cheatsheet storage
            subtitle_storage: Subtitle storage (optional, for context)
            path_resolver: Path resolution for PDF and other files
            llm_provider: LLM provider for runtime model selection
            pdf_text_extractor: PDF text extraction service (optional)
        """
        self._metadata = metadata_storage
        self._cheatsheets = cheatsheet_storage
        self._subtitles = subtitle_storage
        self._paths = path_resolver
        self._llm_provider = llm_provider
        self._pdf_text_extractor = pdf_text_extractor

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_cheatsheet(self, content_id: str) -> CheatsheetResult | None:
        """
        Get existing cheatsheet.

        Args:
            content_id: Content identifier

        Returns:
            CheatsheetResult if cheatsheet exists, None otherwise
        """
        result = self._cheatsheets.load(content_id)
        if not result:
            return None

        content, updated_at = result

        # Normalize LLM-generated Markdown for proper rendering
        normalized_content = normalize_llm_markdown(content)

        return CheatsheetResult(
            content_id=content_id,
            content=normalized_content,
            updated_at=updated_at,
        )

    def save_cheatsheet(self, request: SaveCheatsheetRequest) -> CheatsheetResult:
        """
        Save cheatsheet content.

        Args:
            request: Save request

        Returns:
            CheatsheetResult with saved data
        """
        updated_at = self._cheatsheets.save(request.content_id, request.content)

        # Update cheatsheet status in metadata
        metadata = self._metadata.get(request.content_id)
        if metadata is not None:
            try:
                metadata = metadata.with_status(
                    FeatureType.CHEATSHEET.value, FeatureStatus.READY
                )
                self._metadata.save(metadata)
            except Exception:
                logger.exception(
                    "Failed to update cheatsheet status for %s", request.content_id
                )

        return CheatsheetResult(
            content_id=request.content_id,
            content=request.content,
            updated_at=updated_at,
        )

    def generate_cheatsheet(
        self, request: GenerateCheatsheetRequest
    ) -> GeneratedCheatsheetResult:
        """
        Generate AI cheatsheet for content.

        Two-stage pipeline:
        1. Extract knowledge items from context
        2. Render items into scannable Markdown

        Args:
            request: Generation request

        Returns:
            GeneratedCheatsheetResult with content and stats

        Raises:
            ContentNotFoundError: Content not found
            ValueError: Invalid context mode or no usable context
        """
        # 1. Load metadata
        metadata = self._metadata.get(request.content_id)
        if metadata is None:
            raise ContentNotFoundError(request.content_id)

        # 2. Get LLM from provider
        llm = self._llm_provider.get(request.llm_model)

        # 3. Load context sources
        context_block, used_sources = self._load_context(
            request.content_id,
            request.context_mode,
            metadata.type,
        )

        if not context_block:
            raise ValueError(
                "Cannot generate cheatsheet: failed to load usable context "
                "from subtitles or slides."
            )

        # 4. Stage 1: Extract knowledge items
        items = self._extract_knowledge_items(
            context_block=context_block,
            language=request.language,
            user_instruction=request.user_instruction,
            min_criticality=request.min_criticality,
            subject_type=request.subject_type,
            llm=llm,
        )

        if not items:
            raise ValueError(
                "LLM did not extract any knowledge items from the content."
            )

        # 5. Stage 2: Render to Markdown
        markdown = self._render_cheatsheet(
            items=items,
            language=request.language,
            target_pages=request.target_pages,
            user_instruction=request.user_instruction,
            llm=llm,
        )

        # 6. Compute stats
        stats = self._compute_stats(items)

        # 7. Save cheatsheet
        save_request = SaveCheatsheetRequest(
            content_id=request.content_id, content=markdown
        )
        result = self.save_cheatsheet(save_request)

        return GeneratedCheatsheetResult(
            content_id=request.content_id,
            content=result.content,
            updated_at=result.updated_at,
            used_sources=used_sources,
            stats=stats,
        )

    # =========================================================================
    # CONTEXT LOADING
    # =========================================================================

    def _load_context(
        self,
        content_id: str,
        context_mode: str,
        content_type: str,
    ) -> tuple[str, list[str]]:
        """
        Load context from subtitle and/or slide sources.

        Args:
            content_id: Content identifier
            context_mode: "subtitle" | "slide" | "both" | "auto"
            content_type: "video" | "pdf"

        Returns:
            (context_block, used_sources)
        """
        mode = (context_mode or "auto").strip().lower()

        subtitle_text = ""
        slide_text = ""

        needs_subtitle = mode in ("subtitle", "both", "auto")
        needs_slides = mode in ("slide", "both", "auto")

        if needs_subtitle:
            subtitle_text = self._load_subtitle_context(content_id)
        if needs_slides:
            slide_text = self._load_pdf_context(content_id)

        has_subtitle = bool(subtitle_text)
        has_slides = bool(slide_text)

        use_subtitle, use_slides = self._select_sources(
            mode=mode,
            content_type=content_type,
            has_subtitle=has_subtitle,
            has_slides=has_slides,
        )

        context_parts = []
        used_sources = []

        if use_subtitle and subtitle_text:
            context_parts.append(
                "=== Subtitle transcript context ===\n" + subtitle_text
            )
            used_sources.append("subtitle")

        if use_slides and slide_text:
            context_parts.append("=== Slide deck context ===\n" + slide_text)
            used_sources.append("slide")

        context_block = "\n\n".join(context_parts)
        return context_block, used_sources

    @staticmethod
    def _select_sources(
        *,
        mode: str,
        content_type: str,
        has_subtitle: bool,
        has_slides: bool,
    ) -> tuple[bool, bool]:
        """Select which sources to use based on mode and availability."""
        if not has_subtitle and not has_slides:
            if content_type == "video":
                raise ValueError(
                    "Cannot generate cheatsheet: this video has no subtitles "
                    "or slide deck. Please generate subtitles first."
                )
            raise ValueError(
                "Cannot generate cheatsheet: no transcript or slides "
                "are available for this content."
            )

        if mode == "subtitle":
            if not has_subtitle:
                raise ValueError(
                    "Requested subtitle context, but no subtitles are available."
                )
            return True, False

        if mode == "slide":
            if not has_slides:
                raise ValueError(
                    "Requested slide context, but no slide deck is available."
                )
            return False, True

        if mode == "both":
            return has_subtitle, has_slides

        if mode == "auto":
            if content_type == "video":
                if has_subtitle:
                    return True, has_slides
                return False, True
            if has_slides:
                return has_subtitle, True
            return True, False

        raise ValueError(
            "Unsupported context_mode. Allowed: 'subtitle', 'slide', 'both', 'auto'."
        )

    def _load_subtitle_context(self, content_id: str) -> str:
        """Load subtitle text from best available source."""
        if not self._subtitles:
            return ""

        candidate_languages = prioritize_subtitle_languages(
            self._subtitles.list_languages(content_id)
        )

        loaded = load_first_available_subtitle_segments(
            self._subtitles,
            content_id=content_id,
            candidate_languages=candidate_languages,
        )
        if loaded:
            _lang_used, segments = loaded
            lines = [
                seg.text.replace("\n", " ").strip()
                for seg in segments
                if seg.text.strip()
            ]
            if lines:
                return "\n".join(lines)

        return ""

    def _load_pdf_context(self, content_id: str) -> str:
        """Load PDF text if available."""
        if self._pdf_text_extractor is None:
            return ""

        pdf_path = self._paths.build_content_path(content_id, "slide", "slide.pdf")
        return self._pdf_text_extractor.extract_text(pdf_path)

    # =========================================================================
    # EXTRACTION STAGE
    # =========================================================================

    def _extract_knowledge_items(
        self,
        *,
        context_block: str,
        language: str,
        user_instruction: str,
        min_criticality: str,
        subject_type: str,
        llm: LLMProtocol,
    ) -> list[KnowledgeItem]:
        """
        Extract knowledge items from context using LLM.

        Args:
            context_block: Lecture context
            language: Target language
            user_instruction: User instruction
            min_criticality: Minimum criticality filter
            subject_type: Subject type hint
            llm: LLM instance

        Returns:
            List of KnowledgeItem objects
        """
        system_prompt, user_prompt = build_cheatsheet_extraction_prompts(
            language=language,
            context_block=context_block,
            user_instruction=user_instruction,
            min_criticality=min_criticality,
            subject_type=subject_type,
        )

        raw = llm.complete(
            user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )

        return self._parse_extraction_json(raw, min_criticality)

    def _parse_extraction_json(
        self, raw: str, min_criticality: str
    ) -> list[KnowledgeItem]:
        """Parse extraction JSON from LLM response."""
        data = parse_llm_json(raw, context="cheatsheet extraction")

        if not isinstance(data, dict):
            return []

        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            return []

        # Criticality filter
        crit_order = {"high": 3, "medium": 2, "low": 1}
        min_level = crit_order.get(min_criticality.lower(), 2)

        items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue

            category = str(item.get("category") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            criticality = str(item.get("criticality") or "medium").strip().lower()
            tags_raw = item.get("tags") or []

            if not content:
                continue

            # Validate category
            valid_categories = {
                "formula",
                "definition",
                "condition",
                "algorithm",
                "constant",
                "example",
            }
            if category not in valid_categories:
                category = "definition"  # default

            # Validate criticality
            if criticality not in crit_order:
                criticality = "medium"

            # Apply filter
            if crit_order[criticality] < min_level:
                continue

            # Parse tags
            if isinstance(tags_raw, list):
                tags = [str(t).strip() for t in tags_raw if str(t).strip()]
            else:
                tags = []

            items.append(
                KnowledgeItem(
                    category=category,
                    content=content,
                    criticality=criticality,
                    tags=tags,
                )
            )

        return items

    # =========================================================================
    # RENDERING STAGE
    # =========================================================================

    def _render_cheatsheet(
        self,
        *,
        items: list[KnowledgeItem],
        language: str,
        target_pages: int,
        user_instruction: str,
        llm: LLMProtocol,
    ) -> str:
        """
        Render knowledge items into Markdown cheatsheet.

        Args:
            items: Knowledge items to render
            language: Target language
            target_pages: Target length in pages
            user_instruction: User instruction
            llm: LLM instance

        Returns:
            Rendered Markdown content
        """
        system_prompt, user_prompt = build_cheatsheet_rendering_prompts(
            language=language,
            items=items,
            target_pages=target_pages,
            user_instruction=user_instruction,
        )

        raw = llm.complete(
            user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )

        # Normalize LLM-generated Markdown
        return normalize_llm_markdown(raw)

    # =========================================================================
    # STATS
    # =========================================================================

    @staticmethod
    def _compute_stats(items: list[KnowledgeItem]) -> CheatsheetStats:
        """Compute statistics about extracted items."""
        by_category: dict[str, int] = {}
        for item in items:
            by_category[item.category] = by_category.get(item.category, 0) + 1

        return CheatsheetStats(
            total_items=len(items),
            by_category=by_category,
        )
