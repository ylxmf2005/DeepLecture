"""Prompt registry - runtime prompt selection by function ID.

Central registry for all prompt builders. Supports:
- Multiple implementations per function (e.g., "default", "detailed")
- Runtime selection via (func_id, impl_id)
- Preview text for UI display
- Listing for config endpoints
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from deeplecture.use_cases.interfaces.prompt_registry import (
    PromptInfo,
    PromptSpec,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from deeplecture.use_cases.interfaces.prompt_registry import PromptBuilder


class PromptRegistry:
    """
    Registry for prompt builders indexed by (func_id, impl_id).

    Thread-safe for read operations (builders are registered at startup).
    """

    def __init__(self) -> None:
        # func_id -> {impl_id -> PromptBuilder}
        self._builders: dict[str, dict[str, PromptBuilder]] = {}
        # func_id -> default impl_id
        self._defaults: dict[str, str] = {}

    def register(
        self,
        func_id: str,
        builder: PromptBuilder,
        *,
        is_default: bool = False,
    ) -> None:
        """
        Register a prompt builder.

        Args:
            func_id: Function identifier (e.g., "note_outline")
            builder: PromptBuilder implementation
            is_default: If True, set as default for this func_id
        """
        if func_id not in self._builders:
            self._builders[func_id] = {}

        impl_id = builder.impl_id
        if impl_id in self._builders[func_id]:
            raise ValueError(f"Duplicate impl_id {impl_id!r} for func_id {func_id!r}")

        self._builders[func_id][impl_id] = builder

        # Set default: first registered or explicit is_default
        if is_default or func_id not in self._defaults:
            self._defaults[func_id] = impl_id

    def get(self, func_id: str, impl_id: str | None = None) -> PromptBuilder:
        """
        Get prompt builder by (func_id, impl_id).

        Args:
            func_id: Function identifier
            impl_id: Implementation ID. None uses default.

        Returns:
            PromptBuilder instance.

        Raises:
            ValueError: If func_id or impl_id not found.
        """
        if func_id not in self._builders:
            valid = ", ".join(self._builders.keys()) or "<none>"
            raise ValueError(f"Unknown func_id: {func_id!r}. Available: {valid}")

        impl = impl_id if impl_id else self.get_default_impl_id(func_id)
        builders = self._builders[func_id]

        if impl not in builders:
            valid = ", ".join(builders.keys()) or "<none>"
            raise ValueError(f"Unknown impl_id {impl!r} for {func_id!r}. Available: {valid}")

        return builders[impl]

    def get_default_impl_id(self, func_id: str) -> str:
        """Get default implementation ID for a function."""
        if func_id not in self._defaults:
            raise ValueError(f"Unknown func_id: {func_id!r}")
        return self._defaults[func_id]

    def list_func_ids(self) -> Sequence[str]:
        """List all registered function IDs."""
        return tuple(sorted(self._builders.keys()))

    def list_implementations(self, func_id: str) -> Sequence[PromptInfo]:
        """List available implementations for a func_id."""
        if func_id not in self._builders:
            raise ValueError(f"Unknown func_id: {func_id!r}")

        default_impl = self._defaults.get(func_id, "")
        result = []
        for impl_id, builder in self._builders[func_id].items():
            result.append(
                PromptInfo(
                    impl_id=impl_id,
                    name=builder.name,
                    description=builder.description,
                    is_default=(impl_id == default_impl),
                )
            )
        return tuple(result)

    def get_prompt_text(self, func_id: str, impl_id: str) -> str:
        """Return preview text for UI display."""
        builder = self.get(func_id, impl_id)
        return builder.get_preview_text()

    def get_all_defaults(self) -> Mapping[str, str]:
        """Return all func_id -> default_impl_id mappings."""
        return dict(self._defaults)


# =============================================================================
# BASE BUILDER CLASSES
# =============================================================================


class BasePromptBuilder:
    """Base class for prompt builders with common metadata."""

    def __init__(
        self,
        impl_id: str,
        name: str,
        description: str | None = None,
    ) -> None:
        self._impl_id = impl_id
        self._name = name
        self._description = description

    @property
    def impl_id(self) -> str:
        return self._impl_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str | None:
        return self._description

    def build(self, **kwargs) -> PromptSpec:
        raise NotImplementedError

    def get_preview_text(self) -> str:
        raise NotImplementedError


# =============================================================================
# PROMPT BUILDERS BY DOMAIN
# =============================================================================


class TimelineSegmentationBuilder(BasePromptBuilder):
    """Builder for lecture segmentation prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.timeline import build_lecture_segmentation_prompt

        segments = kwargs["segments"]
        language = kwargs["language"]
        learner_profile = kwargs.get("learner_profile")

        user_prompt, system_prompt = build_lecture_segmentation_prompt(
            segments, language=language, learner_profile=learner_profile
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Groups subtitle segments into knowledge units for timeline navigation. "
            "Creates pedagogical structure with titles and time boundaries."
        )


class TimelineExplanationBuilder(BasePromptBuilder):
    """Builder for segment explanation prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.timeline import build_segment_explanation_prompt

        segments = kwargs["segments"]
        language = kwargs["language"]
        chunk_start = kwargs["chunk_start"]
        chunk_end = kwargs["chunk_end"]
        learner_profile = kwargs.get("learner_profile")

        user_prompt, system_prompt = build_segment_explanation_prompt(
            segments,
            language=language,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            learner_profile=learner_profile,
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Generates explanations for timeline segments. "
            "Decides whether content warrants explanation and creates Markdown."
        )


class SlideLectureBuilder(BasePromptBuilder):
    """Builder for slide lecture generation prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.slide_lecture import build_slide_lecture_prompt

        user_prompt, system_prompt = build_slide_lecture_prompt(
            deck_id=kwargs["deck_id"],
            page_index=kwargs["page_index"],
            total_pages=kwargs["total_pages"],
            source_language=kwargs["source_language"],
            target_language=kwargs["target_language"],
            neighbor_images=kwargs["neighbor_images"],
            previous_transcript=kwargs["previous_transcript"],
            accumulated_summaries=kwargs["accumulated_summaries"],
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Generates narrated lecture content for slides. "
            "Produces TTS-ready bilingual segments with teaching style."
        )


class AskVideoBuilder(BasePromptBuilder):
    """Builder for Q&A system prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.ask import build_ask_video_user_prompt, get_ask_video_prompt

        system_prompt = get_ask_video_prompt(
            learner_profile=kwargs.get("learner_profile", ""),
            language=kwargs.get("language", "Simplified Chinese"),
        )
        user_prompt = build_ask_video_user_prompt(
            context_block=kwargs.get("context_block", ""),
            history_block=kwargs.get("history_block", ""),
            question=kwargs["question"],
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Handles Q&A about lecture content. "
            "Uses context from subtitles, slides, and timeline to answer questions."
        )


class AskSummarizeContextBuilder(BasePromptBuilder):
    """Builder for context summarization prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.ask import (
            build_summarize_context_user_prompt,
            get_summarize_context_prompt,
        )

        system_prompt = get_summarize_context_prompt(
            learner_profile=kwargs.get("learner_profile", ""),
            language=kwargs.get("language", "Simplified Chinese"),
        )
        user_prompt = build_summarize_context_user_prompt(
            context_block=kwargs.get("context_block", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return "Summarizes lecture context for condensed understanding."


class SubtitleBackgroundBuilder(BasePromptBuilder):
    """Builder for background extraction prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.subtitle import build_background_prompt

        user_prompt, system_prompt = build_background_prompt(kwargs["transcript_text"])
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Extracts background context from transcripts. "
            "Identifies topic, keywords, and tone for subtitle processing."
        )


class SubtitleEnhanceTranslateBuilder(BasePromptBuilder):
    """Builder for subtitle enhancement and translation prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.subtitle import build_enhance_translate_prompt

        user_prompt, system_prompt = build_enhance_translate_prompt(
            background=kwargs["background"],
            segments=kwargs["segments"],
            target_language=kwargs.get("target_language", "zh"),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Enhances and translates subtitles. " "Fixes ASR errors, merges fragments, and produces bilingual output."
        )


class ExplanationSystemBuilder(BasePromptBuilder):
    """Builder for explanation system prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.explanation import build_explain_system_prompt

        system_prompt = build_explain_system_prompt(
            learner_profile=kwargs.get("learner_profile", ""),
            output_language=kwargs.get("output_language", ""),
        )
        return PromptSpec(user_prompt="", system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return "System prompt for slide/frame explanations with learner adaptation."


class ExplanationUserBuilder(BasePromptBuilder):
    """Builder for explanation user prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.explanation import build_explain_user_prompt

        user_prompt = build_explain_user_prompt(
            timestamp=kwargs["timestamp"],
            subtitle_context=kwargs.get("subtitle_context", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=None)

    def get_preview_text(self) -> str:
        return "User prompt for requesting explanation at a specific timestamp."


class NoteOutlineBuilder(BasePromptBuilder):
    """Builder for note outline generation prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.note import build_note_outline_prompt

        user_prompt, system_prompt = build_note_outline_prompt(
            language=kwargs["language"],
            context_block=kwargs["context_block"],
            instruction=kwargs.get("instruction", ""),
            profile=kwargs.get("profile", ""),
            max_parts=kwargs.get("max_parts"),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Designs multi-part outline for study notes. " "Groups concepts by pedagogical coherence with focus points."
        )


class NotePartBuilder(BasePromptBuilder):
    """Builder for note part expansion prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.note import build_note_part_prompt

        user_prompt, system_prompt = build_note_part_prompt(
            language=kwargs["language"],
            context_block=kwargs["context_block"],
            instruction=kwargs.get("instruction", ""),
            profile=kwargs.get("profile", ""),
            part=kwargs["part"],
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return "Expands a single note part into full Markdown content. " "Includes headings, examples, and LaTeX math."


# =============================================================================
# REGISTRY FACTORY
# =============================================================================


def create_default_registry() -> PromptRegistry:
    """Create registry with all default prompt builders."""
    registry = PromptRegistry()

    # Timeline prompts
    registry.register(
        "timeline_segmentation",
        TimelineSegmentationBuilder("default", "Default", "Standard segmentation"),
        is_default=True,
    )
    registry.register(
        "timeline_explanation",
        TimelineExplanationBuilder("default", "Default", "Standard explanation"),
        is_default=True,
    )

    # Slide lecture
    registry.register(
        "slide_lecture",
        SlideLectureBuilder("default", "Default", "Professor-style narration"),
        is_default=True,
    )

    # Ask/Q&A
    registry.register(
        "ask_video",
        AskVideoBuilder("default", "Default", "Teaching assistant style"),
        is_default=True,
    )
    registry.register(
        "ask_summarize_context",
        AskSummarizeContextBuilder("default", "Default", "Context summarization"),
        is_default=True,
    )

    # Subtitle
    registry.register(
        "subtitle_background",
        SubtitleBackgroundBuilder("default", "Default", "Background extraction"),
        is_default=True,
    )
    registry.register(
        "subtitle_enhance_translate",
        SubtitleEnhanceTranslateBuilder("default", "Default", "Enhancement + translation"),
        is_default=True,
    )

    # Explanation
    registry.register(
        "explanation_system",
        ExplanationSystemBuilder("default", "Default", "System prompt"),
        is_default=True,
    )
    registry.register(
        "explanation_user",
        ExplanationUserBuilder("default", "Default", "User prompt"),
        is_default=True,
    )

    # Note
    registry.register(
        "note_outline",
        NoteOutlineBuilder("default", "Default", "Multi-part outline design"),
        is_default=True,
    )
    registry.register(
        "note_part",
        NotePartBuilder("default", "Default", "Part content expansion"),
        is_default=True,
    )

    return registry
