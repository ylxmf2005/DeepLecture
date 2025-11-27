from __future__ import annotations

import logging
import os
import re
from typing import List, Optional, Tuple, TYPE_CHECKING

from deeplecture.app_context import get_app_context
from deeplecture.config.config import load_config
from deeplecture.dto.note import GeneratedNoteResult, NoteDTO, NoteGenerationJobResult, NotePart
from deeplecture.infra.parallel_pool import ResourceWorkerPool
from deeplecture.prompts.explain_prompt import _get_explanation_language
from deeplecture.prompts.note_prompt import build_note_outline_prompts, build_note_part_prompts
from deeplecture.services.content_service import ContentService, get_default_content_service
from deeplecture.storage.fs_note_storage import NoteStorage, get_default_note_storage
from deeplecture.transcription.interactive import parse_srt_to_segments
from deeplecture.workers import TaskManager

try:  # pragma: no cover - optional helper, falls back to stdlib json
    import json_repair  # type: ignore[import]
except Exception:  # pragma: no cover
    import json as json_repair  # type: ignore[no-redef]

try:  # pragma: no cover - imported lazily in normal runs
    import pypdfium2 as pdfium  # type: ignore[import]
except Exception:  # pragma: no cover
    pdfium = None

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from deeplecture.llm.llm_factory import LLMFactory


logger = logging.getLogger(__name__)


class NoteService:
    def __init__(
        self,
        storage: Optional[NoteStorage] = None,
        content_service: Optional[ContentService] = None,
        llm_factory: Optional["LLMFactory"] = None,
        task_manager: Optional[TaskManager] = None,
    ) -> None:
        self._content_service = content_service or get_default_content_service()
        self._storage: NoteStorage = storage or get_default_note_storage(self._content_service)
        # Allow tests or callers to inject their own LLM factory; fall back
        # to the global application-level factory when not provided.
        if llm_factory is None:
            ctx = get_app_context()
            ctx.ensure_initialized()
            self._llm_factory = ctx.llm_factory
        else:
            self._llm_factory = llm_factory
        self._task_manager: Optional[TaskManager] = task_manager

    def get_note(self, video_id: str) -> NoteDTO:
        record = self._storage.load(video_id)
        if not record:
            return NoteDTO(video_id=video_id, content="", updated_at=None)
        updated = record.updated_at.isoformat() if record.updated_at else None
        return NoteDTO(video_id=video_id, content=record.content, updated_at=updated)

    def get_note_path(self, video_id: str) -> str:
        """Public accessor for the computed note path."""
        return self._storage.build_note_path(video_id)

    def save_note(self, video_id: str, content: str) -> NoteDTO:
        record = self._storage.save(video_id, content)
        updated = record.updated_at.isoformat() if record.updated_at else None
        return NoteDTO(video_id=video_id, content=record.content, updated_at=updated)

    # ------------------------------------------------------------------
    # AI-assisted note generation
    # ------------------------------------------------------------------
    def start_generation(
        self,
        video_id: str,
        *,
        context_mode: str = "auto",
        user_instruction: str = "",
        learner_profile: str = "",
        max_parts: Optional[int] = None,
    ) -> NoteGenerationJobResult:
        """
        Start background note generation for a content item.

        This submits a task to the shared TaskManager and returns a lightweight
        descriptor. Callers should poll task status endpoints until the task
        reaches a terminal state and then fetch the final note via ``get_note``.
        """
        note_path = self.get_note_path(video_id)

        task_mgr = self._require_task_manager()
        task_id = task_mgr.submit_task(
            video_id,
            "note_generation",
            metadata={
                "content_id": video_id,
                "note_path": note_path,
                "context_mode": context_mode,
                "user_instruction": user_instruction,
                "learner_profile": learner_profile,
                "max_parts": max_parts,
            },
        )

        return NoteGenerationJobResult(
            note_path=note_path,
            status="processing",
            message="Note generation started",
            job_id=task_id,
        )

    def generate_ai_note(
        self,
        video_id: str,
        *,
        context_mode: str = "auto",
        user_instruction: str = "",
        learner_profile: str = "",
        max_parts: Optional[int] = None,
    ) -> GeneratedNoteResult:
        """
        Generate a structured Markdown note for a content item.

        Context selection is controlled by ``context_mode`` with the
        following allowed values:
            - "auto"     : use whatever is available; if both subtitle and
                           slide exist, use both.
            - "subtitle" : use subtitles/transcript only.
            - "slide"    : use slide deck only.
            - "both"     : require both subtitle and slide and use both.
        """
        metadata = self._content_service.get_content(video_id)
        if not metadata:
            raise FileNotFoundError(f"Content {video_id} not found")

        mode = str(context_mode or "auto").strip().lower()
        instruction = (user_instruction or "").strip()
        profile = (learner_profile or "").strip()

        subtitle_path = self._resolve_best_subtitle_path(video_id)

        # Fixed worker count - actual rate limiting is handled by RateLimitedLLM
        worker_count = 16

        pdf_path = self._content_service.get_pdf_path(video_id)

        has_subtitle = bool(subtitle_path)
        has_slides = bool(pdf_path)

        if metadata.type == "video" and not has_subtitle:
            raise ValueError(
                "Cannot generate notes: this video has no subtitles yet. "
                "Please generate subtitles first.",
            )

        use_subtitle, use_slides = self._select_sources(
            mode=mode,
            has_subtitle=has_subtitle,
            has_slides=has_slides,
        )

        context_parts: List[str] = []
        used_sources: List[str] = []

        if use_subtitle and subtitle_path:
            text = self._load_subtitle_context(subtitle_path)
            if text:
                context_parts.append("=== Subtitle transcript context ===\n" + text)
                used_sources.append("subtitle")

        if use_slides and pdf_path:
            text = self._load_pdf_context(pdf_path)
            if text:
                context_parts.append("=== Slide deck context ===\n" + text)
                used_sources.append("slide")

        if not context_parts:
            raise ValueError(
                "Cannot generate notes: failed to load usable context from subtitles or slides.",
            )

        context_block = "\n\n".join(context_parts)

        try:
            language = _get_explanation_language()
        except Exception:
            language = "Simplified Chinese"

        llm = self._get_llm()

        outline = self._build_outline(
            llm=llm,
            language=language,
            context_block=context_block,
            instruction=instruction,
            profile=profile,
            max_parts=max_parts,
        )

        if not outline:
            raise ValueError("LLM did not return a usable note outline.")

        pool = ResourceWorkerPool(
            name="note_part_generation",
            max_workers=min(worker_count, len(outline)),
            resource_factory=lambda: self._get_llm(),
        )

        def handle_part_error(exc: BaseException, part_id: int) -> str:
            logger.error(
                "Failed to generate note part %s: %s",
                part_id,
                exc,
                exc_info=True,
            )
            raise exc

        tasks = [
            (
                int(part.id),
                (part, language, context_block, instruction, profile),
            )
            for part in outline
        ]

        results = pool.map(tasks=tasks, handler=self._expand_part_handler, on_error=handle_part_error)

        full_note = "\n\n".join(results[int(part.id)].strip() for part in outline).strip()
        dto = self.save_note(video_id, full_note)

        return GeneratedNoteResult(
            video_id=video_id,
            content=dto.content,
            updated_at=dto.updated_at,
            outline=outline,
            used_sources=used_sources,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_llm(self):
        factory = self._llm_factory
        if factory is None:
            ctx = get_app_context()
            ctx.ensure_initialized()
            factory = ctx.llm_factory
        return factory.get_llm_for_task("note_generation")

    def _resolve_best_subtitle_path(self, video_id: str) -> Optional[str]:
        enhanced = self._content_service.get_enhanced_subtitle_path(video_id)
        if enhanced and os.path.exists(enhanced):
            return enhanced

        translated = self._content_service.get_translated_subtitle_path(video_id)
        if translated and os.path.exists(translated):
            return translated

        original = self._content_service.get_subtitle_path(video_id)
        if original and os.path.exists(original):
            return original

        return None

    @staticmethod
    def _select_sources(
        *,
        mode: str,
        has_subtitle: bool,
        has_slides: bool,
    ) -> tuple[bool, bool]:
        if not has_subtitle and not has_slides:
            raise ValueError(
                "Cannot generate notes: no transcript or slides are available for this content.",
            )

        normalized = (mode or "").strip().lower()

        if not normalized or normalized == "auto":
            if has_subtitle and has_slides:
                return True, True
            if has_subtitle:
                return True, False
            if has_slides:
                return False, True
            raise ValueError(
                "Cannot generate notes: no transcript or slides are available for this content.",
            )

        if normalized == "subtitle":
            if not has_subtitle:
                raise ValueError(
                    "Requested subtitle context, but no subtitles are available.",
                )
            return True, False

        if normalized == "slide":
            if not has_slides:
                raise ValueError(
                    "Requested slide context, but no slide deck is available.",
                )
            return False, True

        if normalized == "both":
            if not has_subtitle or not has_slides:
                raise ValueError(
                    "Requested 'both' context, but subtitles or slide deck are missing.",
                )
            return True, True

        raise ValueError(
            "Unsupported context_mode. Allowed values are 'auto', 'subtitle', 'slide', or 'both'.",
        )

    @staticmethod
    def _load_subtitle_context(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except Exception as exc:
            logger.error("Failed to read subtitle file %s: %s", path, exc)
            return ""

        segments = parse_srt_to_segments(content)
        if not segments:
            return ""

        lines: List[str] = []
        for seg in segments:
            text = seg.text.replace("\n", " ").strip()
            if not text:
                continue
            lines.append(text)

        if not lines:
            return ""

        return "\n".join(lines)

    @staticmethod
    def _load_pdf_context(path: str) -> str:
        if not pdfium:
            logger.warning("pypdfium2 is not available; cannot extract text from PDF %s", path)
            return ""

        try:
            doc = pdfium.PdfDocument(path)
        except Exception as exc:
            logger.error("Failed to open PDF %s: %s", path, exc)
            return ""

        parts: List[str] = []
        try:
            n_pages = len(doc)
            for index in range(n_pages):
                try:
                    page = doc.get_page(index)
                    textpage = page.get_textpage()
                    raw = textpage.get_text_range()
                    page_text = (raw or "").strip()
                except Exception as exc:
                    logger.warning("Failed to read text for PDF %s page %d: %s", path, index + 1, exc)
                    continue

                if not page_text:
                    continue

                block = f"--- Page {index + 1} ---\n{page_text}"
                parts.append(block)
        finally:
            try:
                doc.close()
            except Exception:
                pass

        if not parts:
            return ""

        return "\n\n".join(parts)

    def _build_outline(
        self,
        *,
        llm,
        language: str,
        context_block: str,
        instruction: str,
        profile: str,
        max_parts: Optional[int],
    ) -> List[NotePart]:
        system_prompt, user_prompt = build_note_outline_prompts(
            language=language,
            context_block=context_block,
            instruction=instruction,
            profile=profile,
            max_parts=max_parts,
        )
        raw = llm.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return self._parse_outline_json(raw)

    def _expand_part_handler(
        self,
        llm,
        part_id: int,
        payload: Tuple[NotePart, str, str, str, str],
    ) -> str:
        part, language, context_block, instruction, profile = payload
        return self._expand_part(
            llm=llm,
            language=language,
            context_block=context_block,
            instruction=instruction,
            profile=profile,
            part=part,
        )

    def _parse_outline_json(self, raw: str) -> List[NotePart]:
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
            logger.warning("Failed to parse outline JSON from LLM: %s", exc)
            return []

        raw_parts = data.get("parts")
        if not isinstance(raw_parts, list):
            return []

        parts: List[NotePart] = []
        for index, item in enumerate(raw_parts, start=1):
            if not isinstance(item, dict):
                continue

            raw_id = item.get("id", index)
            try:
                pid = int(raw_id)
            except Exception:
                pid = index

            title_raw = item.get("title") or ""
            summary_raw = item.get("summary") or ""
            focus_raw = item.get("focus_points") or []

            title = str(title_raw).strip()
            summary = str(summary_raw).strip()

            if not isinstance(focus_raw, list):
                focus_raw = []

            focus_points: List[str] = []
            for value in focus_raw:
                text = str(value or "").strip()
                if text:
                    focus_points.append(text)

            if not title and not summary and not focus_points:
                continue

            final_title = title or f"Part {pid}"
            parts.append(
                NotePart(
                    id=pid,
                    title=final_title,
                    summary=summary,
                    focus_points=focus_points,
                ),
            )

    def _require_task_manager(self) -> TaskManager:
        if self._task_manager is None:
            raise RuntimeError("TaskManager is required for background note jobs")
        return self._task_manager

        parts.sort(key=lambda part: part.id)
        return parts

    def _expand_part(
        self,
        *,
        llm,
        language: str,
        context_block: str,
        instruction: str,
        profile: str,
        part: NotePart,
    ) -> str:
        pid = int(part.id or 0)
        title = part.title or f"Part {pid}"
        summary = part.summary or ""
        focus_points = part.focus_points or []

        system_prompt, user_prompt = build_note_part_prompts(
            language=language,
            context_block=context_block,
            instruction=instruction,
            profile=profile,
            part_id=pid,
            title=title,
            summary=summary,
            focus_points=focus_points,
        )
        return llm.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4,
        )
