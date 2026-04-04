"""Explanation generation use case."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.explanation import (
    ExplanationEntry,
    ExplanationResult,
)
from deeplecture.use_cases.shared.prompt_safety import sanitize_learner_profile
from deeplecture.use_cases.shared.subtitle import (
    build_subtitle_language_candidates,
    load_first_available_subtitle_segments,
)

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.explanation import GenerateExplanationRequest
    from deeplecture.use_cases.interfaces import (
        MetadataStorageProtocol,
        SubtitleStorageProtocol,
    )
    from deeplecture.use_cases.interfaces.explanation import ExplanationStorageProtocol
    from deeplecture.use_cases.interfaces.llm_provider import LLMProviderProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol

logger = logging.getLogger(__name__)


class ExplanationUseCase:
    """
    Slide/frame explanation generation using LLM.

    Orchestrates:
    - Screenshot image processing
    - Subtitle context extraction
    - LLM explanation generation
    - Result storage
    """

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        explanation_storage: ExplanationStorageProtocol,
        llm_provider: LLMProviderProtocol,
        prompt_registry: PromptRegistryProtocol,
    ) -> None:
        self._metadata = metadata_storage
        self._subtitles = subtitle_storage
        self._explanations = explanation_storage
        self._llm_provider = llm_provider
        self._prompt_registry = prompt_registry

    def generate(self, request: GenerateExplanationRequest) -> ExplanationResult:
        """
        Generate explanation for a captured slide/frame.

        1. Load content metadata
        2. Get subtitle context around timestamp
        3. Generate explanation via LLM
        4. Save to storage
        5. Return result

        Args:
            request: Explanation generation request

        Returns:
            ExplanationResult with generated content

        Raises:
            ContentNotFoundError: If content not found
            RuntimeError: If LLM generation fails
        """
        metadata = self._metadata.get(request.content_id)
        if metadata is None:
            raise ContentNotFoundError(request.content_id)

        subtitle_context = self._get_subtitle_context(
            request.content_id,
            request.timestamp,
            request.subtitle_context_window_seconds,
            request.subtitle_language,
        )

        # Get LLM from provider
        llm = self._llm_provider.get(request.llm_model)

        # Build prompts using registry
        learner_profile = sanitize_learner_profile(request.learner_profile or "")

        # System prompt
        sys_impl_id = request.prompts.get("explanation_system") if request.prompts else None
        sys_builder = self._prompt_registry.get("explanation_system", sys_impl_id)
        sys_spec = sys_builder.build(
            learner_profile=learner_profile,
            output_language=request.output_language,
        )

        # User prompt
        user_impl_id = request.prompts.get("explanation_user") if request.prompts else None
        user_builder = self._prompt_registry.get("explanation_user", user_impl_id)
        user_spec = user_builder.build(
            timestamp=request.timestamp,
            subtitle_context=subtitle_context,
        )

        logger.info(
            "Generating explanation for %s at %.1fs",
            request.content_id,
            request.timestamp,
        )

        try:
            explanation_text = llm.complete(
                user_spec.user_prompt,
                system_prompt=sys_spec.system_prompt,
                image_path=request.image_path,
            )
        except Exception as e:
            logger.error("LLM explanation generation failed: %s", e)
            raise RuntimeError("Failed to generate explanation") from e

        # Update the pending entry with the generated explanation
        self._explanations.update(
            request.content_id,
            request.entry_id,
            {"explanation": explanation_text},
        )

        entry = ExplanationEntry(
            id=request.entry_id,
            timestamp=request.timestamp,
            explanation=explanation_text,
            created_at=datetime.now(timezone.utc).isoformat(),
            image_url=request.image_url,
            language=request.output_language,
        )

        logger.info(
            "Explanation generated for %s at %.1fs (%d chars)",
            request.content_id,
            request.timestamp,
            len(explanation_text),
        )

        return ExplanationResult(
            content_id=request.content_id,
            entry=entry,
            status="ready",
        )

    def _get_subtitle_context(
        self,
        content_id: str,
        timestamp: float,
        window_seconds: float,
        preferred_language: str | None,
    ) -> str:
        """Get subtitle text around the specified timestamp."""
        available_languages = self._subtitles.list_languages(content_id)
        candidate_languages = build_subtitle_language_candidates(
            available_languages,
            preferred_base_language=preferred_language,
        )

        loaded = load_first_available_subtitle_segments(
            self._subtitles,
            content_id=content_id,
            candidate_languages=candidate_languages,
        )
        if not loaded:
            return ""

        _lang_used, segments = loaded
        start_time = max(0.0, timestamp - window_seconds / 2)
        end_time = timestamp + window_seconds / 2

        relevant = [
            seg.text.replace("\n", " ").strip()
            for seg in segments
            if seg.start <= end_time and seg.end >= start_time and seg.text.strip()
        ]
        return " ".join(relevant)
