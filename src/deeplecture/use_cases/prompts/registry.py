"""Prompt registry - runtime prompt selection by function ID.

Central registry for all prompt builders. Supports:
- Multiple implementations per function (e.g., "default", "detailed")
- Runtime selection via (func_id, impl_id)
- Preview text for UI display
- Listing for config endpoints
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deeplecture.use_cases.interfaces.prompt_registry import (
    PromptInfo,
    PromptSpec,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from deeplecture.use_cases.interfaces.prompt_registry import PromptBuilder
    from deeplecture.use_cases.prompts.template_definitions import PromptTemplateDefinition

logger = logging.getLogger(__name__)


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
            outline=kwargs.get("outline"),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return "Expands a single note part into full Markdown content. " "Includes headings, examples, and LaTeX math."


class CheatsheetExtractionBuilder(BasePromptBuilder):
    """Builder for cheatsheet knowledge extraction prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.cheatsheet import build_cheatsheet_extraction_prompts

        system_prompt, user_prompt = build_cheatsheet_extraction_prompts(
            context=kwargs["context"],
            language=kwargs["language"],
            subject_type=kwargs.get("subject_type", "auto"),
            user_instruction=kwargs.get("user_instruction", ""),
            coverage_mode=kwargs.get("coverage_mode", "exam_focused"),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Extracts structured knowledge items from educational content. "
            "Focuses on exam-critical formulas, definitions, and conditions."
        )


class CheatsheetRenderingBuilder(BasePromptBuilder):
    """Builder for cheatsheet rendering prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.cheatsheet import build_cheatsheet_rendering_prompts

        system_prompt, user_prompt = build_cheatsheet_rendering_prompts(
            knowledge_items_json=kwargs["knowledge_items_json"],
            language=kwargs["language"],
            target_pages=kwargs.get("target_pages", 2),
            min_criticality=kwargs.get("min_criticality", "medium"),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Renders knowledge items into scannable Markdown cheatsheet. "
            "Uses tables, bullet points, and LaTeX for high information density."
        )


class QuizGenerationBuilder(BasePromptBuilder):
    """Builder for quiz MCQ generation prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.quiz import build_quiz_generation_prompts

        system_prompt, user_prompt = build_quiz_generation_prompts(
            knowledge_items_json=kwargs["knowledge_items_json"],
            language=kwargs["language"],
            question_count=kwargs["question_count"],
            user_instruction=kwargs.get("user_instruction", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Generates multiple-choice quiz questions from knowledge items. "
            "Uses misconception-based distractor generation strategy."
        )


class FlashcardGenerationBuilder(BasePromptBuilder):
    """Builder for flashcard generation prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.flashcard import build_flashcard_generation_prompts

        system_prompt, user_prompt = build_flashcard_generation_prompts(
            knowledge_items_json=kwargs["knowledge_items_json"],
            language=kwargs["language"],
            user_instruction=kwargs.get("user_instruction", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Generates front/back flashcard pairs from knowledge items. "
            "Designed for active recall study with video timestamp linking."
        )


class TestPaperGenerationBuilder(BasePromptBuilder):
    """Builder for test paper generation prompts."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.test_paper import build_test_paper_generation_prompts

        system_prompt, user_prompt = build_test_paper_generation_prompts(
            knowledge_items_json=kwargs["knowledge_items_json"],
            language=kwargs["language"],
            user_instruction=kwargs.get("user_instruction", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Generates exam-style open-ended test paper questions from knowledge items. "
            "Includes reference answers, scoring criteria, and Bloom levels."
        )


class PodcastDialogueBuilder(BasePromptBuilder):
    """Builder for podcast dialogue generation prompts (Stage 2)."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.podcast import build_podcast_dialogue_prompts

        system_prompt, user_prompt = build_podcast_dialogue_prompts(
            knowledge_items_json=kwargs["knowledge_items_json"],
            language=kwargs["language"],
            host_role=kwargs.get("host_role", ""),
            guest_role=kwargs.get("guest_role", ""),
            user_instruction=kwargs.get("user_instruction", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Generates a two-person podcast dialogue script from knowledge items. "
            "Creates natural conversation flow between host and guest speakers."
        )


class PodcastDramatizeBuilder(BasePromptBuilder):
    """Builder for podcast dialogue dramatization prompts (Stage 3)."""

    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.podcast import build_podcast_dramatize_prompts

        system_prompt, user_prompt = build_podcast_dramatize_prompts(
            dialogue_json=kwargs["dialogue_json"],
            language=kwargs["language"],
            user_instruction=kwargs.get("user_instruction", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return (
            "Rewrites podcast dialogue to sound natural for TTS delivery. "
            "Adds filler words, reactions, and informal phrasing."
        )


class TemplateOverrideBuilder(BasePromptBuilder):
    """Builder that overrides default prompts with template-based rendering."""

    def __init__(
        self,
        *,
        impl_id: str,
        name: str,
        description: str | None,
        func_id: str,
        fallback_builder: PromptBuilder,
        system_template: str,
        user_template: str,
    ) -> None:
        super().__init__(impl_id=impl_id, name=name, description=description)
        self._func_id = func_id
        self._fallback = fallback_builder
        self._system_template = system_template
        self._user_template = user_template

    def build(self, **kwargs) -> PromptSpec:
        base = self._fallback.build(**kwargs)
        context = {k: self._stringify(v) for k, v in kwargs.items()}
        system_prompt = base.system_prompt
        user_prompt = base.user_prompt

        if self._system_template.strip():
            system_prompt = self._render(self._system_template, context, field_name="system_template") or system_prompt
        if self._user_template.strip():
            user_prompt = self._render(self._user_template, context, field_name="user_template") or user_prompt

        return PromptSpec(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=base.temperature,
        )

    def get_preview_text(self) -> str:
        return f"Template override for {self._func_id} (fallbacks to default on render error)."

    def _render(self, template: str, context: dict[str, str], *, field_name: str) -> str | None:
        try:
            return template.format_map(context)
        except KeyError as exc:
            logger.warning(
                "Prompt template render fallback (%s/%s): missing key %s in %s",
                self._func_id,
                self.impl_id,
                exc,
                field_name,
            )
            return None
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning(
                "Prompt template render fallback (%s/%s): %s",
                self._func_id,
                self.impl_id,
                exc,
            )
            return None

    @staticmethod
    def _stringify(value: object) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        return str(value)


# =============================================================================
# REGISTRY FACTORY
# =============================================================================


def create_default_registry(custom_templates: Sequence[PromptTemplateDefinition] | None = None) -> PromptRegistry:
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

    # Cheatsheet
    registry.register(
        "cheatsheet_extraction",
        CheatsheetExtractionBuilder("default", "Default", "Knowledge extraction"),
        is_default=True,
    )
    registry.register(
        "cheatsheet_rendering",
        CheatsheetRenderingBuilder("default", "Default", "Scannable Markdown rendering"),
        is_default=True,
    )

    # Quiz
    registry.register(
        "quiz_generation",
        QuizGenerationBuilder("default", "Default", "Misconception-based MCQ generation"),
        is_default=True,
    )

    # Flashcard
    registry.register(
        "flashcard_generation",
        FlashcardGenerationBuilder("default", "Default", "Flashcard generation from knowledge items"),
        is_default=True,
    )

    # Test paper
    registry.register(
        "test_paper_generation",
        TestPaperGenerationBuilder("default", "Default", "Exam-style test paper generation"),
        is_default=True,
    )

    # Podcast
    registry.register(
        "podcast_dialogue",
        PodcastDialogueBuilder("default", "Default", "Two-person podcast dialogue generation"),
        is_default=True,
    )
    registry.register(
        "podcast_dramatize",
        PodcastDramatizeBuilder("default", "Default", "Dialogue dramatization for TTS"),
        is_default=True,
    )

    if custom_templates:
        for template in custom_templates:
            if not template.active or template.impl_id == "default":
                continue
            try:
                fallback = registry.get(template.func_id)
                registry.register(
                    template.func_id,
                    TemplateOverrideBuilder(
                        impl_id=template.impl_id,
                        name=template.name,
                        description=template.description,
                        func_id=template.func_id,
                        fallback_builder=fallback,
                        system_template=template.system_template,
                        user_template=template.user_template,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "Skip invalid custom prompt template (%s/%s): %s",
                    template.func_id,
                    template.impl_id,
                    exc,
                )

    return registry
