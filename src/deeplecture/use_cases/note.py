"""Note generation and management use case."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deeplecture.domain import FeatureStatus, FeatureType
from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.note import (
    GeneratedNoteResult,
    NotePart,
    NoteResult,
    SaveNoteRequest,
)
from deeplecture.use_cases.shared.llm_json import parse_llm_json
from deeplecture.use_cases.shared.prompt_safety import (
    normalize_llm_markdown,
    sanitize_learner_profile,
)
from deeplecture.use_cases.shared.subtitle import (
    load_first_available_subtitle_segments,
    prioritize_subtitle_languages,
)

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.note import GenerateNoteRequest
    from deeplecture.use_cases.interfaces import (
        LLMProtocol,
        MetadataStorageProtocol,
        NoteStorageProtocol,
        ParallelRunnerProtocol,
        PathResolverProtocol,
        PdfTextExtractorProtocol,
        SubtitleStorageProtocol,
    )
    from deeplecture.use_cases.interfaces.llm_provider import LLMProviderProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol

logger = logging.getLogger(__name__)


class NoteUseCase:
    """
    Note generation and management.

    Orchestrates:
    - AI note generation from subtitle/slide context
    - Parallel note part generation with LLM
    - Note storage and retrieval
    - Metadata updates
    """

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        note_storage: NoteStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol | None = None,
        path_resolver: PathResolverProtocol,
        llm_provider: LLMProviderProtocol,
        prompt_registry: PromptRegistryProtocol,
        parallel_runner: ParallelRunnerProtocol,
        pdf_text_extractor: PdfTextExtractorProtocol | None = None,
    ) -> None:
        """
        Initialize NoteUseCase.

        Args:
            metadata_storage: Content metadata storage
            note_storage: Note storage
            subtitle_storage: Subtitle storage (optional, for context)
            path_resolver: Path resolution for PDF and other files
            llm_provider: LLM provider for runtime model selection
            prompt_registry: Prompt registry for prompt selection
            parallel_runner: Parallel execution adapter (injected via DI)
            pdf_text_extractor: PDF text extraction service (optional)
        """
        self._metadata = metadata_storage
        self._notes = note_storage
        self._subtitles = subtitle_storage
        self._paths = path_resolver
        self._llm_provider = llm_provider
        self._prompt_registry = prompt_registry
        self._parallel = parallel_runner
        self._pdf_text_extractor = pdf_text_extractor

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_note(self, content_id: str) -> NoteResult | None:
        """
        Get existing note.

        Args:
            content_id: Content identifier

        Returns:
            NoteResult if note exists, None otherwise
        """
        result = self._notes.load(content_id)
        if not result:
            return None

        content, updated_at = result

        # Normalize LLM-generated Markdown for proper rendering
        normalized_content = normalize_llm_markdown(content)

        return NoteResult(
            content_id=content_id,
            content=normalized_content,
            updated_at=updated_at,
        )

    def save_note(self, request: SaveNoteRequest) -> NoteResult:
        """
        Save note content.

        Args:
            request: Save request

        Returns:
            NoteResult with saved data
        """
        updated_at = self._notes.save(request.content_id, request.content)

        # Update notes status in metadata
        metadata = self._metadata.get(request.content_id)
        if metadata is not None:
            try:
                metadata = metadata.with_status(FeatureType.NOTES.value, FeatureStatus.READY)
                self._metadata.save(metadata)
            except Exception:
                logger.exception("Failed to update notes status for %s", request.content_id)

        return NoteResult(
            content_id=request.content_id,
            content=request.content,
            updated_at=updated_at,
        )

    def generate_note(self, request: GenerateNoteRequest) -> GeneratedNoteResult:
        """
        Generate AI notes for content.

        Args:
            request: Generation request

        Returns:
            GeneratedNoteResult with outline and generated content

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

        # 3. Select and load context sources
        context_block, used_sources = self._load_context(
            request.content_id,
            request.context_mode,
            metadata.type,
        )

        if not context_block:
            raise ValueError("Cannot generate notes: failed to load usable context from subtitles or slides.")

        # Sanitize user-provided learner profile
        profile = sanitize_learner_profile(request.learner_profile)

        # 4. Build outline
        language = request.language
        outline = self._build_outline(
            language=language,
            context_block=context_block,
            instruction=request.user_instruction,
            profile=profile,
            max_parts=request.max_parts,
            llm=llm,
            prompts=request.prompts,
        )

        if not outline:
            raise ValueError("LLM did not return a usable note outline.")

        # 5. Generate parts in parallel
        full_note = self._generate_parts_parallel(
            outline=outline,
            language=language,
            context_block=context_block,
            instruction=request.user_instruction,
            profile=profile,
            llm=llm,
            prompts=request.prompts,
        )

        # 6. Save note
        save_request = SaveNoteRequest(content_id=request.content_id, content=full_note)
        result = self.save_note(save_request)

        return GeneratedNoteResult(
            content_id=request.content_id,
            content=result.content,
            updated_at=result.updated_at,
            outline=outline,
            used_sources=used_sources,
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

        # Load context on-demand based on mode
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

        # Determine which sources to use
        use_subtitle, use_slides = self._select_sources(
            mode=mode,
            content_type=content_type,
            has_subtitle=has_subtitle,
            has_slides=has_slides,
        )

        # Build context block
        context_parts = []
        used_sources = []

        if use_subtitle and subtitle_text:
            context_parts.append("=== Subtitle transcript context ===\n" + subtitle_text)
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
        """
        Select which sources to use based on mode and availability.

        Args:
            mode: Context mode ("subtitle", "slide", "both", "auto")
            content_type: Content type ("video", "pdf")
            has_subtitle: Whether subtitles are available
            has_slides: Whether slides are available

        Returns:
            (use_subtitle, use_slides)
        """
        if not has_subtitle and not has_slides:
            if content_type == "video":
                raise ValueError(
                    "Cannot generate notes: this video has no subtitles or slide deck. "
                    "Please generate subtitles first."
                )
            raise ValueError("Cannot generate notes: no transcript or slides are available for this content.")

        if mode == "subtitle":
            if not has_subtitle:
                raise ValueError("Requested subtitle context, but no subtitles are available.")
            return True, False

        if mode == "slide":
            if not has_slides:
                raise ValueError("Requested slide context, but no slide deck is available.")
            return False, True

        if mode == "both":
            # Use all available sources (no longer requires both to exist)
            return has_subtitle, has_slides

        if mode == "auto":
            # Prefer the most relevant source for the content type
            if content_type == "video":
                # For video: prefer subtitle if available
                if has_subtitle:
                    return True, has_slides  # Include slides if also available
                return False, True
            # For slides/PDF: prefer slide text when available
            if has_slides:
                return has_subtitle, True  # Include subtitle if also available
            return True, False

        raise ValueError("Unsupported context_mode. Allowed values are 'subtitle', 'slide', 'both', or 'auto'.")

    def _load_subtitle_context(self, content_id: str) -> str:
        """Load subtitle text from best available source."""
        if not self._subtitles:
            return ""

        candidate_languages = prioritize_subtitle_languages(self._subtitles.list_languages(content_id))

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

    def _load_pdf_context(self, content_id: str) -> str:
        """Load PDF text if available."""
        if self._pdf_text_extractor is None:
            return ""

        pdf_path = self._paths.build_content_path(content_id, "slide", "slide.pdf")
        return self._pdf_text_extractor.extract_text(pdf_path)

    # =========================================================================
    # OUTLINE GENERATION
    # =========================================================================

    def _build_outline(
        self,
        *,
        language: str,
        context_block: str,
        instruction: str,
        profile: str,
        max_parts: int | None,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[NotePart]:
        """
        Generate note outline using LLM.

        Args:
            language: Target language
            context_block: Lecture context
            instruction: User instruction
            profile: Learner profile
            max_parts: Max parts to generate
            llm: LLM instance to use
            prompts: Prompt selection mapping

        Returns:
            List of NotePart objects
        """
        impl_id = prompts.get("note_outline") if prompts else None
        prompt_builder = self._prompt_registry.get("note_outline", impl_id)
        spec = prompt_builder.build(
            language=language,
            context_block=context_block,
            instruction=instruction,
            profile=profile,
            max_parts=max_parts,
        )

        raw = llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
            temperature=0.2,
        )

        return self._parse_outline_json(raw)

    def _parse_outline_json(self, raw: str) -> list[NotePart]:
        """Parse outline JSON from LLM response."""
        data = parse_llm_json(raw, context="note outline")

        if not isinstance(data, dict):
            return []

        raw_parts = data.get("parts")
        if not isinstance(raw_parts, list):
            return []

        parts = []
        for index, item in enumerate(raw_parts, start=1):
            if not isinstance(item, dict):
                continue

            raw_id = item.get("id", index)
            try:
                pid = int(raw_id)
            except Exception:
                pid = index

            title = str(item.get("title") or "").strip()
            summary = str(item.get("summary") or "").strip()
            focus_raw = item.get("focus_points") or []

            if not isinstance(focus_raw, list):
                focus_raw = []

            focus_points = [str(value or "").strip() for value in focus_raw if str(value or "").strip()]

            if not title and not summary and not focus_points:
                continue

            final_title = title or f"Part {pid}"
            parts.append(
                NotePart(
                    id=pid,
                    title=final_title,
                    summary=summary,
                    focus_points=focus_points,
                )
            )

        parts.sort(key=lambda part: part.id)
        return parts

    # =========================================================================
    # PART GENERATION
    # =========================================================================

    def _generate_parts_parallel(
        self,
        *,
        outline: list[NotePart],
        language: str,
        context_block: str,
        instruction: str,
        profile: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> str:
        """
        Generate all note parts in parallel.

        Args:
            outline: List of parts to generate
            language: Target language
            context_block: Lecture context
            instruction: User instruction
            profile: Learner profile
            llm: LLM instance to use
            prompts: Prompt selection mapping

        Returns:
            Full note content (joined parts)
        """
        if not outline:
            return ""

        # Get prompt builder once (reused in parallel)
        impl_id = prompts.get("note_part") if prompts else None
        prompt_builder = self._prompt_registry.get("note_part", impl_id)

        def _render_error(part: NotePart, exc: Exception) -> str:
            logger.error("Failed to generate note part %s: %s", part.id, exc)
            return f"## Part {part.id}: {part.title}\n\n[Generation failed. Please retry later.]"

        def _generate(part: NotePart) -> str:
            spec = prompt_builder.build(
                language=language,
                context_block=context_block,
                instruction=instruction,
                profile=profile,
                part=part,
            )
            return llm.complete(
                spec.user_prompt,
                system_prompt=spec.system_prompt,
                temperature=0.4,
            )

        parts = self._parallel.map_ordered(
            outline,
            _generate,
            group="note_parts",
            on_error=lambda exc, part: _render_error(part, exc),
        )

        joined = "\n\n".join(part.strip() for part in parts if part.strip()).strip()
        # Normalize LLM-generated Markdown for proper rendering
        return normalize_llm_markdown(joined)
