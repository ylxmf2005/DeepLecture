from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from deeplecture.app_context import get_app_context
from deeplecture.prompts.explain_prompt import get_explain_prompt
from deeplecture.services.content_service import ContentService
from deeplecture.services.note_service import NoteService
from deeplecture.services.slide_lecture_service import SlideLectureService
from deeplecture.services.subtitle_service import SubtitleService
from deeplecture.services.timeline_service import TimelineService
from deeplecture.transcription.interactive import parse_srt_to_segments
from deeplecture.transcription.voiceover import SubtitleVoiceoverGenerator
from deeplecture.workers.task_manager import TaskManager

logger = logging.getLogger(__name__)


@dataclass
class WorkerServices:
    """Container for services used by worker threads."""
    content: ContentService
    subtitle: SubtitleService
    timeline: TimelineService
    slide: SlideLectureService
    note: NoteService

    @classmethod
    def create(cls) -> "WorkerServices":
        """Create a new set of services for a worker thread."""
        content = ContentService()
        return cls(
            content=content,
            subtitle=SubtitleService(content_service=content),
            timeline=TimelineService(content_service=content),
            slide=SlideLectureService(content_service=content),
            note=NoteService(content_service=content),
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dispatch_task(
    task_type: str,
    metadata: Dict[str, Any],
    services: WorkerServices,
) -> Optional[str]:
    """
    Dispatch a task to the appropriate handler based on task type.

    Args:
        task_type: The type of task to execute
        metadata: Task metadata dictionary
        services: WorkerServices instance containing all required services

    Returns:
        Result path from the handler, or None if not applicable

    Raises:
        ValueError: If task_type is not supported
    """
    if task_type == "subtitle_generation":
        return _handle_subtitle_generation(services.subtitle, metadata)
    elif task_type == "subtitle_enhancement":
        return _handle_subtitle_enhancement(services.subtitle, metadata)
    elif task_type == "subtitle_translation":
        return _handle_subtitle_translation(services.subtitle, metadata)
    elif task_type == "timeline_generation":
        return _handle_timeline_generation(services.timeline, metadata)
    elif task_type == "video_generation":
        return _handle_video_generation(services.slide, metadata)
    elif task_type == "note_generation":
        return _handle_note_generation(services.note, metadata)
    elif task_type == "voiceover_generation":
        return _handle_voiceover_generation(services.content, metadata)
    elif task_type == "slide_explanation":
        return _handle_slide_explanation(services.content, metadata)
    elif task_type == "video_import_url":
        return _handle_video_import(services.content, metadata)
    elif task_type == "pdf_merge":
        return _handle_pdf_merge(services.content, metadata)
    elif task_type == "video_merge":
        return _handle_video_merge(services.content, metadata)
    else:
        raise ValueError(f"Unsupported task type: {task_type}")


def worker_loop(task_manager: TaskManager) -> None:
    """Consume TaskManager.task_queue forever and execute tasks."""

    if task_manager is None:
        raise ValueError("task_manager is required for worker loop")

    # Instantiate services once per worker thread to avoid repeated setup cost.
    services = WorkerServices.create()

    logger.info("Task worker loop started")

    while True:
        task_id = task_manager.task_queue.get()
        try:
            task = task_manager.get_task(task_id)
            if not task:
                logger.warning("Task %s disappeared before processing", task_id)
                continue

            metadata = task.metadata
            task_type = str(getattr(task, "type", ""))

            # Mark that we picked up the job.
            try:
                task_manager.update_task_progress(task_id, 1)
            except Exception:  # pragma: no cover - best effort
                logger.debug("Progress update failed for %s at start", task_id, exc_info=True)

            try:
                result_path = dispatch_task(task_type, metadata, services)

                if not result_path:
                    # Fall back to any path provided by caller metadata.
                    result_path = str(metadata.get("result_path") or "")

                task_manager.complete_task(task_id, result_path)
            except Exception as exc:  # pragma: no cover - defensive catch-all
                logger.error("Task %s (%s) failed: %s", task_id, task_type, exc, exc_info=True)
                task_manager.fail_task(task_id, str(exc))
            finally:
                task_manager.task_queue.task_done()
        except Exception:  # pragma: no cover - keep worker alive
            logger.exception("Worker loop crashed handling task %s", task_id)


def start_worker(task_manager: TaskManager) -> threading.Thread:
    """Start a single worker loop in a daemon thread."""

    if task_manager is None:
        raise ValueError("TaskManager instance is required to start worker")

    thread = threading.Thread(target=worker_loop, args=(task_manager,), name="task-worker", daemon=True)
    thread.start()
    return thread


class WorkerPool:
    """
    Multithreaded worker pool for concurrent task processing.

    Provides N× throughput compared with the single-thread worker.
    """

    def __init__(self, task_manager: TaskManager, num_workers: int = 3):
        """
        Initialize the worker pool.

        Args:
            task_manager: Task manager instance
            num_workers: Number of worker threads (default 3)
        """
        if task_manager is None:
            raise ValueError("TaskManager instance is required")

        self.task_manager = task_manager
        self.num_workers = max(1, num_workers)
        self.threads: List[threading.Thread] = []
        self._shutdown = threading.Event()
        self._started = False

    def start(self) -> None:
        """Start all worker threads."""
        if self._started:
            logger.warning("WorkerPool already started")
            return

        logger.info("Starting WorkerPool with %d workers", self.num_workers)

        for i in range(self.num_workers):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"task-worker-{i}",
                daemon=True,
            )
            thread.start()
            self.threads.append(thread)
            logger.info("Started worker thread: %s", thread.name)

        self._started = True

    def _worker_loop(self) -> None:
        """Main loop for a single worker thread."""
        thread_name = threading.current_thread().name

        # Instantiate services per thread to avoid contention
        services = WorkerServices.create()

        logger.info("[%s] Worker loop started", thread_name)

        while not self._shutdown.is_set():
            try:
                # Use timeout to avoid indefinite blocking and allow graceful shutdown
                task_id = self.task_manager.task_queue.get(timeout=1.0)
            except Exception:
                # queue.Empty or other transient errors: keep polling
                continue

            try:
                task = self.task_manager.get_task(task_id)
                if not task:
                    logger.warning("[%s] Task %s disappeared", thread_name, task_id)
                    continue

                metadata = task.metadata
                task_type = str(getattr(task, "type", ""))

                logger.info("[%s] Processing task %s (%s)", thread_name, task_id, task_type)

                try:
                    self.task_manager.update_task_progress(task_id, 1)
                except Exception:
                    pass

                try:
                    result_path = dispatch_task(task_type, metadata, services)

                    if not result_path:
                        result_path = str(metadata.get("result_path") or "")

                    self.task_manager.complete_task(task_id, result_path)
                    logger.info("[%s] Task %s completed", thread_name, task_id)

                except Exception as exc:
                    logger.error("[%s] Task %s failed: %s", thread_name, task_id, exc, exc_info=True)
                    self.task_manager.fail_task(task_id, str(exc))

            except Exception:
                logger.exception("[%s] Unexpected error handling task %s", thread_name, task_id)
            finally:
                self.task_manager.task_queue.task_done()

        logger.info("[%s] Worker loop shutting down", thread_name)

    def shutdown(self, wait: bool = True, timeout: float = 5.0) -> None:
        """
        Shut down the worker pool.

        Args:
            wait: Whether to wait for all threads to finish
            timeout: Wait timeout in seconds
        """
        logger.info("Shutting down WorkerPool...")
        self._shutdown.set()

        if wait:
            for thread in self.threads:
                thread.join(timeout=timeout)
                if thread.is_alive():
                    logger.warning("Worker thread %s did not terminate in time", thread.name)

        logger.info("WorkerPool shutdown complete")

    @property
    def active_count(self) -> int:
        """Return the number of live worker threads."""
        return sum(1 for t in self.threads if t.is_alive())

    @property
    def is_running(self) -> bool:
        """Return whether the worker pool is running."""
        return self._started and not self._shutdown.is_set()


def start_worker_pool(task_manager: TaskManager, num_workers: int = 3) -> WorkerPool:
    """
    Start a worker pool (preferred API).

    Args:
        task_manager: Task manager instance
        num_workers: Number of worker threads

    Returns:
        WorkerPool instance
    """
    pool = WorkerPool(task_manager, num_workers)
    pool.start()
    return pool


def _require_content_id(metadata: Dict[str, Any]) -> str:
    content_id = metadata.get("content_id") or metadata.get("video_id") or metadata.get("deck_id")
    if not content_id:
        raise ValueError("Task metadata missing content_id/video_id/deck_id")
    return str(content_id)


def _handle_subtitle_generation(service: SubtitleService, metadata: Dict[str, Any]) -> str:
    content_id = _require_content_id(metadata)
    source_language = str(metadata.get("source_language") or metadata.get("language") or "en")
    service.generate_subtitles_sync(content_id, source_language)
    return service.resolve_subtitle_path(content_id)


def _handle_subtitle_enhancement(service: SubtitleService, metadata: Dict[str, Any]) -> str:
    # Enhancement currently piggybacks on the combined enhance+translate pipeline.
    content_id = _require_content_id(metadata)
    target_language = str(metadata.get("target_language") or metadata.get("language") or "zh")
    service.enhance_and_translate_sync(content_id, target_language)
    return service.get_enhanced_path(content_id)


def _handle_subtitle_translation(service: SubtitleService, metadata: Dict[str, Any]) -> str:
    content_id = _require_content_id(metadata)
    target_language = str(metadata.get("target_language") or metadata.get("language") or "zh")
    service.enhance_and_translate_sync(content_id, target_language)
    return service.resolve_translation_path(content_id, target_language)


def _handle_timeline_generation(service: TimelineService, metadata: Dict[str, Any]) -> str:
    video_id = _require_content_id(metadata)
    language = metadata.get("language")
    learner_profile = metadata.get("learner_profile")

    subtitle_path = metadata.get("subtitle_path")
    if not subtitle_path:
        subtitle_path = service.resolve_subtitle_path(video_id)

    timeline_path = metadata.get("timeline_path") or service.get_timeline_path(
        video_id,
        language,
    )

    # Directly run the synchronous timeline job to avoid nesting background runners.
    service.run_timeline_job(
        video_id=video_id,
        subtitle_path=str(subtitle_path),
        language=str(language or ""),
        learner_profile=learner_profile,
    )

    return timeline_path


def _handle_video_generation(service: SlideLectureService, metadata: Dict[str, Any]) -> str:
    deck_id = _require_content_id(metadata)
    tts_language = metadata.get("tts_language")
    page_break = metadata.get("page_break_silence_seconds")

    cfg = service._get_effective_lecture_config(  # noqa: SLF001 - reuse config builder
        tts_language=tts_language,
        page_break_silence_seconds=page_break,
    )
    service.generate_lecture_sync(deck_id, cfg)
    return service.resolve_lecture_video_path(deck_id)


def _handle_note_generation(service: NoteService, metadata: Dict[str, Any]) -> str:
    video_id = _require_content_id(metadata)
    context_mode = metadata.get("context_mode", "auto")
    instruction = metadata.get("user_instruction", "")
    learner_profile = metadata.get("learner_profile", "")
    max_parts = metadata.get("max_parts")

    service.generate_ai_note(
        video_id,
        context_mode=context_mode,
        user_instruction=instruction,
        learner_profile=learner_profile,
        max_parts=max_parts,
    )
    return service.get_note_path(video_id)


def _handle_voiceover_generation(content_service: ContentService, metadata: Dict[str, Any]) -> str:
    """Generate voiceover audio and sync timeline (no video processing)."""
    video_id = _require_content_id(metadata)
    video_path = content_service.get_video_path(video_id)
    if not video_path:
        raise FileNotFoundError(f"Video file for ID {video_id} not found")

    subtitle_path = metadata.get("subtitle_path")
    if not subtitle_path:
        subtitle_path = content_service.get_translated_subtitle_path(video_id)
    if not subtitle_path:
        subtitle_path = content_service.get_subtitle_path(video_id)
    if not subtitle_path or not os.path.exists(subtitle_path):
        raise FileNotFoundError(f"Subtitle file not found for voiceover: {subtitle_path}")

    language = str(metadata.get("language") or "zh")
    meta_path = metadata.get("meta_path")
    voiceover_dir = metadata.get("voiceover_dir")
    if not voiceover_dir:
        voiceover_dir = content_service.ensure_content_dir(video_id, "voiceover")
    os.makedirs(voiceover_dir, exist_ok=True)

    audio_basename = metadata.get("audio_basename")
    voiceover_id = str(metadata.get("voiceover_id") or "")
    voiceover_name = metadata.get("voiceover_name") or audio_basename or "voiceover"

    ctx = get_app_context()
    ctx.ensure_initialized()
    generator = SubtitleVoiceoverGenerator(tts_factory=ctx.tts_factory)
    try:
        result = generator.generate_voiceover(
            video_path=video_path,
            subtitle_path=str(subtitle_path),
            output_dir=voiceover_dir,
            language=language,
            audio_basename=audio_basename,
        )
    except Exception as exc:
        _update_voiceover_manifest(
            meta_path,
            content_service,
            video_id,
            voiceover_id,
            voiceover_name,
            language,
            subtitle_path,
            voiceover_audio_path=None,
            sync_timeline_path=None,
            status="error",
            error=str(exc),
        )
        raise

    _update_voiceover_manifest(
        meta_path,
        content_service,
        video_id,
        voiceover_id,
        voiceover_name,
        language,
        subtitle_path,
        voiceover_audio_path=result.audio_path,
        sync_timeline_path=result.timeline_path,
        status="done",
        error=None,
        duration=result.audio_duration,
    )

    content_service.register_artifact(
        video_id,
        result.audio_path,
        kind="voiceover:audio",
        media_type="audio/mp4",
    )
    content_service.register_artifact(
        video_id,
        result.timeline_path,
        kind="voiceover:sync_timeline",
        media_type="application/json",
    )

    return result.timeline_path


def _handle_slide_explanation(content_service: ContentService, metadata: Dict[str, Any]) -> str:
    video_id = _require_content_id(metadata)
    image_path = metadata.get("image_path")
    json_path = metadata.get("json_path")
    timestamp = metadata.get("timestamp")
    raw_instruction = metadata.get("raw_instruction") or ""
    learner_profile = metadata.get("learner_profile")
    subtitle_context = metadata.get("subtitle_context")
    window_seconds = float(metadata.get("subtitle_window_seconds") or 30.0)

    if not json_path:
        raise ValueError("slide_explanation task missing json_path")

    if subtitle_context is None:
        subtitle_path = content_service.get_enhanced_subtitle_path(video_id)
        if not subtitle_path:
            subtitle_path = content_service.get_subtitle_path(video_id)
        subtitle_context = _build_subtitle_context(subtitle_path, timestamp, window_seconds)

    base_payload = _load_json_file(json_path) or {}
    base_payload.setdefault("id", os.path.splitext(os.path.basename(json_path))[0])
    base_payload.setdefault("video_id", video_id)
    base_payload.setdefault("image_path", image_path)
    base_payload.setdefault("timestamp", timestamp)

    ctx = get_app_context()
    ctx.ensure_initialized()
    llm = ctx.llm_factory.get_llm()
    user_prompt, system_prompt = get_explain_prompt(
        raw_instruction,
        learner_profile=learner_profile,
        subtitle_context=subtitle_context or None,
        subtitle_window_seconds=window_seconds,
    )

    try:
        explanation = llm.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            image_path=image_path,
        )
        payload = dict(base_payload)
        payload["explanation"] = explanation
        payload["updated_at"] = _utc_now_iso()
        _write_json_file(json_path, payload)
        content_service.register_artifact(
            video_id,
            json_path,
            kind="explanation:result",
            media_type="application/json",
        )
    except Exception as exc:
        error_payload = dict(base_payload)
        error_payload["error"] = str(exc)
        error_payload["updated_at"] = _utc_now_iso()
        _write_json_file(json_path, error_payload)
        content_service.register_artifact(
            video_id,
            json_path,
            kind="explanation:error",
            media_type="application/json",
            metadata={"error": str(exc)},
        )
        raise

    return json_path


def _handle_video_import(content_service: ContentService, metadata: Dict[str, Any]) -> str:
    content_id = _require_content_id(metadata)
    url = metadata.get("url")
    custom_name = metadata.get("custom_name")
    if not url:
        raise ValueError("video_import_url task missing url")

    content_service.import_video_from_url_sync(content_id, url, custom_name)
    video_path = content_service.get_video_path(content_id)
    return str(video_path or "")


def _handle_pdf_merge(content_service: ContentService, metadata: Dict[str, Any]) -> str:
    content_id = _require_content_id(metadata)
    temp_dir = metadata.get("temp_dir")
    temp_paths = [str(p) for p in metadata.get("temp_paths") or []]
    display_name = metadata.get("display_name") or metadata.get("custom_name") or "Merged PDF"
    file_count = int(metadata.get("file_count") or len(temp_paths) or 0)

    if not temp_dir or not temp_paths:
        raise ValueError("pdf_merge task missing temp_dir or temp_paths")

    content_service._merge_pdfs_job_sync(  # noqa: SLF001 - reuse sync helper
        content_id,
        temp_dir,
        temp_paths,
        display_name,
        file_count,
    )
    return str(content_service.get_pdf_path(content_id) or "")


def _handle_video_merge(content_service: ContentService, metadata: Dict[str, Any]) -> str:
    content_id = _require_content_id(metadata)
    temp_dir = metadata.get("temp_dir")
    temp_paths = [str(p) for p in metadata.get("temp_paths") or []]
    display_name = metadata.get("display_name") or metadata.get("custom_name") or "Merged Video"
    file_count = int(metadata.get("file_count") or len(temp_paths) or 0)

    if not temp_dir or not temp_paths:
        raise ValueError("video_merge task missing temp_dir or temp_paths")

    content_service._merge_videos_job_sync(  # noqa: SLF001 - reuse sync helper
        content_id,
        temp_dir,
        temp_paths,
        display_name,
        file_count,
    )
    return str(content_service.get_video_path(content_id) or "")


def _update_voiceover_manifest(
    meta_path: Optional[str],
    content_service: ContentService,
    video_id: str,
    voiceover_id: str,
    voiceover_name: str,
    language: str,
    subtitle_path: str,
    voiceover_audio_path: Optional[str],
    sync_timeline_path: Optional[str],
    *,
    status: str,
    error: Optional[str],
    duration: Optional[float] = None,
) -> None:
    if not meta_path:
        return

    try:
        current_meta = _load_json_file(meta_path) or {}
    except Exception:
        current_meta = {}

    voiceovers = current_meta.get("voiceovers") or []
    updated = False
    for item in voiceovers:
        if item.get("id") == voiceover_id:
            item["voiceover_audio_path"] = voiceover_audio_path
            item["sync_timeline_path"] = sync_timeline_path
            # Remove legacy field if present
            item.pop("dubbed_video_path", None)
            item["status"] = status
            item["error"] = error
            item["updated_at"] = _utc_now_iso()
            if duration is not None:
                item["duration"] = duration
            updated = True
            break

    if not updated:
        entry = {
            "id": voiceover_id,
            "name": voiceover_name,
            "language": language,
            "subtitle_path": subtitle_path,
            "voiceover_audio_path": voiceover_audio_path,
            "sync_timeline_path": sync_timeline_path,
            "created_at": _utc_now_iso(),
            "status": status,
            "error": error,
        }
        if duration is not None:
            entry["duration"] = duration
        voiceovers.append(entry)

    current_meta["video_id"] = video_id
    current_meta["voiceovers"] = voiceovers

    _write_json_file(meta_path, current_meta)
    content_service.register_artifact(
        video_id,
        meta_path,
        kind="voiceover:manifest",
        media_type="application/json",
    )


def _build_subtitle_context(subtitle_path: Optional[str], timestamp: Any, window_seconds: float) -> str:
    if timestamp is None or not subtitle_path or not os.path.exists(subtitle_path):
        return ""

    try:
        center = float(timestamp)
    except (TypeError, ValueError):
        return ""

    window = max(float(window_seconds), 0.0)
    start_time = max(0.0, center - window)
    end_time = center + window

    try:
        with open(subtitle_path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except Exception:
        return ""

    segments = parse_srt_to_segments(content)
    if not segments:
        return ""

    lines: list[str] = []
    for seg in segments:
        if seg.end < start_time or seg.start > end_time:
            continue
        text = seg.text.replace("\n", " ").strip()
        if not text:
            continue
        lines.append(f"[{seg.start:.1f}s] {text}")

    return "\n".join(lines)


def _load_json_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _write_json_file(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
