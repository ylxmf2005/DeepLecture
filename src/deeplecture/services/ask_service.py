from __future__ import annotations

import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import logging

from deeplecture.app_context import get_app_context
from deeplecture.config.config import load_config
from deeplecture.prompts.ask_prompt import get_ask_video_prompt, get_summarize_context_prompt
from deeplecture.services.content_service import ContentService
from deeplecture.storage.fs_ask_storage import AskStorage, ConversationRecord, get_default_ask_storage
from deeplecture.storage.metadata_storage import MetadataStorage, get_default_metadata_storage
from deeplecture.transcription.interactive import parse_srt_to_segments
from deeplecture.use_cases.shared.prompt_safety import normalize_llm_markdown

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from deeplecture.llm.llm_factory import LLMFactory

UTC = getattr(datetime, "UTC", timezone.utc)
logger = logging.getLogger(__name__)

# Module-level executor for non-blocking LLM calls (can take 1-20 seconds)
_llm_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="llm_call")


def _sanitize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


class AskService:
    def __init__(
        self,
        storage: Optional[AskStorage] = None,
        metadata_storage: Optional[MetadataStorage] = None,
        content_service: Optional[ContentService] = None,
        llm_factory: Optional["LLMFactory"] = None,
    ) -> None:
        self._metadata_storage: MetadataStorage = (
            metadata_storage or get_default_metadata_storage()
        )
        self._content_service = content_service or ContentService(
            metadata_storage=self._metadata_storage,
        )
        self._storage: AskStorage = storage or get_default_ask_storage(self._content_service)
        # Allow callers/tests to inject a dedicated LLM factory; when not
        # provided we fall back to the global application-level factory.
        if llm_factory is None:
            ctx = get_app_context()
            ctx.ensure_initialized()
            self._llm_factory = ctx.llm_factory
        else:
            self._llm_factory = llm_factory

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _content_exists(self, content_id: str) -> bool:
        """Check if content (video or slide) exists."""
        # Check metadata first (works for both video and slide)
        return self._metadata_storage.exists(content_id)

    def _require_content(self, content_id: str) -> None:
        if not self._content_exists(content_id):
            raise FileNotFoundError(f"Content (video or slide) for ID {content_id} not found")

    def _resolve_llm_factory(self) -> "LLMFactory":
        if self._llm_factory is None:
            ctx = get_app_context()
            ctx.ensure_initialized()
            self._llm_factory = ctx.llm_factory
        return self._llm_factory

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------
    def list_conversations(self, video_id: str) -> List[Dict[str, Any]]:
        self._require_content(video_id)
        records = self._storage.list_conversations(video_id)
        items: List[Dict[str, Any]] = []
        for record in records:
            messages = record.messages or []
            last_message_content = ""
            if messages:
                last = messages[-1]
                last_message_content = _sanitize_text(last.get("content") or "")

            preview = last_message_content[:120]
            items.append(
                {
                    "id": record.conversation_id,
                    "title": record.title,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                    "last_message_preview": preview,
                }
            )
        return items

    def get_conversation(self, video_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        self._require_content(video_id)
        record = self._storage.get_conversation(video_id, conversation_id)
        if not record:
            return None
        return {
            "id": record.conversation_id,
            "title": record.title,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "messages": record.messages or [],
        }

    def create_conversation(self, video_id: str, title: str) -> Dict[str, Any]:
        self._require_content(video_id)

        conv_id = str(uuid.uuid4())
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        resolved_title = title.strip() or "New chat"
        greeting = (
            "Hello, feel free to ask me any questions!"
        )
        record = ConversationRecord(
            video_id=video_id,
            conversation_id=conv_id,
            title=resolved_title,
            created_at=now,
            updated_at=now,
            messages=[
                {
                    "role": "assistant",
                    "content": greeting,
                    "created_at": now,
                }
            ],
        )
        self._storage.save_conversation(record)
        return {
            "id": conv_id,
            "title": resolved_title,
            "created_at": now,
            "updated_at": now,
            "messages": record.messages,
        }

    def delete_conversation(self, video_id: str, conversation_id: str) -> bool:
        self._require_content(video_id)
        return self._storage.delete_conversation(video_id, conversation_id)

    # ------------------------------------------------------------------
    # Q&A
    # ------------------------------------------------------------------
    def ask_video(
        self,
        *,
        video_id: str,
        conversation_id: str,
        question: str,
        context_items: List[Dict[str, Any]],
        learner_profile: str = "",
        context_window_override: Optional[float] = None,
    ) -> str:
        self._require_content(video_id)

        conversation = self._storage.get_conversation(video_id, conversation_id)
        if not conversation:
            raise FileNotFoundError("Conversation not found")

        resolved_question = _sanitize_text(question)

        # Resolve subtitle context window (seconds) once per request so that
        # all screenshot items use the same configuration.
        window_seconds = self._get_context_window_seconds(context_window_override)

        history_block = self._build_history_block(conversation.messages)

        context_block, screenshot_image_path = self._build_context_block(
            video_id,
            context_items,
            window_seconds,
        )

        profile_str = _sanitize_text(learner_profile)
        system_prompt = get_ask_video_prompt(learner_profile=profile_str)

        user_parts: List[str] = []

        if context_block:
            user_parts.append(
                "Here are context snippets from the lecture timeline, content, and slides:\n"
                f"{context_block}"
            )

        if history_block:
            user_parts.append(
                "Here is the recent conversation between you (Tutor) and the student:\n"
                f"{history_block}"
            )

        user_parts.append(
            "Now answer the student's current question based on the lecture content and the conversation above.\n"
            f"Student's question:\n{resolved_question}"
        )

        user_prompt = "\n\n".join(user_parts)

        factory = self._resolve_llm_factory()
        if hasattr(factory, "get_llm_for_task"):
            llm = factory.get_llm_for_task("ask_video")
        else:
            llm = factory.get_llm()
        answer = llm.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            image_path=screenshot_image_path,
        )
        answer = normalize_llm_markdown(str(answer or ""))

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        conversation.messages.append(
            {
                "role": "user",
                "content": resolved_question,
                "created_at": now,
            }
        )
        conversation.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "created_at": now,
            }
        )
        conversation.updated_at = now
        self._storage.save_conversation(conversation)
        return answer

    def ask_video_async(
        self,
        *,
        video_id: str,
        conversation_id: str,
        question: str,
        context_items: List[Dict[str, Any]],
        learner_profile: str = "",
        context_window_override: Optional[float] = None,
    ) -> Future[str]:
        """
        Non-blocking version of ask_video(). Returns a Future that resolves to the answer.
        Use future.result() to block and get the result when needed.
        """
        return _llm_executor.submit(
            self.ask_video,
            video_id=video_id,
            conversation_id=conversation_id,
            question=question,
            context_items=context_items,
            learner_profile=learner_profile,
            context_window_override=context_window_override,
        )

    def summarize_context(
        self,
        *,
        context_items: List[Dict[str, Any]],
        learner_profile: str = "",
    ) -> str:
        if not context_items:
            return ""

        context_lines: List[str] = []
        for item in context_items:
            item_type = str(item.get("type") or "").lower()
            if item_type == "subtitle":
                text = _sanitize_text(item.get("text") or "")
                start_time = item.get("startTime")
                try:
                    start_s = float(start_time)
                    prefix = f"[{start_s:.1f}s]"
                except (TypeError, ValueError):
                    prefix = "[-]"
                context_lines.append(f"{prefix} {text}")

        context_block = "\n".join(context_lines)

        profile = _sanitize_text(learner_profile)
        system_prompt = get_summarize_context_prompt(learner_profile=profile)

        user_prompt = (
            "Here is the transcript of the content I missed:\n"
            f"{context_block}\n\n"
            "Please provide a summary of what was discussed."
        )

        factory = self._resolve_llm_factory()
        if hasattr(factory, "get_llm_for_task"):
            llm = factory.get_llm_for_task("ask_video")
        else:
            llm = factory.get_llm()
        summary = llm.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            image_path=None,
        )
        return normalize_llm_markdown(str(summary or ""))

    def summarize_context_async(
        self,
        *,
        context_items: List[Dict[str, Any]],
        learner_profile: str = "",
    ) -> Future[str]:
        """
        Non-blocking version of summarize_context(). Returns a Future that resolves to the summary.
        Use future.result() to block and get the result when needed.
        """
        return _llm_executor.submit(
            self.summarize_context,
            context_items=context_items,
            learner_profile=learner_profile,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_context_window_seconds(context_window_override: Optional[float]) -> float:
        try:
            if context_window_override is not None:
                value = float(context_window_override)
            else:
                config = load_config()
                slides_cfg = (config or {}).get("slides") or {}
                explanation_cfg = slides_cfg.get("explanation") or {}
                raw = explanation_cfg.get("subtitle_context_window_seconds", 30.0)
                value = float(raw)
            if value <= 0:
                return 30.0
            return value
        except Exception:
            return 30.0

    @staticmethod
    def _build_history_block(messages: List[Dict[str, Any]]) -> str:
        history_lines: List[str] = []
        for msg in (messages or [])[-8:]:
            role = str(msg.get("role", "")).lower()
            content = _sanitize_text(msg.get("content") or "")
            if not content:
                continue
            prefix = "Student" if role == "user" else "Tutor"
            history_lines.append(f"{prefix}: {content}")
        return "\n".join(history_lines)

    def _build_context_block(
        self,
        video_id: str,
        context_items: List[Dict[str, Any]],
        window_seconds: float,
    ) -> tuple[str, Optional[str]]:
        context_lines: List[str] = []
        screenshot_image_path: Optional[str] = None

        for item in context_items:
            item_type = str(item.get("type") or "").lower()

            if item_type == "timeline":
                title = _sanitize_text(item.get("title") or "")
                content = _sanitize_text(item.get("content") or "")
                start = item.get("start")
                end = item.get("end")
                try:
                    start_s = float(start)
                    end_s = float(end)
                    time_span = f"{start_s:.1f}s → {end_s:.1f}s"
                except (TypeError, ValueError):
                    time_span = "unknown time range"
                line = f"[Timeline segment {time_span}] {title}\n{content}"
                context_lines.append(line)

            elif item_type == "subtitle":
                text = _sanitize_text(item.get("text") or "")
                start_time = item.get("startTime")
                try:
                    start_s = float(start_time)
                    prefix = f"[Subtitle at {start_s:.1f}s]"
                except (TypeError, ValueError):
                    prefix = "[Subtitle]"
                context_lines.append(f"{prefix} {text}")

            elif item_type == "screenshot":
                timestamp = item.get("timestamp")
                ts_value: Optional[float]
                try:
                    ts_value = float(timestamp)
                    prefix = f"[Screenshot at {ts_value:.1f}s]"
                except (TypeError, ValueError):
                    ts_value = None
                    prefix = "[Screenshot]"

                line_parts: List[str] = [
                    f"{prefix} A captured frame from the lecture video. "
                    "You can visually inspect this slide to better answer the question."
                ]

                if ts_value is not None:
                    subtitle_context = self._build_subtitle_context_for_timestamp(
                        video_id,
                        ts_value,
                        window_seconds,
                    )
                    if subtitle_context:
                        line_parts.append(
                            "Nearby transcript snippet from the original-language subtitles "
                            f"(about ±{window_seconds:.0f}s around this frame):\n"
                            f"{subtitle_context}"
                        )

                context_lines.append("\n".join(line_parts))

                if screenshot_image_path is None:
                    path = item.get("imagePath") or item.get("image_path")
                    if isinstance(path, str) and path.strip():
                        screenshot_image_path = path.strip()

        return "\n\n".join(context_lines), screenshot_image_path

    def _resolve_subtitle_path(self, video_id: str) -> Optional[str]:
        enhanced = self._content_service.get_enhanced_subtitle_path(video_id)
        if enhanced and os.path.exists(enhanced):
            return enhanced

        path = self._content_service.get_subtitle_path(video_id)
        if path and os.path.exists(path):
            return path

        return None

    def _build_subtitle_context_for_timestamp(
        self,
        video_id: str,
        timestamp: Optional[float],
        window_seconds: float,
    ) -> str:
        if timestamp is None:
            return ""

        subtitle_path = self._resolve_subtitle_path(video_id)
        if not subtitle_path:
            return ""

        try:
            with open(subtitle_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            logger.error(
                "Failed to read subtitle file %s for context: %s",
                subtitle_path,
                exc,
            )
            return ""

        segments = parse_srt_to_segments(content)
        if not segments:
            return ""

        try:
            center = float(timestamp)
        except (TypeError, ValueError):
            return ""

        window = max(float(window_seconds), 0.0)
        start_time = max(0.0, center - window)
        end_time = center + window

        lines: List[str] = []
        for seg in segments:
            if seg.end < start_time or seg.start > end_time:
                continue
            text = _sanitize_text(seg.text)
            if not text:
                continue
            lines.append(f"[{seg.start:.1f}s] {text}")

        return "\n".join(lines)
