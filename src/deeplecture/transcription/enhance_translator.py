import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    import json_repair
except ImportError:
    import json as json_repair

from deeplecture.config.config import load_config
from deeplecture.llm.llm_factory import LLM
from deeplecture.prompts.enhance_translate_prompt import (
    build_background_prompt,
    build_enhance_and_translate_prompt,
)
from deeplecture.transcription.interactive import SubtitleSegment, parse_srt_to_segments
from deeplecture.infra.parallel_pool import ResourceWorkerPool

logger = logging.getLogger(__name__)


class SubtitleEnhanceTranslator:
    """
    Service to enhance and translate subtitles in a single pass.
    """

    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        
        config = load_config()
        subtitle_cfg = (config or {}).get("subtitle") or {}
        # Use a larger batch size as requested
        self.batch_size = 50
        self.max_concurrency = int(subtitle_cfg.get("translation", {}).get("max_concurrency", 5))
        self.background_max_chars = 8000

        self._batch_pool = ResourceWorkerPool(
            name="subtitle_enhance_batches",
            max_workers=self.max_concurrency,
            resource_factory=lambda: self.llm,
        )

    def process_subtitles(
        self,
        srt_content: str,
        target_language: str = "zh",
    ) -> str:
        """
        Main entry point: Enhance and translate SRT content.

        Returns the new bilingual SRT content. Callers that need access
        to the structured entries or background JSON should use
        `process_to_entries` instead.
        """
        entries, _background = self.process_to_entries(
            srt_content,
            target_language=target_language,
        )
        return self._reconstruct_srt(entries)

    def process_to_entries(
        self,
        srt_content: str,
        target_language: str = "zh",
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Enhance and translate SRT content and return:
        - structured subtitle entries with timing and bilingual text
        - background context JSON extracted from the transcript
        """
        segments = parse_srt_to_segments(srt_content)
        if not segments:
            raise ValueError("No subtitle segments found")

        # 1. Build background context
        background = self.build_background(segments)
        logger.info("Background context extracted: %s", background.get("topic"))

        # 2. Process in batches
        processed_entries = self._process_all_batches(segments, background, target_language)

        return processed_entries, background

    def build_background(self, segments: List[SubtitleSegment]) -> Dict[str, Any]:
        """
        Extract background context from the full transcript.
        """
        transcript_text = "\n".join(seg.text.strip() for seg in segments)
        if len(transcript_text) > self.background_max_chars:
            transcript_text = transcript_text[: self.background_max_chars]

        user_prompt, system_prompt = build_background_prompt(transcript_text)

        try:
            raw = self.llm.generate_response(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            return self._parse_json(raw)
        except Exception as e:
            logger.warning("Failed to extract background: %s", e)
            return {}

    def _process_all_batches(
        self,
        segments: List[SubtitleSegment],
        background: Dict[str, Any],
        target_language: str,
    ) -> List[Dict[str, Any]]:
        """
        Split segments into batches and process them (concurrently if configured).
        """
        batches = [
            segments[i : i + self.batch_size]
            for i in range(0, len(segments), self.batch_size)
        ]
        
        results: List[Optional[List[Dict[str, Any]]]] = [None] * len(batches)

        def handler(_llm: LLM, idx: int, batch: List[SubtitleSegment]) -> List[Dict[str, Any]]:
            return self._process_batch(batch, background, target_language)

        def handle_error(exc: BaseException, idx: int) -> List[Dict[str, Any]]:
            logger.error("Batch processing failed: %s", exc)
            return self._fallback_batch(batches[idx], exc)

        mapped = self._batch_pool.map(
            list(enumerate(batches)),
            handler,
            on_error=handle_error,
        )

        for idx, value in mapped.items():
            results[idx] = value

        # Flatten results
        flat_results = []
        for batch_res in results:
            if batch_res:
                flat_results.extend(batch_res)

        # Post-process: merge overlapping subtitles
        return self._merge_overlapping(flat_results)

    def _merge_overlapping(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge subtitles that have overlapping or identical timestamps.

        Two subtitles are considered overlapping if:
        - They have the same start time, OR
        - The second starts before the first ends (with 0.1s tolerance)
        """
        if not entries:
            return entries

        # Sort by start time
        sorted_entries = sorted(entries, key=lambda x: x["start"])
        merged = [sorted_entries[0]]

        for current in sorted_entries[1:]:
            prev = merged[-1]

            # Check for overlap: same start OR current starts before prev ends
            # Use 0.1s tolerance
            overlap = (
                abs(current["start"] - prev["start"]) < 0.1 or
                current["start"] < prev["end"] - 0.1
            )

            if overlap:
                # Merge: extend end time, concatenate text
                prev["end"] = max(prev["end"], current["end"])

                prev_en = prev.get("text_en", "").strip()
                curr_en = current.get("text_en", "").strip()
                if curr_en and curr_en not in prev_en:
                    prev["text_en"] = f"{prev_en} {curr_en}".strip()

                prev_zh = prev.get("text_zh", "").strip()
                curr_zh = current.get("text_zh", "").strip()
                if curr_zh and curr_zh not in prev_zh:
                    prev["text_zh"] = f"{prev_zh} {curr_zh}".strip()

                logger.debug(
                    "Merged overlapping subtitles at %.2fs-%.2fs",
                    prev["start"], prev["end"]
                )
            else:
                merged.append(current)

        if len(merged) < len(entries):
            logger.info(
                "Merged %d overlapping subtitles (%d -> %d)",
                len(entries) - len(merged), len(entries), len(merged)
            )

        return merged

    def _process_batch(
        self,
        batch: List[SubtitleSegment],
        background: Dict[str, Any],
        target_language: str,
    ) -> List[Dict[str, Any]]:
        """
        Process a single batch of segments.
        """
        user_prompt, system_prompt = build_enhance_and_translate_prompt(
            background, batch, target_language
        )

        raw = self.llm.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )
        
        data = self._parse_json(raw)
        subtitles = data.get("subtitles", [])
        
        if not subtitles:
            logger.warning("No subtitles returned from LLM for batch")
            return self._fallback_batch(batch)

        # Map LLM output back to timestamps
        # The LLM returns start_index and end_index (1-based relative to the batch)
        processed = []
        for item in subtitles:
            try:
                start_idx = int(item.get("start_index", 0)) - 1
                end_idx = int(item.get("end_index", 0)) - 1
                
                # Validation
                if start_idx < 0 or end_idx >= len(batch) or start_idx > end_idx:
                    continue
                
                # Calculate time range from original segments
                start_time = batch[start_idx].start
                end_time = batch[end_idx].end
                
                processed.append({
                    "start": start_time,
                    "end": end_time,
                    "text_en": item.get("text_en", "").strip(),
                    "text_zh": item.get("text_zh", "").strip(),
                })
            except (ValueError, IndexError):
                continue
                
        return processed

    def _fallback_batch(
        self, batch: List[SubtitleSegment], exc: Optional[BaseException] = None
    ) -> List[Dict[str, Any]]:
        """
        Fallback if LLM fails: return error message instead of original text.
        This prevents showing duplicate English when translation fails.
        """
        reason = str(exc) if exc else "Unknown error"
        error_msg = f"[Translation failed: {reason}]"
        return [
            {
                "start": seg.start,
                "end": seg.end,
                "text_en": seg.text.strip(),
                "text_zh": error_msg,
            }
            for seg in batch
        ]

    def _reconstruct_srt(self, entries: List[Dict[str, Any]]) -> str:
        """
        Convert processed entries to SRT format.

        We deliberately emit a *single* text block per cue. Callers control
        what goes into ``text_en`` / ``text_zh``:

        - For enhanced original‑language subtitles, ``text_en`` contains the
          corrected source text and ``text_zh`` is ignored.
        - For translation‑only subtitles, the caller stores the target‑language
          text in ``text_en`` and leaves ``text_zh`` empty.

        Bilingual views (EN+ZH / ZH+EN) are composed at the UI layer by
        merging separate EN / ZH tracks, which keeps data structures simple
        and avoids duplicate text.
        """
        lines = []
        for i, entry in enumerate(entries, start=1):
            start_str = self._format_timestamp(entry["start"])
            end_str = self._format_timestamp(entry["end"])

            text_en = (entry.get("text_en") or "").strip()
            text_zh = (entry.get("text_zh") or "").strip()

            # Use a single text block per cue. Prefer text_en; fall back to
            # text_zh so that callers can stash the final text there if needed.
            text_block = text_en or text_zh

            lines.append(str(i))
            lines.append(f"{start_str} --> {end_str}")
            lines.append(text_block)
            lines.append("")
            
        return "\n".join(lines)

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        raw_clean = (raw or "").strip()
        if raw_clean.startswith("```"):
            import re
            match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw_clean, re.DOTALL | re.IGNORECASE)
            if match:
                raw_clean = match.group(1).strip()
        try:
            return json_repair.loads(raw_clean)
        except Exception:
            return {}

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total_ms = max(0, int(round(seconds * 1000)))
        hours = total_ms // 3_600_000
        minutes = (total_ms % 3_600_000) // 60_000
        secs = (total_ms % 60_000) // 1000
        millis = total_ms % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
