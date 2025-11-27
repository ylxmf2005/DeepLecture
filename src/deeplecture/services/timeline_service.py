from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from deeplecture.llm.llm_factory import LLM, LLMFactory
from deeplecture.app_context import get_app_context
from deeplecture.prompts.explain_prompt import _get_explanation_language
from deeplecture.services.content_service import ContentService
from deeplecture.storage.fs_timeline_storage import TimelineStorage, get_default_timeline_storage
from deeplecture.transcription.interactive import TimelineGenerator
from deeplecture.workers import TaskManager

UTC = getattr(datetime, "UTC", timezone.utc)


class TimelineService:
    """
    Application service responsible for generating and caching subtitle timelines.
    """

    def __init__(
        self,
        storage: Optional[TimelineStorage] = None,
        task_manager: Optional[TaskManager] = None,
        content_service: Optional[ContentService] = None,
        llm_factory: Optional[LLMFactory] = None,
        timeline_generator_factory: Optional[Callable[[LLM], TimelineGenerator]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._task_manager: Optional[TaskManager] = task_manager
        self._content_service = content_service or ContentService()
        self._storage: TimelineStorage = (
            storage or get_default_timeline_storage(self._content_service)
        )
        if llm_factory is None:
            ctx = get_app_context()
            ctx.ensure_initialized()
            self._llm_factory = ctx.llm_factory
        else:
            self._llm_factory = llm_factory
        self._timeline_generator_factory = (
            timeline_generator_factory or (lambda llm: TimelineGenerator(llm))
        )

    def resolve_subtitle_path(
        self,
        video_id: str,
    ) -> str:
        """
        Resolve the subtitle path for timeline generation.

        Uses unified content metadata only. Legacy flat layouts and any
        client-provided paths are no longer supported.
        """
        # Prefer enhanced subtitles when available for better timeline quality.
        path = self._content_service.get_enhanced_subtitle_path(video_id)
        if path and os.path.exists(path):
            return path

        path = self._content_service.get_subtitle_path(video_id)

        if not path:
            raise FileNotFoundError("Subtitle file could not be resolved for timeline")

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Subtitle file not found for timeline: {path}",
            )

        return path

    def get_timeline_path(self, video_id: str, language: Optional[str] = None) -> str:
        """Public accessor for the timeline JSON output path."""
        resolved_language = self._resolve_language(language)
        return self._storage.build_timeline_path(video_id, resolved_language)

    def has_cached_timeline(
        self,
        video_id: str,
        language: Optional[str] = None,
        learner_profile: Optional[str] = None,
    ) -> bool:
        """Check whether a ready timeline exists that matches the learner profile."""
        _, cache_ready, _ = self._load_cache_state(video_id, language, learner_profile)
        return cache_ready

    def get_or_generate_timeline(
        self,
        *,
        video_id: str,
        language: Optional[str],
        learner_profile: Optional[str],
        force: bool,
    ) -> Dict[str, Any]:
        """
        Public entry point for routes: resolve subtitle path, check cache, and
        enqueue generation when needed.
        """
        if not video_id:
            raise ValueError("Missing video_id")

        resolved_language = self._resolve_language(language)
        learner_profile_value = (learner_profile or "").strip()

        subtitle_path_resolved = self.resolve_subtitle_path(video_id)
        timeline_path = self.get_timeline_path(video_id, resolved_language)

        cached_payload, cache_ready, cached_status = self._load_cache_state(
            video_id,
            resolved_language,
            learner_profile_value,
        )

        if cache_ready and not force:
            timeline_list = cached_payload.get("timeline", []) if cached_payload else []
            return {
                "video_id": cached_payload.get("video_id", video_id)
                if cached_payload
                else video_id,
                "language": cached_payload.get("language", resolved_language)
                if cached_payload
                else resolved_language,
                "generated_at": cached_payload.get("generated_at") if cached_payload else None,
                "timeline": timeline_list,
                "count": len(timeline_list),
                "cached": True,
                "timeline_path": timeline_path,
                "status": "ready",
            }

        if cached_status == "processing" and not force:
            return {
                "video_id": cached_payload.get("video_id", video_id)
                if cached_payload
                else video_id,
                "language": cached_payload.get("language", resolved_language)
                if cached_payload
                else resolved_language,
                "generated_at": cached_payload.get("generated_at") if cached_payload else None,
                "timeline": cached_payload.get("timeline", []) if cached_payload else [],
                "count": len(cached_payload.get("timeline", [])) if cached_payload else 0,
                "cached": False,
                "timeline_path": timeline_path,
                "status": "processing",
                "message": "Timeline generation already in progress",
            }

        job_id: Optional[str] = None
        placeholder_generated_at = (
            datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        )

        task_mgr = self._task_manager

        # Persist a processing placeholder to give clients immediate feedback.
        try:
            self._storage.save(
                {
                    "timeline": [],
                    "status": "processing",
                    "error": None,
                },
                video_id=video_id,
                language=resolved_language,
                learner_profile=learner_profile_value,
            )
            self._update_timeline_metadata(
                video_id=video_id,
                status="processing",
                job_id=None,
            )
        except Exception as exc:
            self._logger.warning(
                "Failed to write placeholder timeline file %s: %s",
                timeline_path,
                exc,
            )

        if task_mgr is None:
            self._logger.warning(
                "TaskManager not configured; timeline generation will not be enqueued",
            )
        else:
            job_id = task_mgr.submit_task(
                video_id,
                "timeline_generation",
                metadata={
                    "video_id": video_id,
                    "subtitle_path": subtitle_path_resolved,
                    "language": resolved_language,
                    "learner_profile": learner_profile_value,
                    "timeline_path": timeline_path,
                },
            )
            # Refresh metadata with the queued job id for visibility.
            self._update_timeline_metadata(
                video_id=video_id,
                status="processing",
                job_id=job_id,
            )

        response: Dict[str, Any] = {
            "video_id": video_id,
            "language": resolved_language,
            "generated_at": cached_payload.get("generated_at", placeholder_generated_at)
            if cached_payload
            else placeholder_generated_at,
            "timeline": cached_payload.get("timeline", []) if cache_ready else [],
            "count": len(cached_payload.get("timeline", [])) if cache_ready else 0,
            "cached": cache_ready,
            "timeline_path": timeline_path,
            "status": "processing",
        }

        if job_id:
            response["job_id"] = job_id

        return response

    def generate_timeline(
        self,
        *,
        video_id: str,
        language: Optional[str],
        learner_profile: Optional[str],
        force: bool,
    ) -> Dict[str, Any]:
        """
        Core logic extracted from the Flask route. Returns the JSON-serializable
        response payload while relying on TimelineStorage for persistence.
        """
        return self.get_or_generate_timeline(
            video_id=video_id,
            language=language,
            learner_profile=learner_profile,
            force=force,
        )

    def run_timeline_job(
        self,
        *,
        video_id: str,
        language: str,
        learner_profile: Optional[str] = None,
        subtitle_path: Optional[str] = None,
    ) -> str:
        """Public synchronous timeline generation used by worker tasks."""
        resolved_language = self._resolve_language(language)
        resolved_subtitle_path = subtitle_path or self.resolve_subtitle_path(video_id)
        self._run_timeline_job(
            video_id=video_id,
            subtitle_path=resolved_subtitle_path,
            resolved_language=resolved_language,
            learner_profile=learner_profile,
        )
        return self.get_timeline_path(video_id, resolved_language)

    def _run_timeline_job(
        self,
        *,
        video_id: str,
        subtitle_path: str,
        resolved_language: str,
        learner_profile: Optional[str],
    ) -> None:
        try:
            generator = self._create_timeline_generator()

            entries = generator.generate_from_srt(
                subtitle_path,
                language=resolved_language,
                learner_profile=learner_profile,
            )

            path = self._storage.save(
                {
                    "timeline": entries,
                    "status": "ready",
                    "error": None,
                },
                video_id=video_id,
                language=resolved_language,
                learner_profile=learner_profile,
            )
            self._update_timeline_metadata(
                video_id=video_id,
                status="ready",
                path=path,
                job_id=None,
            )
            self._logger.info(
                "Subtitle timeline generated for video_id=%s language=%s",
                video_id,
                resolved_language,
            )
        except Exception as exc:
            self._logger.error(
                "Background subtitle timeline generation failed for video_id=%s: %s",
                video_id,
                exc,
                exc_info=True,
            )
            try:
                self._storage.save(
                    {
                        "timeline": [],
                        "status": "error",
                        "error": str(exc),
                    },
                    video_id=video_id,
                    language=resolved_language,
                    learner_profile=learner_profile,
                )
                self._update_timeline_metadata(
                    video_id=video_id,
                    status="error",
                    job_id=None,
                )
            except Exception as exc2:
                self._logger.error(
                    "Failed to persist error state for subtitle timeline of %s: %s",
                    video_id,
                    exc2,
                )
            raise

    def _create_timeline_generator(self) -> TimelineGenerator:
        """Create a timeline generator with the configured LLM."""
        if hasattr(self._llm_factory, "get_llm_for_task"):
            llm = self._llm_factory.get_llm_for_task("subtitle_timeline")
        else:
            llm = self._llm_factory.get_llm()
        return self._timeline_generator_factory(llm)

    def _require_task_manager(self) -> TaskManager:
        if self._task_manager is None:
            raise RuntimeError("TaskManager is required for background timeline jobs")
        return self._task_manager

    def _resolve_language(self, language: Optional[str]) -> str:
        if language:
            return str(language)
        try:
            return _get_explanation_language()
        except Exception:
            return "zh"

    def _load_cache_state(
        self,
        video_id: str,
        language: Optional[str],
        learner_profile: Optional[str],
    ) -> Tuple[Optional[Dict[str, Any]], bool, Optional[str]]:
        payload = self._storage.load(video_id, self._resolve_language(language))
        if not payload:
            return None, False, None

        cached_profile = (payload.get("learner_profile") or "").strip()
        current_profile = (learner_profile or "").strip()
        status = str(payload.get("status") or "ready").lower()
        cache_ready = cached_profile == current_profile and status == "ready"
        return payload, cache_ready, status

    def _update_timeline_metadata(
        self,
        *,
        video_id: str,
        status: str,
        path: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> None:
        try:
            if status == "ready" and path:
                self._content_service.mark_timeline_generated(video_id, path)
            else:
                self._content_service.update_feature_status(
                    content_id=video_id,
                    feature="timeline",
                    status=status,
                    job_id=job_id,
                )
        except FileNotFoundError:
            # Metadata may not exist yet; avoid raising from best-effort update.
            pass
