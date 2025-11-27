"""
Sequential slide transcript generation service.

Processes slides page-by-page in sequence, maintaining full previous transcript
and accumulated summaries for context, enabling pipelined TTS/video generation.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Callable, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

import json_repair

from deeplecture.app_context import get_app_context
from deeplecture.dto.slide import TranscriptHistory, TranscriptPage, TranscriptSegment
from deeplecture.prompts.slide_lecture_prompt import build_slide_lecture_prompt

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from deeplecture.llm.llm_factory import LLMFactory


logger = logging.getLogger(__name__)


class TranscriptService:
    """
    Sequential transcript generation service.

    Processes pages one-by-one in order, maintaining full context from
    previous pages and enabling immediate pipelined processing.
    """

    def __init__(self, llm_factory: Optional["LLMFactory"] = None) -> None:
        self._llm_factory: Optional[LLMFactory] = llm_factory

    def _get_llm_factory(self) -> "LLMFactory":
        if self._llm_factory is not None:
            return self._llm_factory
        ctx = get_app_context()
        ctx.ensure_initialized()
        return ctx.llm_factory

    def stream_pages(
        self,
        *,
        deck_id: str,
        page_images: Dict[int, str],
        transcripts_dir: str,
        source_language: str,
        target_language: str,
        neighbor_images: str = "next",
        transcript_lookback_pages: int = -1,
        summary_lookback_pages: int = -1,
        callback: Optional[Callable[[TranscriptPage], None]] = None,
    ) -> List[TranscriptPage]:
        """
        Generate transcripts sequentially with streaming callback.

        Processes each page in order, maintaining context from previous pages
        and calling the callback immediately after each page completes to
        enable pipelined TTS/video generation.

        Args:
            deck_id: Slide deck identifier
            page_images: Dict mapping page_index to image_path
            transcripts_dir: Directory to write transcript JSON files
            source_language: Source language code
            target_language: Target language code
            neighbor_images: Image context mode (none/next/prev_next)
            transcript_lookback_pages: How many pages to look back for transcript (-1 for all, 0 for none)
            summary_lookback_pages: How many pages to look back for summaries (-1 for all, 0 for none)
            callback: Optional function called with each completed TranscriptPage

        Returns:
            List of all generated TranscriptPage objects in order
        """
        os.makedirs(transcripts_dir, exist_ok=True)

        # Sort pages to ensure deterministic order
        ordered_pages = sorted(page_images.items())
        total_pages = len(ordered_pages)

        # Initialize history tracker
        history = TranscriptHistory()

        # Results accumulator
        pages: List[TranscriptPage] = []

        # Get LLM instance for the task
        llm = self._get_llm_factory().get_llm_for_task("slide_lecture")

        # Process each page sequentially
        for pos, (page_index, image_path) in enumerate(ordered_pages):
            logger.info(
                "Generating transcript for deck %s page %d/%d",
                deck_id, page_index, total_pages
            )

            # Prepare image context based on mode
            images = [image_path]  # Current page always first

            if neighbor_images in ("next", "prev_next"):
                # Add next page if available
                if pos + 1 < len(ordered_pages):
                    next_image = ordered_pages[pos + 1][1]
                    images.append(next_image)

            # Note: prev_next mode would also look at previous, but since we have
            # the full transcript, we don't need the previous image

            # Get context from history with lookback limit
            # Determine actual lookback based on position and setting
            actual_lookback = transcript_lookback_pages
            if transcript_lookback_pages > 0 and pos > 0:
                # Only look back to recent pages based on setting
                if pos < transcript_lookback_pages:
                    actual_lookback = -1  # Look at all available if less than limit
            elif transcript_lookback_pages == 0:
                # No lookback for transcript
                actual_lookback = 0
            # -1 means look at all, which is the default

            prev_transcript, accumulated_summaries = history.as_prompt_blocks(
                lookback_pages=actual_lookback,
                summary_lookback_pages=summary_lookback_pages,
            )

            try:
                # Generate transcript for this page
                page = self._generate_page_transcript(
                    llm=llm,
                    deck_id=deck_id,
                    page_index=page_index,
                    total_pages=total_pages,
                    images=images,
                    source_language=source_language,
                    target_language=target_language,
                    prev_transcript=prev_transcript,
                    accumulated_summaries=accumulated_summaries,
                    neighbor_images=neighbor_images,
                )
            except Exception as e:
                logger.error(
                    "Failed to generate transcript for deck %s page %d: %s",
                    deck_id, page_index, e, exc_info=True
                )
                # Create fallback page to maintain timeline continuity
                page = self._create_fallback_page(
                    deck_id, page_index, source_language, target_language
                )

            # Persist to JSON
            json_path = os.path.join(transcripts_dir, f"page_{page_index:03d}.json")
            self._write_transcript_page_json(page, json_path)

            # Update history with this page's content
            history = history.after_page(page)

            # Add to results
            pages.append(page)

            # Trigger callback for pipelined processing
            if callback:
                try:
                    callback(page)
                except Exception as e:
                    logger.error(
                        "Callback failed for deck %s page %d: %s",
                        deck_id, page_index, e
                    )
                    # Continue processing even if callback fails

        logger.info(
            "Completed transcript generation for deck %s (%d pages)",
            deck_id, len(pages)
        )

        return pages

    def _generate_page_transcript(
        self,
        *,
        llm,
        deck_id: str,
        page_index: int,
        total_pages: int,
        images: List[str],
        source_language: str,
        target_language: str,
        prev_transcript: str,
        accumulated_summaries: str,
        neighbor_images: str,
    ) -> TranscriptPage:
        """Call vision LLM to generate transcript for one page."""

        # Build prompt with context
        user_prompt, system_prompt = build_slide_lecture_prompt(
            deck_id=deck_id,
            page_index=page_index,
            total_pages=total_pages,
            source_language=source_language,
            target_language=target_language,
            previous_transcript=prev_transcript if prev_transcript else None,
            accumulated_summaries=accumulated_summaries if accumulated_summaries else None,
            neighbor_images=neighbor_images,
        )

        # Call LLM
        raw = llm.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            image_path=images if len(images) > 1 else images[0],
        )

        # Parse response
        return self._parse_transcript_response(
            raw, deck_id, page_index, source_language, target_language
        )

    def _parse_transcript_response(
        self,
        raw: str,
        deck_id: str,
        page_index: int,
        source_language: str,
        target_language: str,
    ) -> TranscriptPage:
        """Parse LLM JSON response into TranscriptPage."""

        try:
            data = json.loads(raw)
        except Exception:
            try:
                data = json_repair.loads(raw)
            except Exception as exc:
                logger.error(
                    "Failed to parse slide lecture JSON for deck %s page %s: %s",
                    deck_id, page_index, exc
                )
                raise

        if not isinstance(data, dict):
            raise ValueError("Slide lecture response must be a JSON object")

        segs = data.get("segments")
        if not isinstance(segs, list) or not segs:
            raise ValueError("Slide lecture JSON must contain a non-empty 'segments' array")

        segments: List[TranscriptSegment] = []
        for idx, raw_seg in enumerate(segs, start=1):
            if not isinstance(raw_seg, dict):
                continue

            seg_id = raw_seg.get("id")
            try:
                seg_id_int = int(seg_id) if seg_id is not None else idx
            except (TypeError, ValueError):
                seg_id_int = idx

            source_text = str(raw_seg.get("source", "")).strip()
            target_text = str(raw_seg.get("target", "")).strip()

            if not source_text:
                continue

            segments.append(
                TranscriptSegment(
                    id=seg_id_int,
                    source=source_text,
                    target=target_text,
                )
            )

        if not segments:
            raise ValueError("No usable segments found in slide lecture JSON")

        one_sentence_summary = str(data.get("one_sentence_summary", "")).strip()

        return TranscriptPage(
            deck_id=deck_id,
            page_index=page_index,
            source_language=data.get("source_language", source_language),
            target_language=data.get("target_language", target_language),
            segments=segments,
            one_sentence_summary=one_sentence_summary,
        )

    def _create_fallback_page(
        self,
        deck_id: str,
        page_index: int,
        source_language: str,
        target_language: str,
    ) -> TranscriptPage:
        """Create a minimal fallback page when generation fails."""
        return TranscriptPage(
            deck_id=deck_id,
            page_index=page_index,
            source_language=source_language,
            target_language=target_language,
            segments=[
                TranscriptSegment(
                    id=1,
                    source=f"[Content generation failed for page {page_index}]",
                    target=f"[Content generation failed for page {page_index}]",
                ),
            ],
            one_sentence_summary=f"Page {page_index} generation failed",
        )

    @staticmethod
    def _write_transcript_page_json(page: TranscriptPage, json_path: str) -> None:
        """Persist transcript page to JSON file."""
        payload = {
            "deck_id": page.deck_id,
            "page_index": page.page_index,
            "source_language": page.source_language,
            "target_language": page.target_language,
            "one_sentence_summary": page.one_sentence_summary,
            "segments": [
                {
                    "id": seg.id,
                    "source": seg.source,
                    "target": seg.target,
                }
                for seg in page.segments
            ],
        }

        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("Failed to persist transcript page JSON %s: %s", json_path, exc)
