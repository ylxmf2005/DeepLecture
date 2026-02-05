"""Timeline generation use case."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deeplecture.domain import FeatureStatus, FeatureType
from deeplecture.domain.errors import ContentNotFoundError, SubtitleGenerationError
from deeplecture.use_cases.dto.timeline import (
    KnowledgeUnit,
    SubtitleSegment,
    TimelineEntry,
    TimelineResult,
)
from deeplecture.use_cases.shared.llm_json import parse_llm_json
from deeplecture.use_cases.shared.prompt_safety import sanitize_learner_profile
from deeplecture.use_cases.shared.subtitle import load_subtitle_segments_with_fallback

if TYPE_CHECKING:
    from deeplecture.config import TimelineConfig
    from deeplecture.use_cases.dto.timeline import GenerateTimelineRequest
    from deeplecture.use_cases.interfaces import (
        LLMProtocol,
        MetadataStorageProtocol,
        ParallelRunnerProtocol,
        SubtitleStorageProtocol,
        TimelineStorageProtocol,
    )
    from deeplecture.use_cases.interfaces.llm_provider import LLMProviderProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol

logger = logging.getLogger(__name__)


class TimelineUseCase:
    """
    Timeline generation from subtitles using LLM.

    Orchestrates:
    - SRT parsing and subtitle segment extraction
    - Two-stage LLM processing:
      1. Segmentation: Divide lecture into knowledge units
      2. Explanation: Generate explanation for each unit
    - Timeline storage
    - Metadata updates
    """

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        timeline_storage: TimelineStorageProtocol,
        llm_provider: LLMProviderProtocol,
        prompt_registry: PromptRegistryProtocol,
        config: TimelineConfig,
        parallel_runner: ParallelRunnerProtocol,
    ) -> None:
        self._metadata = metadata_storage
        self._subtitles = subtitle_storage
        self._timelines = timeline_storage
        self._llm_provider = llm_provider
        self._prompt_registry = prompt_registry
        self._config = config
        self._parallel = parallel_runner

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def generate(self, request: GenerateTimelineRequest) -> TimelineResult:
        """
        Generate timeline for content.

        1. Load content metadata
        2. Check for cached timeline (unless force=True)
        3. Load subtitle file
        4. Parse SRT to segments
        5. Stage 1: Segment into knowledge units (1 LLM call)
        6. Stage 2: Generate explanation for each unit (parallel LLM calls)
        7. Save timeline
        8. Update metadata

        Args:
            request: Timeline generation request

        Returns:
            TimelineResult with entries and metadata

        Raises:
            ContentNotFoundError: If content or subtitles not found
            SubtitleGenerationError: If generation fails
        """
        metadata = self._metadata.get(request.content_id)
        if metadata is None:
            raise ContentNotFoundError(request.content_id)

        subtitle_language = self._resolve_language(request.subtitle_language)
        output_language = self._resolve_language(request.output_language)
        learner_profile = sanitize_learner_profile(request.learner_profile or "")

        # Check cache (unless force) - cache is keyed by output_language
        if not request.force:
            cached_result = self._try_load_cached(request.content_id, output_language, learner_profile)
            if cached_result:
                return cached_result

        # Mark as processing
        metadata = metadata.with_status(FeatureType.TIMELINE.value, FeatureStatus.PROCESSING)
        self._metadata.save(metadata)

        try:
            # Get LLM instance from provider
            llm = self._llm_provider.get(request.llm_model)

            # Load and parse subtitles using subtitle_language (source)
            segments = self._load_subtitle_segments(request.content_id, subtitle_language)
            if not segments:
                raise SubtitleGenerationError("No subtitle segments found")

            # Stage 1: Segment into knowledge units (LLM uses output_language)
            knowledge_units = self._segment_knowledge_units(
                segments,
                language=output_language,
                learner_profile=learner_profile,
                llm=llm,
                prompts=request.prompts,
            )

            if not knowledge_units:
                logger.warning("Knowledge segmentation produced no units")
                entries = []
                total_units = 0
                failed_units = 0
                error_message = None
            else:
                # Stage 2: Generate explanations (parallel, LLM uses output_language)
                entries, total_units, failed_units, error_message = self._generate_explanations(
                    segments,
                    knowledge_units,
                    language=output_language,
                    learner_profile=learner_profile,
                    llm=llm,
                    prompts=request.prompts,
                )

            # Renumber IDs sequentially
            entries.sort(key=lambda x: (x.start, x.id))
            for new_id, entry in enumerate(entries, start=1):
                entry.id = new_id

            # Determine status based on failures
            if failed_units > 0:
                if len(entries) == 0:
                    status = "error"
                    metadata = metadata.with_status(FeatureType.TIMELINE.value, FeatureStatus.ERROR)
                else:
                    status = "partial_success"
                    metadata = metadata.with_status(FeatureType.TIMELINE.value, FeatureStatus.READY)
            else:
                status = "ready"
                metadata = metadata.with_status(FeatureType.TIMELINE.value, FeatureStatus.READY)

            # Save timeline - keyed by output_language
            self._save_timeline(
                request.content_id,
                output_language,
                learner_profile,
                entries,
                total_units=total_units,
                failed_units=failed_units,
                error_message=error_message,
            )

            self._metadata.save(metadata)

            return TimelineResult(
                content_id=request.content_id,
                language=output_language,
                entries=entries,
                status=status,
                total_units=total_units,
                failed_units=failed_units,
                error_message=error_message,
            )

        except Exception as e:
            metadata = metadata.with_status(FeatureType.TIMELINE.value, FeatureStatus.ERROR)
            self._metadata.save(metadata)
            logger.error("Timeline generation failed: %s", e)
            raise SubtitleGenerationError(str(e)) from e

    def get_timeline(self, content_id: str, language: str | None = None) -> TimelineResult | None:
        """Get existing timeline."""
        resolved_language = self._resolve_language(language)

        payload = self._timelines.load(content_id, resolved_language)
        if not payload:
            return None

        entries = self._parse_timeline_entries(payload.get("timeline", []))

        return TimelineResult(
            content_id=content_id,
            language=resolved_language,
            entries=entries,
            cached=True,
            status=payload.get("status", "ready"),
            total_units=payload.get("total_units", 0),
            failed_units=payload.get("failed_units", 0),
            error_message=payload.get("error"),
        )

    # =========================================================================
    # SUBTITLE LOADING
    # =========================================================================

    def _load_subtitle_segments(self, content_id: str, language: str) -> list[SubtitleSegment]:
        """
        Load and parse subtitle file to segments.

        Tries enhanced subtitles first, then falls back to regular.
        """
        loaded = load_subtitle_segments_with_fallback(
            self._subtitles,
            content_id=content_id,
            base_language=language,
        )
        if not loaded:
            raise SubtitleGenerationError(f"Subtitles not found: {language}")
        _lang_used, subtitle_segments = loaded

        # Convert domain Segment to timeline SubtitleSegment
        return [
            SubtitleSegment(
                id=idx + 1,
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
            )
            for idx, seg in enumerate(subtitle_segments)
        ]

    # =========================================================================
    # STAGE 1: KNOWLEDGE SEGMENTATION
    # =========================================================================

    def _segment_knowledge_units(
        self,
        segments: list[SubtitleSegment],
        *,
        language: str,
        learner_profile: str | None,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[KnowledgeUnit]:
        """
        Use LLM to divide full transcript into knowledge units.

        Single LLM call processes entire transcript.
        """
        if not segments:
            return []

        # Get prompt builder from registry
        impl_id = prompts.get("timeline_segmentation") if prompts else None
        prompt_builder = self._prompt_registry.get("timeline_segmentation", impl_id)
        spec = prompt_builder.build(
            segments=segments,
            language=language,
            learner_profile=learner_profile,
        )

        raw = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt, temperature=self._config.temperature)

        data = parse_llm_json(raw, context="knowledge segmentation")
        units_raw = data.get("knowledge_units", [])

        if not isinstance(units_raw, list):
            logger.warning("knowledge_units is not a list")
            return []

        # Parse and validate units
        seg_start = segments[0].start
        seg_end = segments[-1].end

        units: list[KnowledgeUnit] = []
        for idx, item in enumerate(units_raw, start=1):
            try:
                start = float(item.get("start", 0))
                end = float(item.get("end", 0))
            except (TypeError, ValueError):
                continue

            if end <= start or end < seg_start or start > seg_end:
                continue

            # Clamp to global subtitle range
            start = max(seg_start, start)
            end = min(seg_end, end)

            title = str(item.get("title", "")).strip() or f"Concept {idx}"

            units.append(KnowledgeUnit(id=idx, start=start, end=end, title=title))

        # Sort and merge overlapping units
        units.sort(key=lambda u: (u.start, u.end, u.id))
        return self._merge_overlapping_units(units)

    def _merge_overlapping_units(self, units: list[KnowledgeUnit]) -> list[KnowledgeUnit]:
        """Merge overlapping knowledge units."""
        if not units:
            return units

        merged: list[KnowledgeUnit] = []
        for unit in units:
            if not merged:
                merged.append(unit)
                continue

            last = merged[-1]
            if unit.start >= last.end:
                merged.append(unit)
            else:
                # Overlapping: extend the previous unit
                if unit.end > last.end:
                    merged[-1] = KnowledgeUnit(
                        id=last.id,
                        start=last.start,
                        end=unit.end,
                        title=last.title,
                    )

        return merged

    # =========================================================================
    # STAGE 2: EXPLANATION GENERATION
    # =========================================================================

    # Sentinel to distinguish LLM errors from intentional skips
    _GENERATION_ERROR = object()

    def _generate_explanations(
        self,
        segments: list[SubtitleSegment],
        knowledge_units: list[KnowledgeUnit],
        *,
        language: str,
        learner_profile: str | None,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> tuple[list[TimelineEntry], int, int, str | None]:
        """
        Generate timeline entries by running one LLM call per knowledge unit.

        Uses parallel execution for efficiency.

        Returns:
            Tuple of (entries, total_units, failed_count, error_message)
            - entries: Successfully generated timeline entries
            - total_units: Total number of knowledge units attempted
            - failed_count: Number of units that failed due to LLM errors
            - error_message: Last error message if any failures occurred
        """
        if not knowledge_units:
            return [], 0, 0, None

        # Get prompt builder from registry (once, reused in parallel)
        impl_id = prompts.get("timeline_explanation") if prompts else None
        prompt_builder = self._prompt_registry.get("timeline_explanation", impl_id)

        # Track the last error message for reporting
        last_error: list[str] = []  # Use list to allow mutation in nested function

        def segments_for_unit(unit: KnowledgeUnit) -> list[SubtitleSegment]:
            """Get subtitle segments within a unit's time range."""
            return [seg for seg in segments if seg.end > unit.start and seg.start < unit.end]

        def process_unit(unit_idx: int, unit: KnowledgeUnit) -> TimelineEntry | object | None:
            """Process a single knowledge unit.

            Returns:
                TimelineEntry: Success
                _GENERATION_ERROR: LLM API error (should be counted as failure)
                None: Intentionally skipped (should_explain=false or empty)
            """
            unit_segments = segments_for_unit(unit)
            if not unit_segments:
                return None

            unit_start = unit_segments[0].start
            unit_end = unit_segments[-1].end

            spec = prompt_builder.build(
                segments=unit_segments,
                language=language,
                chunk_start=unit_start,
                chunk_end=unit_end,
                learner_profile=learner_profile,
            )

            try:
                raw = llm.complete(
                    spec.user_prompt,
                    system_prompt=spec.system_prompt,
                    temperature=self._config.temperature,
                )
            except Exception as exc:
                error_msg = f"LLM error for unit {unit_idx+1} [{unit_start:.1f}s-{unit_end:.1f}s]: {exc}"
                logger.error(error_msg)
                last_error.clear()
                last_error.append(str(exc))
                return self._GENERATION_ERROR  # Mark as error, not skip

            entry = self._parse_explanation_output(
                raw,
                entry_id=unit_idx + 1,
                chunk_start=unit_start,
                chunk_end=unit_end,
            )

            # Use unit title if LLM didn't provide one
            if entry and not entry.title.strip():
                entry.title = unit.title

            return entry

        items = list(enumerate(knowledge_units))

        def _run(item: tuple[int, KnowledgeUnit]) -> TimelineEntry | object | None:
            idx, unit = item
            return process_unit(idx, unit)

        def _on_error(exc: Exception, item: tuple[int, KnowledgeUnit]) -> object:
            """Handle parallel runner errors - count as failure."""
            idx, _unit = item
            error_msg = f"Parallel execution error for unit {idx+1}: {exc}"
            logger.error(error_msg)
            last_error.clear()
            last_error.append(str(exc))
            return self._GENERATION_ERROR

        results = self._parallel.map_ordered(
            items,
            _run,
            group="timeline_units",
            on_error=_on_error,
        )

        # Count failures and filter results
        total_units = len(knowledge_units)
        failed_count = sum(1 for r in results if r is self._GENERATION_ERROR)
        entries = [entry for entry in results if isinstance(entry, TimelineEntry)]
        error_message = last_error[0] if last_error else None

        if failed_count > 0:
            logger.warning(
                "Timeline generation: %d/%d units failed. Last error: %s",
                failed_count,
                total_units,
                error_message,
            )

        return entries, total_units, failed_count, error_message

    def _parse_explanation_output(
        self,
        raw: str,
        *,
        entry_id: int,
        chunk_start: float,
        chunk_end: float,
    ) -> TimelineEntry | None:
        """
        Parse LLM output for explanation.

        Expected JSON shape:
        {
          "should_explain": true | false,
          "title": "short title",
          "trigger_time": 123.45,
          "markdown": "explanation"
        }
        """
        data = parse_llm_json(raw, context="timeline explanation")

        should_explain = data.get("should_explain")
        if should_explain is not None and not bool(should_explain):
            return None

        markdown = str(data.get("markdown", "")).strip()
        if not markdown:
            logger.debug("LLM requested explanation but markdown is empty")
            return None

        title = str(data.get("title", "")).strip() or "Explanation"

        try:
            trigger_time = float(data.get("trigger_time", chunk_start))
        except (TypeError, ValueError):
            trigger_time = chunk_start

        # Clamp trigger time to chunk boundaries
        if trigger_time < chunk_start or trigger_time > chunk_end:
            trigger_time = chunk_start

        return TimelineEntry(
            id=entry_id,
            kind="segment_explanation",
            start=trigger_time,
            end=chunk_end,
            title=title,
            markdown=markdown,
        )

    # =========================================================================
    # STORAGE
    # =========================================================================

    def _save_timeline(
        self,
        content_id: str,
        language: str,
        learner_profile: str | None,
        entries: list[TimelineEntry],
        *,
        total_units: int = 0,
        failed_units: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Save timeline to storage."""
        # Determine status based on failures
        status = ("error" if len(entries) == 0 else "partial_success") if failed_units > 0 else "ready"

        payload = {
            "video_id": content_id,  # Legacy API compatibility
            "language": language,
            "timeline": [entry.to_dict() for entry in entries],
            "status": status,
            "error": error_message,
        }

        # Include failure tracking info
        if total_units > 0:
            payload["total_units"] = total_units
        if failed_units > 0:
            payload["failed_units"] = failed_units

        if learner_profile:
            payload["learner_profile"] = learner_profile

        self._timelines.save(
            payload,
            content_id=content_id,
            language=language,
            learner_profile=learner_profile,
        )

    def _try_load_cached(self, content_id: str, language: str, learner_profile: str | None) -> TimelineResult | None:
        """Try to load cached timeline if it matches the learner profile."""
        payload = self._timelines.load(content_id, language)
        if not payload:
            return None

        cached_profile = (payload.get("learner_profile", "") or "").strip()
        current_profile = (learner_profile or "").strip()
        status = str(payload.get("status", "ready")).lower()

        # Cache is valid if profile matches and status is ready or partial_success
        if cached_profile != current_profile or status not in ("ready", "partial_success"):
            return None

        entries = self._parse_timeline_entries(payload.get("timeline", []))

        return TimelineResult(
            content_id=content_id,
            language=language,
            entries=entries,
            cached=True,
            status=status,
            total_units=payload.get("total_units", 0),
            failed_units=payload.get("failed_units", 0),
            error_message=payload.get("error"),
        )

    def _parse_timeline_entries(self, entries_raw: list) -> list[TimelineEntry]:
        """Parse timeline entries from storage format."""
        entries = []
        for item in entries_raw:
            try:
                entries.append(
                    TimelineEntry(
                        id=item["id"],
                        kind=item.get("kind", "segment_explanation"),
                        start=float(item["start"]),
                        end=float(item["end"]),
                        title=item.get("title", ""),
                        markdown=item.get("markdown", ""),
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Failed to parse timeline entry: %s", e)
                continue

        return entries

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _resolve_language(self, language: str) -> str:
        """Validate and return language (required from request)."""
        if not language or not language.strip():
            raise ValueError("language is required and must be provided from frontend request")
        return language.strip()
