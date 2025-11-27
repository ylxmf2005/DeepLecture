"""
Generate time‑aligned interactive timelines from SRT subtitles.

This module is responsible for turning raw subtitle text into a small
set of LLM‑generated timeline entries that the frontend can display in
the timeline panel below the player.

High‑level pipeline (two stages):
- Stage 1: send the *full* transcript (all subtitle segments) to the
  LLM and ask it to divide the lecture into a small number of coherent
  "knowledge units" (each with a title and a [start, end] time range).
- Stage 2: for each knowledge unit, send only the corresponding
  subtitle slice to the LLM and ask it to generate a focused
  explanation panel for that unit.

The result is a set of time‑aligned "segment_explanation" timeline
entries that represent real concepts instead of arbitrary time chunks.

The server entrypoint for this feature lives in server.py
(`/api/generate-timeline`).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

try:
    import json_repair
except ImportError:  # pragma: no cover - fallback to std json
    import json

    class _JsonRepair:
        @staticmethod
        def load(file_obj):
            return json.load(file_obj)

    json_repair = _JsonRepair()
from deeplecture.config.config import load_config
from deeplecture.llm.llm_factory import LLM
from deeplecture.prompts.subtitle_segment_explain_prompt import (
    build_segment_explanation_prompt,
)
from deeplecture.prompts.subtitle_lecture_segmentation_prompt import (
    build_lecture_segmentation_prompt,
)
from deeplecture.infra.parallel_pool import ResourceWorkerPool

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SubtitleSegment:
    """
    Single subtitle entry with timing in seconds.

    This is intentionally simple and self‑contained instead of reusing
    the SRT parsing logic inside the TTS module, so that LLM‑related
    logic stays decoupled from optional TTS dependencies.
    """

    id: int
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclasses.dataclass
class KnowledgeUnit:
    """
    A higher‑level conceptual slice of the lecture spanning a continuous
    time range and one main idea.
    """

    id: int
    start: float
    end: float
    title: str


def parse_srt_to_segments(content: str) -> List[SubtitleSegment]:
    """
    Parse a basic SRT file content into structured segments.

    This helper is shared by multiple subtitle‑driven LLM features so
    that we keep parsing behaviour consistent across modules.
    """
    blocks = re.split(r"\n\s*\n", content.strip())
    segments: List[SubtitleSegment] = []

    time_pattern = re.compile(
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    )

    for block in blocks:
        lines = [
            line.strip("\ufeff")
            for line in block.strip().split("\n")
            if line.strip()
        ]
        if len(lines) < 2:
            continue

        try:
            seg_id = int(lines[0].strip())
        except ValueError:
            # Skip malformed entries; they are rare in auto‑generated SRTs.
            continue

        time_line = lines[1].strip()
        m = time_pattern.match(time_line)
        if not m:
            logger.debug(
                "Skipping subtitle block with invalid timestamp: %s",
                time_line,
            )
            continue

        start = (
            int(m.group(1)) * 3600
            + int(m.group(2)) * 60
            + int(m.group(3))
            + int(m.group(4)) / 1000.0
        )
        end = (
            int(m.group(5)) * 3600
            + int(m.group(6)) * 60
            + int(m.group(7))
            + int(m.group(8)) / 1000.0
        )

        text = "\n".join(lines[2:]).strip()
        if not text:
            continue

        segments.append(
            SubtitleSegment(
                id=seg_id,
                start=start,
                end=end,
                text=text,
            )
        )

    segments.sort(key=lambda s: (s.start, s.id))
    return segments


@dataclasses.dataclass
class TimelineEntry:
    """
    A single timeline entry that the frontend can show at a specific
    playback time.
    """

    id: int
    kind: str
    start: float
    end: float
    title: str
    markdown: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "start": self.start,
            "end": self.end,
            "title": self.title,
            "markdown": self.markdown,
        }


class TimelineGenerator:
    """
    Generate interactive explanations from subtitle files using an LLM.

    The generator:
    1. Parses an SRT file into segments.
    2. Uses the full transcript to let the LLM divide the lecture into
       coherent "knowledge units" (each with a [start, end] window).
    3. For each knowledge unit, asks the LLM to generate an explanation
       panel in Markdown, with a trigger time inside that window.
    4. Returns a list of `TimelineEntry` objects, one per unit
       that the LLM decides is worth explaining.
    """

    def __init__(self, llm: LLM, config: Optional[Dict[str, Any]] = None) -> None:
        self.llm = llm

        if config is None:
            config = load_config()

        subtitle_cfg = (config or {}).get("subtitle") or {}
        timeline_cfg = subtitle_cfg.get("timeline") or {}
        # Language used for the produced explanation text (e.g. "zh").
        self.output_language: str = str(
            timeline_cfg.get("output_language", "zh")
        )
        # A slightly low temperature to keep explanations focused.
        self.temperature: float = float(
            timeline_cfg.get("temperature", 0.3)
        )

        # Fixed worker count - actual rate limiting is handled by RateLimitedLLM
        self._max_workers: int = 16

        self._unit_pool = ResourceWorkerPool(
            name="timeline_units",
            max_workers=self._max_workers,
            resource_factory=lambda: self.llm,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_from_srt(
        self,
        srt_path: str,
        *,
        language: Optional[str] = None,
        learner_profile: Optional[str] = None,
    ) -> List[TimelineEntry]:
        """
        Generate a timeline for the given SRT file.

        Args:
            srt_path: Path to subtitle file in SRT format.
            language: Optional override for explanation language
                (e.g. "zh"). Falls back to config default if None.
        """
        if not os.path.exists(srt_path):
            raise FileNotFoundError(f"SRT file not found: {srt_path}")

        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()

        segments = self._parse_srt(content)
        if not segments:
            logger.warning("No subtitle segments found in %s", srt_path)
            return []

        explain_language = language or self.output_language

        # Stage 1: ask the LLM (once) to segment the *full* transcript
        # into coherent knowledge units based on content, not just time.
        knowledge_units = self._segment_knowledge_units(
            segments,
            explain_language=explain_language,
            learner_profile=learner_profile,
        )

        if not knowledge_units:
            logger.info(
                "Knowledge segmentation produced no units; returning an "
                "empty timeline."
            )
            return []

        logger.info(
            "Generating subtitle timeline using %s knowledge units "
            "from %s subtitle segments (max_workers=%s)",
            len(knowledge_units),
            len(segments),
            self._max_workers,
        )
        timeline_entries: List[TimelineEntry] = self._generate_from_knowledge_units(
            segments,
            knowledge_units,
            explain_language=explain_language,
            learner_profile=learner_profile,
        )

        # Renumber IDs sequentially in presentation order so the frontend has
        # simple, human‑friendly identifiers.
        timeline_entries.sort(key=lambda x: (x.start, x.id))
        for new_id, item in enumerate(timeline_entries, start=1):
            item.id = new_id

        return timeline_entries

    # ------------------------------------------------------------------
    # SRT parsing
    # ------------------------------------------------------------------
    def _parse_srt(self, content: str) -> List[SubtitleSegment]:
        """
        Parse a basic SRT file into structured segments.

        We intentionally implement this here instead of depending on
        the TTS module. The logic is similar to the one used for the
        voiceover generator but keeps this module independent.
        """
        return parse_srt_to_segments(content)

    # ------------------------------------------------------------------
    # Knowledge‑based segmentation and generation
    # ------------------------------------------------------------------
    def _segment_knowledge_units(
        self,
        segments: List[SubtitleSegment],
        *,
        explain_language: str,
        learner_profile: Optional[str],
    ) -> List[KnowledgeUnit]:
        """
        Use a single LLM call to divide the full transcript into
        contiguous knowledge units.
        """
        if not segments:
            return []

        user_prompt, system_prompt = build_lecture_segmentation_prompt(
            segments,
            language=explain_language,
            learner_profile=learner_profile,
        )

        raw = self.llm.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=self.temperature,
        )

        raw_clean = (raw or "").strip()
        if raw_clean.startswith("```"):
            # Match ```json\n{...}\n``` or ```\n{...}\n```
            fence_match = re.match(
                r"^```(?:json)?\s*(.*?)\s*```$",
                raw_clean,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if fence_match:
                raw_clean = fence_match.group(1).strip()

        try:
            data = json_repair.loads(raw_clean)
        except Exception as exc:
            logger.warning("Failed to parse knowledge segmentation JSON: %s", exc)
            return []

        units_raw = data.get("knowledge_units") or []
        if not isinstance(units_raw, list):
            logger.warning("knowledge_units is not a list in segmentation output")
            return []

        seg_start = segments[0].start
        seg_end = segments[-1].end

        units: List[KnowledgeUnit] = []
        for idx, item in enumerate(units_raw, start=1):
            try:
                start_raw = item.get("start")
                end_raw = item.get("end")
                if start_raw is None or end_raw is None:
                    continue

                start = float(start_raw)
                end = float(end_raw)
            except (TypeError, ValueError):
                continue

            if end <= start:
                continue

            # Clamp to global subtitle range for safety.
            if end < seg_start or start > seg_end:
                continue

            start = max(seg_start, start)
            end = min(seg_end, end)

            title = str(item.get("title") or "").strip()
            if not title:
                title = f"Concept {idx}"

            units.append(
                KnowledgeUnit(
                    id=idx,
                    start=start,
                    end=end,
                    title=title,
                )
            )

        # Sort and de‑overlap in time order.
        units.sort(key=lambda u: (u.start, u.end, u.id))

        merged: List[KnowledgeUnit] = []
        for unit in units:
            if not merged:
                merged.append(unit)
                continue

            last = merged[-1]
            if unit.start >= last.end:
                merged.append(unit)
            else:
                # Overlapping units: keep the one that starts earlier and
                # extends further. This keeps the timeline clean even if
                # the LLM produced slightly overlapping ranges.
                if unit.end > last.end:
                    merged[-1] = KnowledgeUnit(
                        id=last.id,
                        start=last.start,
                        end=unit.end,
                        title=last.title,
                    )

        return merged

    def _generate_from_knowledge_units(
        self,
        segments: List[SubtitleSegment],
        knowledge_units: List[KnowledgeUnit],
        *,
        explain_language: str,
        learner_profile: Optional[str],
    ) -> List[TimelineEntry]:
        """
        Generate timeline entries by running one LLM call per knowledge unit.
        """
        if not knowledge_units:
            return []

        # Helper to map a unit back to the subtitle segments that fall
        # inside its [start, end] window.
        def segments_for_unit(unit: KnowledgeUnit) -> List[SubtitleSegment]:
            return [
                seg
                for seg in segments
                if seg.end > unit.start and seg.start < unit.end
            ]

        timeline_entries: List[TimelineEntry] = []

        def process_unit(unit_index: int, unit: KnowledgeUnit) -> Optional[TimelineEntry]:
            unit_segments = segments_for_unit(unit)
            if not unit_segments:
                return None

            unit_start = unit_segments[0].start
            unit_end = unit_segments[-1].end

            user_prompt, system_prompt = build_segment_explanation_prompt(
                unit_segments,
                language=explain_language,
                chunk_start=unit_start,
                chunk_end=unit_end,
                learner_profile=learner_profile,
            )

            try:
                raw = self.llm.generate_response(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=self.temperature,
                )
            except Exception as exc:
                logger.error(
                    "LLM error while generating timeline entry for knowledge unit "
                    "[%.2f, %.2f] (index=%s): %s",
                    unit_start,
                    unit_end,
                    unit_index,
                    exc,
                )
                return None

            entry = self._parse_llm_output(
                raw,
                entry_id=unit_index + 1,
                chunk_start=unit_start,
                chunk_end=unit_end,
            )
            if entry is not None and not entry.title.strip():
                entry.title = unit.title
            return entry

        max_workers = min(self._max_workers, len(knowledge_units))
        if max_workers <= 1:
            for idx, unit in enumerate(knowledge_units):
                entry = process_unit(idx, unit)
                if entry is not None:
                    timeline_entries.append(entry)
            return timeline_entries

        logger.info(
            "Processing knowledge units in parallel with max_workers=%s",
            max_workers,
        )

        def handler(_llm, idx: int, unit: KnowledgeUnit) -> Optional[TimelineEntry]:
            return process_unit(idx, unit)

        def handle_error(exc: BaseException, idx: int) -> Optional[TimelineEntry]:
            logger.error(
                "Unexpected error while processing knowledge unit index=%s: %s",
                idx,
                exc,
            )
            return None

        results = self._unit_pool.map(
            list(enumerate(knowledge_units)),
            handler,
            on_error=handle_error,
        )

        timeline_entries = [results[idx] for idx in sorted(results.keys()) if results.get(idx) is not None]

        return timeline_entries


    # ------------------------------------------------------------------
    # LLM output parsing
    # ------------------------------------------------------------------
    def _parse_llm_output(
        self,
        raw: str,
        *,
        entry_id: int,
        chunk_start: float,
        chunk_end: float,
    ) -> Optional[TimelineEntry]:
        """
        Parse the JSON output returned by the LLM for a single chunk.

        Expected shape:
            {
              "should_explain": true | false,
              "title": "short title",
              "trigger_time": 123.45,  # seconds
              "markdown": "explanation in Markdown"
            }
        """
        # Some OpenAI‑compatible providers insist on wrapping JSON responses
        # in Markdown code fences (```json ... ```), even when instructed not
        # to. Strip those fences defensively before attempting to parse.
        raw_clean = (raw or "").strip()
        if raw_clean.startswith("```"):
            # Match ```json\n{...}\n``` or ```\n{...}\n```
            fence_match = re.match(
                r"^```(?:json)?\s*(.*?)\s*```$",
                raw_clean,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if fence_match:
                raw_clean = fence_match.group(1).strip()

        try:
            # Use json_repair to tolerate minor JSON issues from LLM output
            data = json_repair.loads(raw_clean)
        except Exception:
            logger.warning("Failed to parse LLM output as JSON: %s", raw)
            return None

        should_explain_raw = data.get("should_explain")
        # Treat missing/null should_explain as "true" so that newer
        # prompts that always generate explanations continue to work.
        if should_explain_raw is not None and not bool(should_explain_raw):
            return None

        markdown = str(data.get("markdown") or "").strip()
        if not markdown:
            logger.debug("LLM requested explanation but markdown is empty")
            return None

        title = str(data.get("title") or "").strip()
        if not title:
            title = "Explanation"

        trigger_time_raw = data.get("trigger_time")
        try:
            trigger_time = float(trigger_time_raw)
        except (TypeError, ValueError):
            trigger_time = chunk_start

        # Clamp trigger time to the chunk boundaries for safety.
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
