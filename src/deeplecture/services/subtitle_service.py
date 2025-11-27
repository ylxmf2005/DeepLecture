from __future__ import annotations

import json
import logging
import os
from typing import Callable, Optional

from deeplecture.app_context import get_app_context
from deeplecture.dto.subtitle import SubtitleEnhanceTranslateResult, SubtitleGenerationResult
from deeplecture.llm.llm_factory import LLM, LLMFactory
from deeplecture.services.content_service import ContentService, get_default_content_service
from deeplecture.storage.fs_subtitle_storage import SubtitleStorage, get_default_subtitle_storage
from deeplecture.transcription.enhance_translator import SubtitleEnhanceTranslator
from deeplecture.transcription.whisper_engine import SubtitleEngine, get_default_subtitle_engine
from deeplecture.workers import TaskManager
from deeplecture.workers.task_manager import Task

logger = logging.getLogger(__name__)


class SubtitleService:
    """Application service for subtitle generation and translation."""

    def __init__(
        self,
        storage: Optional[SubtitleStorage] = None,
        task_manager: Optional[TaskManager] = None,
        subtitle_engine: Optional[SubtitleEngine] = None,
        enhance_translator: Optional[SubtitleEnhanceTranslator] = None,
        content_service: Optional[ContentService] = None,
        llm_factory: Optional[LLMFactory] = None,
        translator_factory: Optional[Callable[[], SubtitleEnhanceTranslator]] = None,
    ) -> None:
        self._content_service = content_service or get_default_content_service()
        self._storage: SubtitleStorage = storage or get_default_subtitle_storage(
            self._content_service,
        )
        self._task_manager: Optional[TaskManager] = task_manager
        self._engine: SubtitleEngine = subtitle_engine or get_default_subtitle_engine()
        if llm_factory is None:
            ctx = get_app_context()
            ctx.ensure_initialized()
            self._llm_factory = ctx.llm_factory
        else:
            self._llm_factory = llm_factory
        self._translator_factory: Callable[[], SubtitleEnhanceTranslator] = (
            translator_factory
            or (lambda: SubtitleEnhanceTranslator(self._get_llm_for_enhancement()))
        )
        self._enhance_translator: Optional[SubtitleEnhanceTranslator] = enhance_translator

    # Original subtitle generation
    def start_generation(
        self,
        content_id: str,
        source_language: str,
        force: bool = False,
    ) -> SubtitleGenerationResult:
        subtitle_path = self._storage.build_original_path(content_id)

        if self.subtitles_exist(content_id) and not force:
            # Subtitles already exist on disk; ensure metadata and artifacts
            # are in sync and report a "ready" status to the caller.
            self._content_service.mark_subtitles_generated(content_id, subtitle_path)
            return SubtitleGenerationResult(
                subtitle_path=subtitle_path,
                status="ready",
                message="Subtitles already exist",
                job_id=None,
            )

        task = self._require_task_manager()
        task_id = task.submit_task(
            content_id,
            "subtitle_generation",
            metadata={
                "content_id": content_id,
                "subtitle_path": subtitle_path,
                "source_language": source_language,
            },
        )

        # Mark subtitle as being processed so polling / UI can reflect
        # that a background job is running.
        try:
            self._content_service.update_feature_status(
                content_id=content_id,
                feature="subtitle",
                status="processing",
                job_id=task_id,
            )
        except Exception as exc:  # pragma: no cover - best-effort logging
            logger.warning(
                "Failed to update subtitle status to processing for %s: %s",
                content_id,
                exc,
            )

        return SubtitleGenerationResult(
            subtitle_path=subtitle_path,
            status="processing",
            message="Subtitle generation started",
            job_id=task_id,
        )

    def resolve_subtitle_path(self, content_id: str) -> str:
        return self._storage.build_original_path(content_id)

    def get_enhanced_path(self, content_id: str) -> str:
        """Public accessor for enhanced subtitle path resolution."""
        return self._storage.build_enhanced_path(content_id)

    def subtitles_exist(self, content_id: str) -> bool:
        return self._storage.get_original(content_id) is not None

    def _get_llm_for_enhancement(self) -> LLM:
        """Get LLM for subtitle enhancement with backward compatibility."""
        if hasattr(self._llm_factory, "get_llm_for_task"):
            return self._llm_factory.get_llm_for_task("subtitle_enhancement")
        return self._llm_factory.get_llm()

    def generate_subtitles_sync(self, content_id: str, source_language: str) -> None:
        """Blocking subtitle generation for a content item."""

        video_path = self._content_service.get_video_path(content_id)
        if not video_path:
            raise FileNotFoundError(f"Video file for ID {content_id} not found")

        subtitle_path = self._storage.build_original_path(content_id)
        logger.info(
            "Generating subtitles for content_id=%s: %s -> %s (language=%s)",
            content_id,
            video_path,
            subtitle_path,
            source_language,
        )
        ok = self._engine.generate_subtitles(
            video_path=video_path,
            output_path=subtitle_path,
            language=source_language,
        )
        if ok:
            # mark_subtitles_generated already sets subtitle_status to ready
            self._content_service.mark_subtitles_generated(content_id, subtitle_path)
            logger.info(
                "Subtitle generation completed for content_id=%s at %s",
                content_id,
                subtitle_path,
            )
        else:
            logger.warning(
                "Subtitle generation reported failure for content_id=%s at %s",
                content_id,
                subtitle_path,
            )
            # Surface a hard failure so the TaskManager can mark the job as
            # error instead of silently pretending success.
            raise RuntimeError(
                f"Subtitle engine failed for content {content_id}; "
                f"no subtitles were generated",
            )

    # Subtitle enhancement and translation
    def start_enhance_and_translate(
        self,
        content_id: str,
        target_language: str,
        force: bool = False,
    ) -> SubtitleEnhanceTranslateResult:
        translated_path = self._storage.build_translation_path(
            content_id,
            target_language,
        )

        if self.translation_exists(content_id, target_language) and not force:
            return SubtitleEnhanceTranslateResult(
                translated_path=translated_path,
                status="ready",
                message="Translated subtitles already exist",
                job_id=None,
            )

        task = self._require_task_manager()
        task_id = task.submit_task(
            content_id,
            "subtitle_translation",
            metadata={
                "content_id": content_id,
                "target_language": target_language,
                "translated_path": translated_path,
            },
        )

        # Mark translation and enhanced as processing
        try:
            self._content_service.update_feature_status(
                content_id=content_id,
                feature="translation",
                status="processing",
                job_id=task_id,
            )
            self._content_service.update_feature_status(
                content_id=content_id,
                feature="enhanced",
                status="processing",
                job_id=task_id,
            )
        except Exception as exc:  # pragma: no cover - best-effort logging
            logger.warning(
                "Failed to update translation/enhanced status to processing for %s: %s",
                content_id,
                exc,
            )

        return SubtitleEnhanceTranslateResult(
            translated_path=translated_path,
            status="processing",
            message="Subtitle enhancement and translation started",
            job_id=task_id,
        )

    def enhance_and_translate_sync(
        self,
        content_id: str,
        target_language: str,
    ) -> None:
        """Blocking subtitle enhancement and translation."""

        original_path = self._require_original_subtitle(content_id)
        logger.info(
            "Starting subtitle enhance & translate for %s (target=%s)",
            original_path,
            target_language,
        )

        with open(original_path, "r", encoding="utf-8") as f:
            source_content = f.read()

        translator = self._get_or_create_translator()

        # Older test doubles only implement process_subtitles; in that
        # case, fall back to the simpler "translated-only" behaviour and
        # skip enhanced/background outputs.
        if not hasattr(translator, "process_to_entries"):
            result_content = translator.process_subtitles(
                source_content,
                target_language,
            )
            translated_path = self._storage.build_translation_path(
                content_id,
                target_language,
            )
            os.makedirs(os.path.dirname(translated_path), exist_ok=True)
            with open(translated_path, "w", encoding="utf-8") as f:
                f.write(result_content)

            # mark_translation_generated sets translation_status to ready
            self._content_service.mark_translation_generated(
                content_id,
                translated_path,
            )
            logger.info(
                "Subtitle enhance & translate (legacy translator) completed for %s at %s",
                original_path,
                translated_path,
            )
            return

        entries, background = translator.process_to_entries(
            source_content,
            target_language=target_language,
        )

        # Paths for enhanced, translated and background artifacts.
        enhanced_path = self._storage.build_enhanced_path(content_id)
        translated_path = self._storage.build_translation_path(
            content_id,
            target_language,
        )
        background_path = self._storage.build_background_path(content_id)

        os.makedirs(os.path.dirname(enhanced_path), exist_ok=True)
        os.makedirs(os.path.dirname(translated_path), exist_ok=True)
        os.makedirs(os.path.dirname(background_path), exist_ok=True)

        # 1) Enhanced original‑language subtitles.
        enhanced_srt = translator._reconstruct_srt(entries)
        with open(enhanced_path, "w", encoding="utf-8") as f:
            f.write(enhanced_srt)

        # 2) Translation-only subtitles for downstream consumers (e.g. TTS).
        translated_entries = []
        for item in entries:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", 0.0))
            zh = (item.get("text_zh") or "").strip()
            if not zh:
                zh = (item.get("text_en") or "").strip()
            translated_entries.append(
                {
                    "start": start,
                    "end": end,
                    # Use text_en for the final text so we can reuse the same reconstruction helper.
                    "text_en": zh,
                    "text_zh": "",
                },
            )

        translated_srt = translator._reconstruct_srt(translated_entries)
        with open(translated_path, "w", encoding="utf-8") as f:
            f.write(translated_srt)

        # 3) Persist background context JSON alongside subtitles.
        try:
            with open(background_path, "w", encoding="utf-8") as f:
                json.dump(background or {}, f, ensure_ascii=False, indent=2)
        except Exception as exc:  # pragma: no cover - best-effort persistence
            logger.warning(
                "Failed to write subtitle background JSON for %s: %s",
                content_id,
                exc,
            )
        else:
            self._content_service.register_artifact(
                content_id,
                background_path,
                kind="subtitle:background",
                media_type="application/json",
            )

        # Update unified metadata and artifact indices.
        # mark_translation_generated and mark_enhanced_generated set respective statuses to ready
        self._content_service.mark_translation_generated(
            content_id,
            translated_path,
        )
        self._content_service.mark_enhanced_generated(
            content_id,
            enhanced_path,
        )

        logger.info(
            "Subtitle enhance & translate completed for %s (enhanced=%s, translated=%s)",
            original_path,
            enhanced_path,
            translated_path,
        )

    def resolve_translation_path(
        self,
        content_id: str,
        target_language: str,
    ) -> str:
        return self._storage.build_translation_path(content_id, target_language)

    def translation_exists(
        self,
        content_id: str,
        target_language: str,
    ) -> bool:
        record = self._storage.get_translation(content_id, target_language)
        return record is not None and os.path.exists(record.path)

    def get_job(self, job_id: str) -> Optional[Task]:
        if self._task_manager is None:
            return None
        return self._task_manager.get_task(job_id)

    # Internal helpers
    def _require_original_subtitle(self, content_id: str) -> str:
        path = self._content_service.get_subtitle_path(content_id)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(
                f"Original subtitles not found for content {content_id}",
            )
        return path

    def _get_or_create_translator(self) -> SubtitleEnhanceTranslator:
        if self._enhance_translator is None:
            self._enhance_translator = self._translator_factory()
        return self._enhance_translator

    def _require_task_manager(self) -> TaskManager:
        if self._task_manager is None:
            raise RuntimeError("TaskManager is required for background subtitle jobs")
        return self._task_manager

    @staticmethod
    def convert_srt_to_vtt(srt_content: str) -> str:
        """Convert SRT content to WebVTT format."""

        import re

        # Normalize newlines
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
            cleaned_text = []
            for line in text_lines:
                line = re.sub(r"<[^>]+>", "", line)
                line = re.sub(r"\{.*?\}", "", line)
                cleaned_text.append(line)

            vtt_lines.append("\n".join(cleaned_text))
            vtt_lines.append("")

        return "\n".join(vtt_lines)
