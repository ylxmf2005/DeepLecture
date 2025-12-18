"""Subtitle generation and translation use case."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from deeplecture.domain import FeatureStatus, FeatureType
from deeplecture.domain.errors import ContentNotFoundError, SubtitleGenerationError
from deeplecture.use_cases.dto.subtitle import (
    BackgroundContext,
    BilingualSegment,
    SubtitleResult,
)
from deeplecture.use_cases.shared.llm_json import parse_llm_json

if TYPE_CHECKING:
    from deeplecture.config import SubtitleEnhanceTranslateConfig
    from deeplecture.domain import Segment
    from deeplecture.use_cases.dto.subtitle import (
        EnhanceTranslateRequest,
        GenerateSubtitleRequest,
    )
    from deeplecture.use_cases.interfaces import (
        ASRProtocol,
        LLMProtocol,
        MetadataStorageProtocol,
        ParallelRunnerProtocol,
        SubtitleStorageProtocol,
    )
    from deeplecture.use_cases.interfaces.llm_provider import LLMProviderProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol

logger = logging.getLogger(__name__)


class SubtitleUseCase:
    """
    Subtitle generation, enhancement, and translation.

    Orchestrates:
    - ASR transcription (Whisper)
    - Background context extraction
    - Batch enhancement and translation with LLM
    - Subtitle storage
    - Metadata updates
    """

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        asr: ASRProtocol,
        llm_provider: LLMProviderProtocol,
        prompt_registry: PromptRegistryProtocol,
        config: SubtitleEnhanceTranslateConfig,
        parallel_runner: ParallelRunnerProtocol,
    ) -> None:
        self._metadata = metadata_storage
        self._subtitles = subtitle_storage
        self._asr = asr
        self._llm_provider = llm_provider
        self._prompt_registry = prompt_registry
        self._config = config
        self._parallel = parallel_runner

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def generate(self, request: GenerateSubtitleRequest) -> SubtitleResult:
        """
        Generate subtitles for content using ASR.

        1. Load content metadata
        2. Run ASR transcription
        3. Save subtitles
        4. Update metadata status
        """
        metadata = self._metadata.get(request.content_id)
        if metadata is None:
            raise ContentNotFoundError(request.content_id)

        # Mark as processing
        metadata = metadata.with_status(FeatureType.SUBTITLE.value, FeatureStatus.PROCESSING)
        self._metadata.save(metadata)

        try:
            # Run ASR
            video_path = Path(metadata.source_file)
            segments = self._asr.transcribe(video_path, language=request.language)

            # Save subtitles
            self._subtitles.save(request.content_id, segments, request.language)

            # Update status
            metadata = metadata.with_status(FeatureType.SUBTITLE.value, FeatureStatus.READY)
            self._metadata.save(metadata)

            return SubtitleResult(
                content_id=request.content_id,
                segments=segments,
                language=request.language,
            )

        except Exception as e:
            metadata = metadata.with_status(FeatureType.SUBTITLE.value, FeatureStatus.ERROR)
            self._metadata.save(metadata)
            logger.error("Subtitle generation failed: %s", e)
            raise SubtitleGenerationError(str(e)) from e

    def enhance_and_translate(
        self,
        request: EnhanceTranslateRequest,
    ) -> tuple[SubtitleResult, SubtitleResult, BackgroundContext]:
        """
        Enhance and translate existing subtitles.

        1. Load source subtitles
        2. Extract background context
        3. Process in batches (enhance + translate)
        4. Save enhanced and translated subtitles
        5. Update metadata

        Returns:
            (enhanced_result, translated_result, background)
        """
        # Get LLM instance from provider (uses request.llm_model or default)
        llm = self._llm_provider.get(request.llm_model)

        # Load source subtitles
        source_segments = self._subtitles.load(request.content_id, request.source_language)
        if not source_segments:
            raise SubtitleGenerationError(f"Source subtitles not found: {request.source_language}")

        metadata = self._metadata.get(request.content_id)
        if metadata is None:
            raise ContentNotFoundError(request.content_id)

        # Mark as processing
        metadata = metadata.with_status(FeatureType.ENHANCE_TRANSLATE.value, FeatureStatus.PROCESSING)
        self._metadata.save(metadata)

        try:
            # 1. Extract background context
            background = self._extract_background(source_segments, llm, request.prompts)
            logger.info("Background extracted: topic=%s", background.topic)

            # 2. Process in batches
            bilingual_segments = self._process_batches(
                source_segments,
                background,
                request.target_language,
                llm,
                request.prompts,
            )

            # 3. Convert to separate enhanced/translated results
            enhanced_segments = [seg.to_source_segment() for seg in bilingual_segments]
            translated_segments = [seg.to_target_segment() for seg in bilingual_segments]

            # 4. Save both
            self._subtitles.save(
                request.content_id,
                enhanced_segments,
                f"{request.source_language}_enhanced",
            )
            self._subtitles.save(
                request.content_id,
                translated_segments,
                request.target_language,
            )

            # 5. Save background context (best-effort, non-critical)
            try:
                self._subtitles.save_background(request.content_id, background.to_dict())
            except (OSError, ValueError, TypeError) as e:
                logger.warning("Background save skipped for %s: %s", request.content_id, e)

            # 6. Update status
            metadata = metadata.with_status(FeatureType.ENHANCE_TRANSLATE.value, FeatureStatus.READY)
            self._metadata.save(metadata)

            return (
                SubtitleResult(
                    content_id=request.content_id,
                    segments=enhanced_segments,
                    language=request.source_language,
                ),
                SubtitleResult(
                    content_id=request.content_id,
                    segments=translated_segments,
                    language=request.target_language,
                ),
                background,
            )

        except Exception as e:
            metadata = metadata.with_status(FeatureType.ENHANCE_TRANSLATE.value, FeatureStatus.ERROR)
            self._metadata.save(metadata)
            logger.error("Enhancement/translation failed: %s", e)
            raise SubtitleGenerationError(str(e)) from e

    def get_subtitles(self, content_id: str, language: str) -> SubtitleResult | None:
        """Get existing subtitles."""
        segments = self._subtitles.load(content_id, language)
        if not segments:
            return None
        return SubtitleResult(
            content_id=content_id,
            segments=segments,
            language=language,
        )

    # =========================================================================
    # BACKGROUND EXTRACTION
    # =========================================================================

    def _extract_background(
        self,
        segments: list[Segment],
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> BackgroundContext:
        """Extract background context from transcript."""
        # Build transcript text (limited to max chars)
        transcript = "\n".join(seg.text.strip() for seg in segments)
        if len(transcript) > self._config.background_max_chars:
            transcript = transcript[: self._config.background_max_chars]

        # Get prompt builder from registry
        impl_id = prompts.get("subtitle_background") if prompts else None
        prompt_builder = self._prompt_registry.get("subtitle_background", impl_id)
        spec = prompt_builder.build(transcript=transcript)

        try:
            raw = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)
            data = parse_llm_json(raw, context="background context")

            return BackgroundContext(
                topic=data.get("topic", ""),
                summary=data.get("summary", ""),
                keywords=data.get("keywords", []),
                tone=data.get("tone", "neutral"),
            )
        except Exception as e:
            logger.error("Failed to extract background: %s", e)
            return BackgroundContext()

    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================

    def _process_batches(
        self,
        segments: list[Segment],
        background: BackgroundContext,
        target_language: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[BilingualSegment]:
        """Process segments in batches with concurrency."""
        # Split into batches
        batch_size = self._config.batch_size
        batches = [segments[i : i + batch_size] for i in range(0, len(segments), batch_size)]
        results = self._parallel.map_ordered(
            batches,
            lambda batch: self._process_batch(batch, background, target_language, llm, prompts),
            group="subtitle_batches",
            on_error=lambda exc, batch: self._fallback_batch(batch, str(exc)),
        )

        # Flatten and merge overlapping
        flat = [seg for batch in results for seg in batch]
        return self._merge_overlapping(flat)

    def _process_batch(
        self,
        batch: list[Segment],
        background: BackgroundContext,
        target_language: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[BilingualSegment]:
        """Process a single batch."""
        # Get prompt builder from registry
        impl_id = prompts.get("subtitle_enhance_translate") if prompts else None
        prompt_builder = self._prompt_registry.get("subtitle_enhance_translate", impl_id)
        spec = prompt_builder.build(
            background=background.to_dict(),
            segments=batch,
            target_language=target_language,
        )

        raw = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)
        data = parse_llm_json(raw, context="subtitle enhance batch")
        subtitles = data.get("subtitles", [])

        if not subtitles:
            logger.warning("No subtitles returned from LLM")
            return self._fallback_batch(batch)

        # Map LLM output back to timestamps
        processed = []
        for item in subtitles:
            try:
                start_idx = int(item.get("start_index", 0)) - 1  # 1-based to 0-based
                end_idx = int(item.get("end_index", 0)) - 1

                if start_idx < 0 or end_idx >= len(batch) or start_idx > end_idx:
                    continue

                processed.append(
                    BilingualSegment(
                        start=batch[start_idx].start,
                        end=batch[end_idx].end,
                        # Backward compatible: accept both new (text_source/text_target)
                        # and legacy (text_en/text_zh) field names from LLM output
                        text_source=(item.get("text_source") or item.get("text_en") or "").strip(),
                        text_target=(item.get("text_target") or item.get("text_zh") or "").strip(),
                    )
                )
            except (ValueError, IndexError):
                continue

        return processed

    def _fallback_batch(
        self,
        batch: list[Segment],
        error: str | None = None,
    ) -> list[BilingualSegment]:
        """Fallback when LLM fails."""
        reason = error or "Unknown error"
        error_msg = f"[Translation failed: {reason}]"

        return [
            BilingualSegment(
                start=seg.start,
                end=seg.end,
                text_source=seg.text.strip(),
                text_target=error_msg,
            )
            for seg in batch
        ]

    def _merge_overlapping(
        self,
        segments: list[BilingualSegment],
    ) -> list[BilingualSegment]:
        """Merge segments with overlapping timestamps."""
        if not segments:
            return segments

        # Sort by start time
        sorted_segs = sorted(segments, key=lambda x: x.start)
        merged = [sorted_segs[0]]

        for current in sorted_segs[1:]:
            prev = merged[-1]

            # Check overlap (0.1s tolerance)
            overlap = abs(current.start - prev.start) < 0.1 or current.start < prev.end - 0.1

            if overlap:
                # Merge
                prev.end = max(prev.end, current.end)

                if current.text_source and current.text_source not in prev.text_source:
                    prev.text_source = f"{prev.text_source} {current.text_source}".strip()

                if current.text_target and current.text_target not in prev.text_target:
                    prev.text_target = f"{prev.text_target} {current.text_target}".strip()
            else:
                merged.append(current)

        if len(merged) < len(segments):
            logger.info(
                "Merged %d overlapping segments (%d -> %d)",
                len(segments) - len(merged),
                len(segments),
                len(merged),
            )

        return merged

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @staticmethod
    def convert_srt_to_vtt(srt_content: str) -> str:
        """Convert SRT to WebVTT format."""
        content = srt_content.replace("\r\n", "\n").replace("\r", "\n")
        blocks = content.strip().split("\n\n")
        vtt_lines = ["WEBVTT", ""]

        for block in blocks:
            lines = block.split("\n")
            if len(lines) < 3:
                continue

            vtt_lines.append(lines[0])

            timestamp_line = lines[1].replace(",", ".")
            if "-->" in timestamp_line:
                timestamp_line += " line:85%"
            vtt_lines.append(timestamp_line)

            text_lines = lines[2:]
            cleaned = []
            for line in text_lines:
                line = re.sub(r"<[^>]+>", "", line)
                line = re.sub(r"\{.*?\}", "", line)
                cleaned.append(line)

            vtt_lines.append("\n".join(cleaned))
            vtt_lines.append("")

        return "\n".join(vtt_lines)
