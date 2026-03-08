"""Podcast generation use case.

Three-stage LLM pipeline + dual TTS synthesis for creating NotebookLM-style
two-person dialogue podcasts:

1. Extraction: Reuse cheatsheet knowledge extraction (shared Stage 1)
2. Dialogue generation: Convert KnowledgeItems into structured two-person dialogue
3. Dramatization: Rewrite dialogue for natural TTS delivery
4. TTS synthesis: Parallel synthesis with different models per speaker
5. Audio merge: Interleave segments with silence gaps, export as M4A
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from typing import TYPE_CHECKING, Any

from deeplecture.use_cases.dto.podcast import (
    DialogueItem,
    GeneratedPodcastResult,
    PodcastResult,
    PodcastSegment,
    PodcastStats,
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
    from deeplecture.use_cases.dto.podcast import GeneratePodcastRequest
    from deeplecture.use_cases.interfaces import (
        AudioProcessorProtocol,
        FileStorageProtocol,
        LLMProtocol,
        LLMProviderProtocol,
        MetadataStorageProtocol,
        ParallelRunnerProtocol,
        PathResolverProtocol,
        PdfTextExtractorProtocol,
        TTSProtocol,
        TTSProviderProtocol,
    )
    from deeplecture.use_cases.interfaces.podcast import PodcastStorageProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol
    from deeplecture.use_cases.interfaces.subtitle import SubtitleStorageProtocol

logger = logging.getLogger(__name__)

# Maximum dialogue turns to prevent runaway LLM output
MAX_DIALOGUE_ITEMS = 500
# TTS failure threshold — abort if more than this fraction fails
TTS_FAILURE_THRESHOLD = 0.5
# Target sample rate for all WAV intermediates
SAMPLE_RATE = 24000


class PodcastUseCase:
    """Three-stage podcast generation use case.

    Stage 1 (Extraction): Reuse cheatsheet knowledge extraction
    Stage 2 (Dialogue): Generate two-person dialogue from knowledge items
    Stage 3 (Dramatization): Rewrite dialogue for natural TTS delivery
    Stage 4 (TTS): Parallel synthesis with per-speaker TTS models
    Stage 5 (Merge): Interleave audio segments with silence, export M4A
    """

    def __init__(
        self,
        *,
        podcast_storage: PodcastStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        llm_provider: LLMProviderProtocol,
        tts_provider: TTSProviderProtocol,
        audio_processor: AudioProcessorProtocol,
        file_storage: FileStorageProtocol,
        path_resolver: PathResolverProtocol,
        prompt_registry: PromptRegistryProtocol,
        parallel_runner: ParallelRunnerProtocol,
        metadata_storage: MetadataStorageProtocol | None = None,
        pdf_text_extractor: PdfTextExtractorProtocol | None = None,
    ) -> None:
        self._podcasts = podcast_storage
        self._subtitles = subtitle_storage
        self._llm_provider = llm_provider
        self._tts_provider = tts_provider
        self._audio = audio_processor
        self._file_storage = file_storage
        self._paths = path_resolver
        self._prompt_registry = prompt_registry
        self._parallel_runner = parallel_runner
        self._metadata = metadata_storage
        self._pdf_text_extractor = pdf_text_extractor

    # =========================================================================
    # Public API
    # =========================================================================

    def get(self, content_id: str, language: str | None = None) -> PodcastResult:
        """Get existing podcast.

        Args:
            content_id: Content identifier
            language: Language filter (optional)

        Returns:
            PodcastResult with segments and metadata
        """
        result = self._podcasts.load(content_id, language)
        if result is None:
            return PodcastResult(content_id=content_id, language=language or "")

        data, updated_at = result
        segments = [PodcastSegment.from_dict(s) for s in data.get("segments", [])]
        return PodcastResult(
            content_id=content_id,
            language=data.get("language", language or ""),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            segments=segments,
            duration=float(data.get("duration", 0)),
            updated_at=updated_at,
        )

    def generate(self, request: GeneratePodcastRequest) -> GeneratedPodcastResult:
        """Generate a podcast using the three-stage LLM + TTS pipeline.

        Args:
            request: Generation request with parameters

        Returns:
            Generated podcast result

        Raises:
            ValueError: If no content sources available or dialogue is empty
            RuntimeError: If TTS failure rate exceeds threshold
        """
        llm = self._llm_provider.get(request.llm_model)

        # --- Stage 1: Knowledge Extraction (shared with quiz/cheatsheet/flashcard) ---
        context, used_sources = self._load_context(request)
        if not context.strip():
            raise ValueError(f"No content available for {request.content_id}")

        instruction = sanitize_question(request.user_instruction)

        knowledge_items = self._extract_knowledge_items(
            context=context,
            language=request.language,
            subject_type=request.subject_type,
            user_instruction=instruction,
            llm=llm,
            prompts=request.prompts,
        )

        if not knowledge_items:
            raise ValueError("Knowledge extraction produced no items")

        # --- Stage 2: Dialogue Generation ---
        raw_dialogue = self._generate_dialogue(
            items=knowledge_items,
            language=request.language,
            user_instruction=instruction,
            llm=llm,
            prompts=request.prompts,
        )
        dialogue_items = self._validate_dialogue(raw_dialogue)

        if not dialogue_items:
            raise ValueError("Dialogue generation produced no valid items")

        # --- Stage 3: Dramatization ---
        dramatized = self._dramatize_dialogue(
            dialogue_items=dialogue_items,
            language=request.language,
            user_instruction=instruction,
            llm=llm,
            prompts=request.prompts,
        )
        # Fallback: if dramatization fails or returns empty, use original
        if not dramatized:
            logger.warning("Dramatization returned empty, falling back to raw dialogue")
            dramatized = dialogue_items

        # --- Stage 4: Parallel TTS Synthesis ---
        segments_dir = self._prepare_segments_dir(request.content_id, request.language)
        tts_host = self._tts_provider.get(request.tts_model_host)
        tts_guest = self._tts_provider.get(request.tts_model_guest)

        segment_results = self._synthesize_all_segments(
            dialogue_items=dramatized,
            tts_host=tts_host,
            tts_guest=tts_guest,
            voice_host=request.voice_id_host,
            voice_guest=request.voice_id_guest,
            segments_dir=segments_dir,
        )

        # --- Stage 5: Audio Merge + Timestamp Calculation ---
        audio_path = self._podcasts.get_audio_path(request.content_id, request.language)
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)

        turn_gap = request.turn_gap_seconds
        segments, stats = self._merge_and_calculate_timestamps(
            segment_results=segment_results,
            output_path=audio_path,
            turn_gap=turn_gap,
        )

        # Cleanup intermediate segment WAVs
        self._cleanup_dir(segments_dir)

        # Save manifest
        title = raw_dialogue.get("title", "Podcast") if isinstance(raw_dialogue, dict) else "Podcast"
        summary = raw_dialogue.get("summary", "") if isinstance(raw_dialogue, dict) else ""
        total_duration = segments[-1].end_time if segments else 0.0

        data = {
            "title": title,
            "summary": summary,
            "segments": [s.to_dict() for s in segments],
            "duration": total_duration,
            "language": request.language,
            "stats": stats.to_dict(),
        }
        updated_at = self._podcasts.save(request.content_id, request.language, data)

        return GeneratedPodcastResult(
            content_id=request.content_id,
            language=request.language,
            title=title,
            summary=summary,
            segments=segments,
            duration=total_duration,
            updated_at=updated_at,
            used_sources=used_sources,
            stats=stats,
        )

    # =========================================================================
    # Stage 1: Content Loading & Knowledge Extraction
    # =========================================================================

    def _load_context(
        self,
        request: GeneratePodcastRequest,
    ) -> tuple[str, list[str]]:
        """Load content context from subtitle/slide sources."""
        mode = (request.context_mode or "both").strip().lower()
        used_sources: list[str] = []
        context_parts: list[str] = []

        subtitle_text = self._load_subtitle_context(request.content_id)
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

    def _load_subtitle_context(self, content_id: str) -> str:
        """Load subtitle text as plain text (no timestamps needed for podcast)."""
        candidate_languages = prioritize_subtitle_languages(
            self._subtitles.list_languages(content_id),
        )
        loaded = load_first_available_subtitle_segments(
            self._subtitles,
            content_id=content_id,
            candidate_languages=candidate_languages,
        )
        if loaded:
            _, segments = loaded
            lines = [seg.text.replace("\n", " ").strip() for seg in segments if seg.text.strip()]
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
                raise ValueError("Cannot generate podcast: no transcript or slides available.")
            return has_subtitle, has_slide
        raise ValueError("Unsupported context_mode. Allowed: 'subtitle', 'slide', 'both'.")

    def _extract_knowledge_items(
        self,
        context: str,
        language: str,
        subject_type: str,
        user_instruction: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[KnowledgeItem]:
        """Stage 1: Extract knowledge items from content (reuses cheatsheet extraction)."""
        from deeplecture.use_cases.dto.cheatsheet import KnowledgeItem

        impl_id = prompts.get("cheatsheet_extraction") if prompts else None
        prompt_builder = self._prompt_registry.get("cheatsheet_extraction", impl_id)
        spec = prompt_builder.build(
            context=context,
            language=language,
            subject_type=subject_type,
            user_instruction=user_instruction,
            coverage_mode="comprehensive",
        )

        response = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)
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

    # =========================================================================
    # Stage 2: Dialogue Generation
    # =========================================================================

    def _generate_dialogue(
        self,
        items: list[KnowledgeItem],
        language: str,
        user_instruction: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Stage 2: Generate structured two-person dialogue from knowledge items."""
        items_json = json.dumps(
            [item.to_dict() for item in items],
            ensure_ascii=False,
            indent=2,
        )

        impl_id = prompts.get("podcast_dialogue") if prompts else None
        prompt_builder = self._prompt_registry.get("podcast_dialogue", impl_id)
        spec = prompt_builder.build(
            knowledge_items_json=items_json,
            language=language,
            user_instruction=user_instruction,
        )

        response = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)
        return parse_llm_json(response, default_type=dict, context="podcast dialogue")

    def _validate_dialogue(self, raw: dict[str, Any]) -> list[DialogueItem]:
        """Validate and truncate dialogue items."""
        dialogue_list = raw.get("dialogue", []) if isinstance(raw, dict) else []
        items: list[DialogueItem] = []

        for entry in dialogue_list:
            if not isinstance(entry, dict):
                continue
            speaker = entry.get("speaker", "")
            text = entry.get("text", "")
            if speaker in ("host", "guest") and text.strip():
                items.append(DialogueItem(speaker=speaker, text=text.strip()))

        if len(items) > MAX_DIALOGUE_ITEMS:
            logger.warning(
                "Dialogue has %d items, truncating to %d",
                len(items),
                MAX_DIALOGUE_ITEMS,
            )
            items = items[:MAX_DIALOGUE_ITEMS]

        return items

    # =========================================================================
    # Stage 3: Dramatization
    # =========================================================================

    def _dramatize_dialogue(
        self,
        dialogue_items: list[DialogueItem],
        language: str,
        user_instruction: str,
        llm: LLMProtocol,
        prompts: dict[str, str] | None,
    ) -> list[DialogueItem]:
        """Stage 3: Rewrite dialogue for natural TTS delivery."""
        dialogue_json = json.dumps(
            {
                "dialogue": [item.to_dict() for item in dialogue_items],
            },
            ensure_ascii=False,
            indent=2,
        )

        impl_id = prompts.get("podcast_dramatize") if prompts else None
        prompt_builder = self._prompt_registry.get("podcast_dramatize", impl_id)
        spec = prompt_builder.build(
            dialogue_json=dialogue_json,
            language=language,
            user_instruction=user_instruction,
        )

        response = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)
        result = parse_llm_json(response, default_type=dict, context="podcast dramatize")

        dramatized: list[DialogueItem] = []
        for entry in result.get("dialogue", []) if isinstance(result, dict) else []:
            if not isinstance(entry, dict):
                continue
            speaker = entry.get("speaker", "")
            text = entry.get("text", "")
            if speaker in ("host", "guest") and text.strip():
                dramatized.append(DialogueItem(speaker=speaker, text=text.strip()))

        # Cap dramatized output too
        if len(dramatized) > MAX_DIALOGUE_ITEMS:
            dramatized = dramatized[:MAX_DIALOGUE_ITEMS]

        return dramatized

    # =========================================================================
    # Stage 4: Parallel TTS Synthesis
    # =========================================================================

    def _prepare_segments_dir(self, content_id: str, language: str) -> str:
        """Create temporary directory for intermediate segment WAVs."""
        base = os.path.dirname(self._podcasts.get_audio_path(content_id, language))
        segments_dir = os.path.join(base, f"{language}_segments")
        os.makedirs(segments_dir, exist_ok=True)
        return segments_dir

    def _synthesize_all_segments(
        self,
        dialogue_items: list[DialogueItem],
        tts_host: TTSProtocol,
        tts_guest: TTSProtocol,
        voice_host: str | None,
        voice_guest: str | None,
        segments_dir: str,
    ) -> list[_SegmentResult]:
        """Synthesize all dialogue items to WAV files using parallel TTS."""
        indexed_items = list(enumerate(dialogue_items))

        def _synth_one(idx_item: tuple[int, DialogueItem]) -> _SegmentResult:
            idx, item = idx_item
            tts = tts_host if item.speaker == "host" else tts_guest
            voice = voice_host if item.speaker == "host" else voice_guest
            wav_path = os.path.join(segments_dir, f"{idx:03d}_{item.speaker}.wav")

            try:
                raw_bytes = tts.synthesize(item.text, voice=voice)
                if not raw_bytes:
                    raise RuntimeError("TTS returned empty audio")

                ext = getattr(tts, "file_extension", ".wav") or ".wav"
                ext = ext if ext.startswith(".") else f".{ext}"
                raw_path = os.path.join(segments_dir, f"{idx:03d}_raw{ext}")
                self._file_storage.write_bytes(raw_path, raw_bytes)

                try:
                    self._audio.transcode_to_wav(raw_path, wav_path, sample_rate=SAMPLE_RATE, channels=1)
                finally:
                    with contextlib.suppress(OSError):
                        self._file_storage.remove_file(raw_path)

                duration = self._audio.probe_duration_seconds(wav_path)
                if duration <= 0:
                    raise RuntimeError("TTS produced invalid duration")

                return _SegmentResult(
                    index=idx,
                    speaker=item.speaker,
                    text=item.text,
                    wav_path=wav_path,
                    duration=duration,
                    success=True,
                )
            except Exception:
                logger.warning(
                    "TTS failed for segment %d (%s), generating silence fallback",
                    idx,
                    item.speaker,
                    exc_info=True,
                )
                self._audio.generate_silence_wav(wav_path, duration=0.5, sample_rate=SAMPLE_RATE, channels=1)
                return _SegmentResult(
                    index=idx,
                    speaker=item.speaker,
                    text=item.text,
                    wav_path=wav_path,
                    duration=0.5,
                    success=False,
                )

        results = self._parallel_runner.map_ordered(
            indexed_items,
            _synth_one,
            group="podcast_tts",
        )

        # Check failure rate
        total = len(results)
        failures = sum(1 for r in results if not r.success)
        if total > 0 and failures / total > TTS_FAILURE_THRESHOLD:
            raise RuntimeError(
                f"TTS failure rate too high: {failures}/{total} segments failed "
                f"(threshold: {TTS_FAILURE_THRESHOLD:.0%})"
            )

        return results

    # =========================================================================
    # Stage 5: Audio Merge + Timestamp Calculation
    # =========================================================================

    def _merge_and_calculate_timestamps(
        self,
        segment_results: list[_SegmentResult],
        output_path: str,
        turn_gap: float,
    ) -> tuple[list[PodcastSegment], PodcastStats]:
        """Merge segment WAVs into a single M4A with timestamps."""
        if not segment_results:
            return [], PodcastStats()

        # Generate silence WAV for inter-turn gaps
        silence_path: str | None = None
        if turn_gap > 0:
            silence_path = os.path.join(os.path.dirname(output_path), "_turn_silence.wav")
            self._audio.generate_silence_wav(
                silence_path,
                duration=turn_gap,
                sample_rate=SAMPLE_RATE,
                channels=1,
            )

        ordered_paths: list[str] = []
        segments: list[PodcastSegment] = []
        current_time = 0.0
        tts_success = 0
        tts_failure = 0

        for result in segment_results:
            # Insert silence between turns
            if result.index > 0 and silence_path:
                ordered_paths.append(silence_path)
                current_time += turn_gap

            ordered_paths.append(result.wav_path)
            segments.append(
                PodcastSegment(
                    speaker=result.speaker,
                    text=result.text,
                    start_time=current_time,
                    end_time=current_time + result.duration,
                )
            )
            current_time += result.duration

            if result.success:
                tts_success += 1
            else:
                tts_failure += 1

        # Merge to M4A
        self._audio.concat_wavs_to_m4a(ordered_paths, output_path, bitrate="192k")

        # Cleanup silence file
        if silence_path:
            with contextlib.suppress(OSError):
                os.remove(silence_path)

        stats = PodcastStats(
            total_dialogue_items=len(segment_results),
            tts_success_count=tts_success,
            tts_failure_count=tts_failure,
        )
        return segments, stats

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _cleanup_dir(dir_path: str) -> None:
        """Remove intermediate segment directory and its contents."""
        with contextlib.suppress(OSError):
            for f in os.listdir(dir_path):
                with contextlib.suppress(OSError):
                    os.remove(os.path.join(dir_path, f))
            os.rmdir(dir_path)


class _SegmentResult:
    """Internal result holder for a single TTS segment."""

    __slots__ = ("duration", "index", "speaker", "success", "text", "wav_path")

    def __init__(
        self,
        *,
        index: int,
        speaker: str,
        text: str,
        wav_path: str,
        duration: float,
        success: bool,
    ) -> None:
        self.index = index
        self.speaker = speaker
        self.text = text
        self.wav_path = wav_path
        self.duration = duration
        self.success = success
