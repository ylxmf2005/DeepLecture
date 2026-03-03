from __future__ import annotations

import contextlib
import json
import logging
import os
import uuid
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from deeplecture.domain import FeatureStatus, FeatureType, Segment
from deeplecture.use_cases.dto.slide import PageWorkPlan, SlideGenerationResult, TranscriptPage, TranscriptSegment
from deeplecture.use_cases.shared.context import build_slide_context_pdf_candidates
from deeplecture.use_cases.shared.llm_json import parse_llm_json

if TYPE_CHECKING:
    from deeplecture.config.settings import SlideLectureConfig
    from deeplecture.domain.entities.content import ContentMetadata
    from deeplecture.use_cases.dto.slide import SlideGenerationRequest
    from deeplecture.use_cases.interfaces.audio import AudioProcessorProtocol
    from deeplecture.use_cases.interfaces.llm_provider import LLMProviderProtocol
    from deeplecture.use_cases.interfaces.parallel import ParallelRunnerProtocol
    from deeplecture.use_cases.interfaces.path import PathResolverProtocol
    from deeplecture.use_cases.interfaces.pdf import PdfRendererProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol
    from deeplecture.use_cases.interfaces.services import LLMProtocol, TTSProtocol
    from deeplecture.use_cases.interfaces.storage import MetadataStorageProtocol
    from deeplecture.use_cases.interfaces.subtitle import SubtitleStorageProtocol
    from deeplecture.use_cases.interfaces.tts_provider import TTSProviderProtocol
    from deeplecture.use_cases.interfaces.upload import FileStorageProtocol
    from deeplecture.use_cases.interfaces.video import VideoProcessorProtocol

logger = logging.getLogger(__name__)


@dataclass
class _TranscriptHistory:
    transcripts: list[str] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)

    def blocks(
        self,
        *,
        transcript_lookback_pages: int,
        summary_lookback_pages: int,
        max_transcript_chars: int = 2500,
        max_summaries: int = 20,
    ) -> tuple[str, str]:
        if transcript_lookback_pages == 0:
            prev = ""
        elif transcript_lookback_pages > 0:
            prev = "\n\n".join(self.transcripts[-transcript_lookback_pages:])
        else:
            prev = "\n\n".join(self.transcripts)

        if len(prev) > max_transcript_chars:
            prev = "..." + prev[-max_transcript_chars:].lstrip()

        if summary_lookback_pages == 0:
            summaries = ""
        elif summary_lookback_pages > 0:
            summaries = "\n".join(self.summaries[-summary_lookback_pages:])
        else:
            summaries = "\n".join(self.summaries[-max_summaries:])

        return prev, summaries

    def after(self, page: TranscriptPage) -> None:
        page_text = "\n".join(seg.source for seg in page.segments if seg.source)
        if page_text:
            self.transcripts.append(page_text)
        if page.one_sentence_summary:
            self.summaries.append(f"Page {page.page_index}: {page.one_sentence_summary}")


class SlideLectureUseCase:
    def __init__(
        self,
        *,
        audio_processor: AudioProcessorProtocol,
        video_processor: VideoProcessorProtocol,
        file_storage: FileStorageProtocol,
        pdf_renderer: PdfRendererProtocol,
        tts_provider: TTSProviderProtocol,
        llm_provider: LLMProviderProtocol,
        prompt_registry: PromptRegistryProtocol,
        path_resolver: PathResolverProtocol,
        metadata_storage: MetadataStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        config: SlideLectureConfig,
        parallel_runner: ParallelRunnerProtocol,
    ) -> None:
        self._audio = audio_processor
        self._video = video_processor
        self._file_storage = file_storage
        self._pdf_renderer = pdf_renderer
        self._tts_provider = tts_provider
        self._llm_provider = llm_provider
        self._prompt_registry = prompt_registry
        self._paths = path_resolver
        self._metadata = metadata_storage
        self._subtitle_storage = subtitle_storage
        self._config = config
        self._parallel = parallel_runner

    def generate(self, request: SlideGenerationRequest) -> SlideGenerationResult:
        content_id = request.content_id
        cfg = self._config

        metadata = self._metadata.get(content_id)
        if metadata is None:
            raise ValueError(f"Content not found: {content_id}")

        output_dir = self._paths.ensure_content_dir(content_id, "slide_lecture")
        out_video = os.path.join(output_dir, f"{request.output_basename}.mp4")

        workspace_dir = os.path.join(self._paths.temp_dir, f"slide_lecture_{content_id}_{uuid.uuid4().hex}")
        pages_dir = os.path.join(workspace_dir, "pages")
        transcripts_dir = os.path.join(output_dir, "transcripts")
        audio_dir = os.path.join(workspace_dir, "audio")
        segments_dir = os.path.join(workspace_dir, "video_segments")

        self._file_storage.makedirs(workspace_dir)
        self._file_storage.makedirs(transcripts_dir)

        metadata = metadata.with_status(FeatureType.VIDEO.value, FeatureStatus.PROCESSING)
        self._metadata.save(metadata)

        try:
            pdf_path = self._resolve_pdf_path(content_id, metadata=metadata)
            page_images = self._render_pdf_pages(pdf_path=pdf_path, pages_dir=pages_dir)
            if not page_images:
                raise RuntimeError("No pages rendered")

            plans = self._plan_pages(
                page_images=page_images,
                transcripts_dir=transcripts_dir,
                audio_dir=audio_dir,
                segments_dir=segments_dir,
            )

            llm = self._llm_provider.get(request.llm_model)
            prompts = dict(request.prompts) if request.prompts else None
            history = _TranscriptHistory()

            pages_by_index: dict[int, TranscriptPage] = {}
            segment_durations_by_page: dict[int, list[tuple[int, float]]] = {}
            page_durations: dict[int, float] = {}

            ordered = sorted(plans, key=lambda p: p.page_index)
            last_page_index = ordered[-1].page_index

            # Stage 1: Sequential LLM calls (needs history from previous pages)
            for pos, plan in enumerate(ordered):
                images = [plan.image_path]
                if cfg.neighbor_images.strip().lower() in ("next", "prev_next") and pos + 1 < len(ordered):
                    images.append(ordered[pos + 1].image_path)

                prev_transcript, summaries = history.blocks(
                    transcript_lookback_pages=cfg.transcript_lookback_pages,
                    summary_lookback_pages=cfg.summary_lookback_pages,
                )
                try:
                    raw = self._generate_page_raw(
                        llm=llm,
                        deck_id=content_id,
                        page_index=plan.page_index,
                        total_pages=len(ordered),
                        source_language=request.source_language,
                        target_language=request.target_language,
                        neighbor_images=cfg.neighbor_images,
                        previous_transcript=prev_transcript,
                        accumulated_summaries=summaries,
                        images=images,
                        prompts=prompts,
                    )
                    page = self._parse_page_raw(
                        raw=raw,
                        deck_id=content_id,
                        page_index=plan.page_index,
                        source_language=request.source_language,
                        target_language=request.target_language,
                    )
                except Exception:
                    logger.exception("Page %d content generation failed", plan.page_index)
                    page = self._fallback_page(
                        content_id,
                        plan.page_index,
                        request.source_language,
                        request.target_language,
                    )
                self._write_page_json(page, plan.transcript_json_path)
                history.after(page)
                pages_by_index[plan.page_index] = page

            # Stage 2: Parallel TTS rendering
            tts_items = [
                (pages_by_index[plan.page_index], plan, plan.page_index == last_page_index) for plan in ordered
            ]

            def _render_tts(
                item: tuple[TranscriptPage, PageWorkPlan, bool],
            ) -> tuple[str, float, list[tuple[int, float]]]:
                page, plan, is_last = item
                return self._render_page_audio(
                    page,
                    plan,
                    is_last,
                    tts_language=request.tts_language,
                    tts_model=request.tts_model,
                )

            audio_results = self._parallel.map_ordered(
                tts_items,
                _render_tts,
                group="slide_lecture_tts",
            )

            page_audio: dict[int, str] = {}
            for plan, (wav_path, page_dur, seg_durs) in zip(ordered, audio_results, strict=False):
                page_audio[plan.page_index] = wav_path
                page_durations[plan.page_index] = page_dur
                segment_durations_by_page[plan.page_index] = seg_durs

            # Stage 3: Parallel video segment builds
            video_items = [
                (plan.image_path, page_durations[plan.page_index], plan.segment_video_path) for plan in ordered
            ]

            def _build_video(item: tuple[str, float, str]) -> str:
                image_path, duration, segment_path = item
                self._video.build_still_segment(image_path, duration, segment_path)
                return segment_path

            video_results = self._parallel.map_ordered(
                video_items,
                _build_video,
                group="slide_lecture_video",
            )

            ordered_audio_paths = [page_audio[p.page_index] for p in ordered]
            lecture_wav = os.path.join(output_dir, f"{request.output_basename}.wav")
            self._audio.concat_wavs_to_wav(ordered_audio_paths, lecture_wav)

            video_only = os.path.join(output_dir, f"{request.output_basename}_video_only.mp4")
            self._video.concat_segments(video_results, video_only)
            self._video.mux_audio(video_only, lecture_wav, out_video)

            audio_dur = self._audio.probe_duration_seconds(lecture_wav)
            video_dur = self._video.probe_duration(out_video)

            # Generate subtitles from transcript data
            # Delete any existing subtitles first to avoid stale data on failure
            ordered_page_indices = [p.page_index for p in ordered]
            source_enhanced_language = f"{request.source_language}_enhanced"
            with contextlib.suppress(Exception):
                self._subtitle_storage.delete(content_id, request.source_language)
                self._subtitle_storage.delete(content_id, source_enhanced_language)
                self._subtitle_storage.delete(content_id, request.target_language)

            try:
                segments_source, segments_target = self._build_subtitle_segments(
                    pages_by_index=pages_by_index,
                    ordered_page_indices=ordered_page_indices,
                    segment_durations_by_page=segment_durations_by_page,
                    page_durations=page_durations,
                )
                # Keep slide-lecture subtitle semantics aligned with enhance+translate:
                # source, source_enhanced, and target are all available.
                self._subtitle_storage.save(content_id, segments_source, request.source_language)
                self._subtitle_storage.save(content_id, segments_source, source_enhanced_language)
                self._subtitle_storage.save(content_id, segments_target, request.target_language)
                metadata = metadata.with_status(FeatureType.SUBTITLE.value, FeatureStatus.READY)
                metadata = metadata.with_status(FeatureType.ENHANCE_TRANSLATE.value, FeatureStatus.READY)
            except Exception:
                logger.exception("Subtitle generation failed for content_id=%s", content_id)
                metadata = metadata.with_status(FeatureType.SUBTITLE.value, FeatureStatus.ERROR)
                metadata = metadata.with_status(FeatureType.ENHANCE_TRANSLATE.value, FeatureStatus.ERROR)

            metadata = replace(
                metadata.with_status(FeatureType.VIDEO.value, FeatureStatus.READY),
                video_file=out_video,
                video_job_id=None,
            )
            self._metadata.save(metadata)

            return SlideGenerationResult(
                content_id=content_id,
                video_path=out_video,
                audio_wav_path=lecture_wav,
                page_count=len(ordered),
                audio_duration=audio_dur,
                video_duration=video_dur,
            )
        except Exception:
            metadata = metadata.with_status(FeatureType.VIDEO.value, FeatureStatus.ERROR)
            self._metadata.save(metadata)
            raise
        finally:
            if cfg.cleanup_temp:
                with contextlib.suppress(OSError):
                    self._file_storage.remove_dir(workspace_dir)

    def _resolve_pdf_path(self, content_id: str, *, metadata: ContentMetadata | None = None) -> str:
        candidates = build_slide_context_pdf_candidates(
            content_id,
            metadata=metadata,
            path_resolver=self._paths,
        )
        for p in candidates:
            if self._file_storage.file_exists(p):
                return p
        raise FileNotFoundError(f"PDF not found for {content_id}")

    def _render_pdf_pages(self, *, pdf_path: str, pages_dir: str) -> dict[int, str]:
        """Delegate PDF rendering to infrastructure via Protocol."""
        return self._pdf_renderer.render_pages_to_images(pdf_path, pages_dir, scale=2.0)

    def _plan_pages(
        self,
        *,
        page_images: dict[int, str],
        transcripts_dir: str,
        audio_dir: str,
        segments_dir: str,
    ) -> list[PageWorkPlan]:
        self._file_storage.makedirs(audio_dir)
        self._file_storage.makedirs(segments_dir)
        plans: list[PageWorkPlan] = []
        for page_index, image_path in sorted(page_images.items()):
            plans.append(
                PageWorkPlan(
                    page_index=page_index,
                    image_path=image_path,
                    transcript_json_path=os.path.join(transcripts_dir, f"page_{page_index:03d}.json"),
                    page_audio_wav_path=os.path.join(audio_dir, f"page_{page_index:03d}.wav"),
                    segment_video_path=os.path.join(segments_dir, f"page_{page_index:03d}.mp4"),
                )
            )
        return plans

    def _get_tts(self, tts_model: str | None) -> TTSProtocol:
        """Get TTS instance from provider."""
        return self._tts_provider.get(tts_model)

    def _render_page_audio(
        self,
        page: TranscriptPage,
        plan: PageWorkPlan,
        is_last_page: bool,
        *,
        tts_language: str,
        tts_model: str | None,
    ) -> tuple[str, float, list[tuple[int, float]]]:
        """Render page audio and collect segment durations for subtitle generation.

        Returns:
            Tuple of (wav_path, page_duration, segment_durations).
            segment_durations is a list of (segment_index, duration_seconds).
        """
        cfg = self._config
        self._file_storage.makedirs(os.path.dirname(plan.page_audio_wav_path))
        segment_wavs: list[str] = []
        segment_durations: list[tuple[int, float]] = []

        use_source = tts_language.lower() != "target"
        for seg_idx, seg in enumerate(page.segments, start=1):
            text = seg.source if use_source else seg.target
            text = (text or "").replace("\r", " ").strip()
            if not text:
                continue

            seg_wav = os.path.join(
                os.path.dirname(plan.page_audio_wav_path),
                f"seg_p{page.page_index:03d}_s{seg_idx:03d}.wav",
            )
            try:
                self._synthesize_to_wav(text=text, wav_path=seg_wav, sample_rate=cfg.sample_rate, tts_model=tts_model)
            except Exception:
                logger.warning(
                    "TTS synthesis failed for page=%d seg=%d, using 0.5s silence fallback",
                    page.page_index,
                    seg_idx,
                    exc_info=True,
                )
                self._audio.generate_silence_wav(seg_wav, duration=0.5, sample_rate=cfg.sample_rate)
            segment_wavs.append(seg_wav)

            seg_duration = self._audio.probe_duration_seconds(seg_wav)
            segment_durations.append((seg_idx, seg_duration))

        if not segment_wavs:
            self._audio.generate_silence_wav(plan.page_audio_wav_path, duration=1.0, sample_rate=cfg.sample_rate)
        else:
            self._audio.concat_wavs_to_wav(segment_wavs, plan.page_audio_wav_path)

        if not is_last_page and cfg.page_break_silence_seconds > 0:
            silence_wav = os.path.join(
                os.path.dirname(plan.page_audio_wav_path),
                f"silence_after_p{page.page_index:03d}.wav",
            )
            self._audio.generate_silence_wav(
                silence_wav,
                duration=cfg.page_break_silence_seconds,
                sample_rate=cfg.sample_rate,
            )
            tmp = os.path.join(
                os.path.dirname(plan.page_audio_wav_path), f"page_{page.page_index:03d}_with_silence.wav"
            )
            self._audio.concat_wavs_to_wav([plan.page_audio_wav_path, silence_wav], tmp)
            self._file_storage.replace_file(tmp, plan.page_audio_wav_path)

        duration = self._audio.probe_duration_seconds(plan.page_audio_wav_path)
        if duration <= 0:
            raise RuntimeError(f"Invalid page audio duration: page={page.page_index}")
        return plan.page_audio_wav_path, duration, segment_durations

    def _synthesize_to_wav(self, *, text: str, wav_path: str, sample_rate: int, tts_model: str | None) -> None:
        tts = self._get_tts(tts_model)
        raw_bytes = tts.synthesize(text)
        if not raw_bytes:
            raise RuntimeError("TTS returned empty audio")

        ext = getattr(tts, "file_extension", ".wav") or ".wav"
        ext = ext if ext.startswith(".") else f".{ext}"
        raw_path = f"{os.path.splitext(wav_path)[0]}_raw{ext}"

        self._file_storage.write_bytes(raw_path, raw_bytes)

        try:
            self._audio.transcode_to_wav(raw_path, wav_path, sample_rate=sample_rate, channels=1)
        finally:
            with contextlib.suppress(OSError):
                self._file_storage.remove_file(raw_path)

        if self._audio.probe_duration_seconds(wav_path) <= 0:
            raise RuntimeError("TTS produced invalid duration")

    def _generate_page_raw(
        self,
        *,
        llm: LLMProtocol,
        deck_id: str,
        page_index: int,
        total_pages: int,
        source_language: str,
        target_language: str,
        neighbor_images: str,
        previous_transcript: str,
        accumulated_summaries: str,
        images: list[str],
        prompts: dict[str, str] | None,
    ) -> str:
        impl_id = prompts.get("slide_lecture") if prompts else None
        prompt_builder = self._prompt_registry.get("slide_lecture", impl_id)
        spec = prompt_builder.build(
            deck_id=deck_id,
            page_index=page_index,
            total_pages=total_pages,
            source_language=source_language,
            target_language=target_language,
            neighbor_images=neighbor_images,
            previous_transcript=previous_transcript,
            accumulated_summaries=accumulated_summaries,
        )
        return llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
            image_path=images if len(images) > 1 else images[0],
        )

    def _parse_page_raw(
        self,
        *,
        raw: str,
        deck_id: str,
        page_index: int,
        source_language: str,
        target_language: str,
    ) -> TranscriptPage:
        data = parse_llm_json(raw, context="slide lecture page", allow_any_type=True)

        # Handle case where LLM returns segments array instead of full object
        if isinstance(data, list):
            logger.warning("LLM returned array instead of object for page %d, wrapping", page_index)
            data = {"segments": data}

        if not isinstance(data, dict):
            return self._fallback_page(deck_id, page_index, source_language, target_language)

        segs = data.get("segments")
        if not isinstance(segs, list) or not segs:
            return self._fallback_page(deck_id, page_index, source_language, target_language)

        segments: list[TranscriptSegment] = []
        for idx, item in enumerate(segs, start=1):
            if not isinstance(item, dict):
                continue
            try:
                seg_id = int(item.get("id", idx))
            except Exception:
                seg_id = idx
            source = str(item.get("source", "")).strip()
            target = str(item.get("target", "")).strip()
            if not source:
                continue
            segments.append(TranscriptSegment(id=seg_id, source=source, target=target))

        if not segments:
            return self._fallback_page(deck_id, page_index, source_language, target_language)

        summary = str(data.get("one_sentence_summary", "")).strip()
        return TranscriptPage(
            deck_id=deck_id,
            page_index=page_index,
            source_language=str(data.get("source_language", source_language)),
            target_language=str(data.get("target_language", target_language)),
            segments=segments,
            one_sentence_summary=summary,
        )

    def _fallback_page(
        self,
        deck_id: str,
        page_index: int,
        source_language: str,
        target_language: str,
    ) -> TranscriptPage:
        msg = f"[Content generation failed for page {page_index}]"
        return TranscriptPage(
            deck_id=deck_id,
            page_index=page_index,
            source_language=source_language,
            target_language=target_language,
            segments=[TranscriptSegment(id=1, source=msg, target=msg)],
            one_sentence_summary=f"Page {page_index} generation failed",
        )

    def _write_page_json(self, page: TranscriptPage, path: str) -> None:
        payload = {
            "deck_id": page.deck_id,
            "page_index": page.page_index,
            "source_language": page.source_language,
            "target_language": page.target_language,
            "one_sentence_summary": page.one_sentence_summary,
            "segments": [{"id": s.id, "source": s.source, "target": s.target} for s in page.segments],
        }
        self._file_storage.write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))

    def _build_subtitle_segments(
        self,
        *,
        pages_by_index: dict[int, TranscriptPage],
        ordered_page_indices: list[int],
        segment_durations_by_page: dict[int, list[tuple[int, float]]],
        page_durations: dict[int, float],
    ) -> tuple[list[Segment], list[Segment]]:
        """Convert transcript data to timed subtitle segments.

        Uses the audio duration of each rendered TTS segment to calculate
        precise timestamps. Applies proportional scaling to ensure segment
        durations sum to the spoken content duration (excluding any trailing
        page-break silence), avoiding drift/overlap.

        Returns:
            Tuple of (source_segments, target_segments) with proper timestamps.
        """
        segments_source: list[Segment] = []
        segments_target: list[Segment] = []
        offset = 0.0
        last_page_index = ordered_page_indices[-1] if ordered_page_indices else None

        for page_index in ordered_page_indices:
            page = pages_by_index.get(page_index)
            page_duration = page_durations.get(page_index, 0.0)

            if page is None:
                offset += page_duration
                continue

            seg_durs = segment_durations_by_page.get(page_index, [])
            if not seg_durs:
                offset += page_duration
                continue

            # Scale segments to fit within spoken content duration.
            # Non-last pages include trailing page-break silence; exclude it from scaling.
            is_last_page = page_index == last_page_index
            content_duration = page_duration
            if not is_last_page and self._config.page_break_silence_seconds > 0:
                content_duration = max(0.0, content_duration - self._config.page_break_silence_seconds)

            raw_sum = sum(dur for _, dur in seg_durs)
            scale = content_duration / raw_sum if raw_sum > 0 and content_duration > 0 else 1.0

            within_page_offset = 0.0
            for seg_idx, raw_duration in seg_durs:
                scaled_duration = raw_duration * scale
                start = offset + within_page_offset
                end = start + scaled_duration
                within_page_offset += scaled_duration

                # seg_idx is 1-based from enumerate(page.segments, start=1)
                if seg_idx < 1 or seg_idx > len(page.segments):
                    continue
                seg = page.segments[seg_idx - 1]

                source_text = (seg.source or "").strip()
                target_text = (seg.target or "").strip()

                if source_text:
                    segments_source.append(Segment(start=start, end=end, text=source_text))
                if target_text:
                    segments_target.append(Segment(start=start, end=end, text=target_text))

            offset += page_duration

        return segments_source, segments_target
