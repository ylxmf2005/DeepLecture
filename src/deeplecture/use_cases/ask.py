"""Ask use case - Q&A and conversation management."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.ask import (
    AskQuestionResponse,
    Conversation,
    Message,
    SummarizeContextResponse,
)
from deeplecture.use_cases.prompts.ask import get_response_language
from deeplecture.use_cases.shared.prompt_safety import (
    sanitize_learner_profile,
    sanitize_question,
    sanitize_user_input,
    wrap_user_content,
)
from deeplecture.use_cases.shared.subtitle import (
    load_first_available_subtitle_segments,
    prioritize_subtitle_languages,
)

if TYPE_CHECKING:
    from deeplecture.config import AskConfig
    from deeplecture.use_cases.dto.ask import (
        AskQuestionRequest,
        ConversationSummary,
        CreateConversationRequest,
        SummarizeContextRequest,
    )
    from deeplecture.use_cases.interfaces import (
        AskStorageProtocol,
        MetadataStorageProtocol,
        SubtitleStorageProtocol,
    )
    from deeplecture.use_cases.interfaces.llm_provider import LLMProviderProtocol
    from deeplecture.use_cases.interfaces.prompt_registry import PromptRegistryProtocol

UTC = getattr(datetime, "UTC", timezone.utc)
logger = logging.getLogger(__name__)


def _sanitize_text(text: str) -> str:
    """Sanitize non-user text (subtitles/timeline/history) before embedding into prompts."""
    return sanitize_user_input(text, max_length=10000)


class AskUseCase:
    """
    Q&A and conversation management use case.

    Orchestrates:
    - Conversation CRUD operations
    - Question answering with context (subtitles, timeline, screenshots)
    - Context summarization
    - Conversation persistence
    """

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        ask_storage: AskStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        llm_provider: LLMProviderProtocol,
        prompt_registry: PromptRegistryProtocol,
        config: AskConfig,
    ) -> None:
        """
        Initialize AskUseCase.

        Args:
            metadata_storage: Content metadata storage
            ask_storage: Conversation storage
            subtitle_storage: Subtitle storage for context
            llm_provider: LLM provider for runtime model selection
            prompt_registry: Prompt registry for prompt selection
            config: AskConfig from settings (injected via DI)
        """
        self._metadata = metadata_storage
        self._ask_storage = ask_storage
        self._subtitles = subtitle_storage
        self._llm_provider = llm_provider
        self._prompt_registry = prompt_registry
        self._config = config

    # =========================================================================
    # PUBLIC API - Conversation Management
    # =========================================================================

    def list_conversations(self, content_id: str) -> list[ConversationSummary]:
        """
        List all conversations for a content item.

        Args:
            content_id: Content identifier

        Returns:
            List of conversation summaries

        Raises:
            ContentNotFoundError: If content doesn't exist
        """
        self._require_content(content_id)
        return self._ask_storage.list_conversations(content_id)

    def get_conversation(self, content_id: str, conversation_id: str) -> Conversation | None:
        """
        Get a specific conversation.

        Args:
            content_id: Content identifier
            conversation_id: Conversation identifier

        Returns:
            Conversation or None if not found

        Raises:
            ContentNotFoundError: If content doesn't exist
        """
        self._require_content(content_id)
        return self._ask_storage.get_conversation(content_id, conversation_id)

    def create_conversation(self, request: CreateConversationRequest) -> Conversation:
        """
        Create a new conversation.

        Args:
            request: Conversation creation request

        Returns:
            Created conversation

        Raises:
            ContentNotFoundError: If content doesn't exist
        """
        self._require_content(request.content_id)

        conversation_id = str(uuid.uuid4())
        now = self._get_timestamp()

        title = request.title.strip() or "New chat"
        greeting_message = Message(
            role="assistant",
            content="Hello, feel free to ask me any questions!",
            created_at=now,
        )

        conversation = Conversation(
            id=conversation_id,
            content_id=request.content_id,
            title=title,
            messages=[greeting_message],
            created_at=now,
            updated_at=now,
        )

        self._ask_storage.save_conversation(conversation)
        return conversation

    def delete_conversation(self, content_id: str, conversation_id: str) -> bool:
        """
        Delete a conversation.

        Args:
            content_id: Content identifier
            conversation_id: Conversation identifier

        Returns:
            True if deleted, False if not found

        Raises:
            ContentNotFoundError: If content doesn't exist
        """
        self._require_content(content_id)
        return self._ask_storage.delete_conversation(content_id, conversation_id)

    # =========================================================================
    # PUBLIC API - Q&A
    # =========================================================================

    def ask_question(self, request: AskQuestionRequest) -> AskQuestionResponse:
        """
        Ask a question within a conversation.

        Args:
            request: Question request with context

        Returns:
            Answer response with updated conversation

        Raises:
            ContentNotFoundError: If content doesn't exist
            ValueError: If conversation doesn't exist
        """
        self._require_content(request.content_id)

        conversation = self._ask_storage.get_conversation(
            request.content_id,
            request.conversation_id,
        )
        if not conversation:
            raise ValueError(f"Conversation not found: {request.conversation_id}")

        # Sanitize user inputs with prompt injection protection
        question = sanitize_question(request.question)
        learner_profile = sanitize_learner_profile(request.learner_profile or "")

        # Get context window
        window_seconds = self._get_context_window_seconds(request.context_window_seconds)

        # Build context and history
        context_block, screenshot_path = self._build_context_block(
            request.content_id,
            request.context_items,
            window_seconds,
        )
        history_block = self._build_history_block(conversation.messages)

        # Get LLM from provider
        llm = self._llm_provider.get(request.llm_model)

        # Build prompts with wrapped user content using registry
        language = get_response_language()

        impl_id = request.prompts.get("ask_video") if request.prompts else None
        prompt_builder = self._prompt_registry.get("ask_video", impl_id)
        spec = prompt_builder.build(
            learner_profile=learner_profile,
            language=language,
            context_block=context_block,
            history_block=history_block,
            question=wrap_user_content(question, "STUDENT_QUESTION"),
        )

        # Generate answer
        answer = llm.complete(
            spec.user_prompt,
            system_prompt=spec.system_prompt,
            image_path=screenshot_path,
        )

        # Update conversation
        now = self._get_timestamp()
        conversation.messages.append(Message(role="user", content=question, created_at=now))
        conversation.messages.append(Message(role="assistant", content=answer, created_at=now))
        conversation.updated_at = now

        self._ask_storage.save_conversation(conversation)

        return AskQuestionResponse(answer=answer, conversation=conversation)

    def summarize_context(self, request: SummarizeContextRequest) -> SummarizeContextResponse:
        """
        Summarize context (e.g., missed lecture content).

        Args:
            request: Summarization request

        Returns:
            Summary response
        """
        if not request.context_items:
            return SummarizeContextResponse(summary="")

        # Sanitize learner profile
        learner_profile = sanitize_learner_profile(request.learner_profile or "")

        # Build context block
        context_lines: list[str] = []
        for item in request.context_items:
            if item.type == "subtitle":
                text = sanitize_question(item.subtitle_text or "")
                start_time = item.subtitle_start_time
                try:
                    start_s = float(start_time) if start_time is not None else 0.0
                    prefix = f"[{start_s:.1f}s]"
                except (TypeError, ValueError):
                    prefix = "[-]"
                context_lines.append(f"{prefix} {text}")

        context_block = "\n".join(context_lines)

        # Get LLM from provider
        llm = self._llm_provider.get(request.llm_model)

        # Build prompts using registry
        language = get_response_language()

        impl_id = request.prompts.get("ask_summarize_context") if request.prompts else None
        prompt_builder = self._prompt_registry.get("ask_summarize_context", impl_id)
        spec = prompt_builder.build(
            learner_profile=learner_profile,
            language=language,
            context_block=context_block,
        )

        # Generate summary
        summary = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)

        return SummarizeContextResponse(summary=summary)

    # =========================================================================
    # INTERNAL - Context Building
    # =========================================================================

    def _build_context_block(
        self,
        content_id: str,
        context_items: list,
        window_seconds: float,
    ) -> tuple[str, str | None]:
        """
        Build context block and extract screenshot path.

        Args:
            content_id: Content identifier
            context_items: List of ContextItem objects
            window_seconds: Context window for subtitles

        Returns:
            Tuple of (context_block, screenshot_path)
        """
        context_lines: list[str] = []
        screenshot_path: str | None = None

        for item in context_items:
            item_type = item.type.lower()

            if item_type == "timeline":
                title = _sanitize_text(item.timeline_title or "")
                content = _sanitize_text(item.timeline_content or "")
                start = item.timeline_start
                end = item.timeline_end

                try:
                    start_s = float(start) if start is not None else 0.0
                    end_s = float(end) if end is not None else 0.0
                    time_span = f"{start_s:.1f}s → {end_s:.1f}s"
                except (TypeError, ValueError):
                    time_span = "unknown time range"

                line = f"[Timeline segment {time_span}] {title}\n{content}"
                context_lines.append(line)

            elif item_type == "subtitle":
                text = _sanitize_text(item.subtitle_text or "")
                start_time = item.subtitle_start_time

                try:
                    start_s = float(start_time) if start_time is not None else 0.0
                    prefix = f"[Subtitle at {start_s:.1f}s]"
                except (TypeError, ValueError):
                    prefix = "[Subtitle]"

                context_lines.append(f"{prefix} {text}")

            elif item_type == "screenshot":
                timestamp = item.screenshot_timestamp

                try:
                    ts_value = float(timestamp) if timestamp is not None else None
                    prefix = f"[Screenshot at {ts_value:.1f}s]"
                except (TypeError, ValueError):
                    ts_value = None
                    prefix = "[Screenshot]"

                line_parts: list[str] = [
                    f"{prefix} A captured frame from the lecture video. "
                    "You can visually inspect this slide to better answer the question."
                ]

                # Add nearby subtitle context
                if ts_value is not None:
                    subtitle_context = self._build_subtitle_context_for_timestamp(
                        content_id,
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

                # Extract screenshot path (use first one found)
                if screenshot_path is None:
                    path = item.screenshot_path
                    if path and path.strip():
                        screenshot_path = path.strip()

        return "\n\n".join(context_lines), screenshot_path

    def _build_subtitle_context_for_timestamp(
        self,
        content_id: str,
        timestamp: float,
        window_seconds: float,
    ) -> str:
        """
        Build subtitle context around a timestamp.

        Args:
            content_id: Content identifier
            timestamp: Center timestamp
            window_seconds: Window size

        Returns:
            Formatted subtitle context
        """
        candidate_languages = prioritize_subtitle_languages(self._subtitles.list_languages(content_id))

        loaded = load_first_available_subtitle_segments(
            self._subtitles,
            content_id=content_id,
            candidate_languages=candidate_languages,
        )
        if not loaded:
            return ""
        _lang_used, segments = loaded

        # Filter segments within window
        window = max(float(window_seconds), 0.0)
        start_time = max(0.0, timestamp - window)
        end_time = timestamp + window

        lines: list[str] = []
        for seg in segments:
            if seg.end < start_time or seg.start > end_time:
                continue
            text = _sanitize_text(seg.text)
            if text:
                lines.append(f"[{seg.start:.1f}s] {text}")

        return "\n".join(lines)

    def _build_history_block(self, messages: list[Message]) -> str:
        """
        Build conversation history block.

        Args:
            messages: List of messages

        Returns:
            Formatted history string
        """
        history_lines: list[str] = []

        max_history = int(self._config.max_history_messages)
        if max_history <= 0:
            return ""

        # Use last N messages
        recent_messages = messages[-max_history:]

        for msg in recent_messages:
            role = msg.role.lower()
            content = _sanitize_text(msg.content)
            if not content:
                continue
            prefix = "Student" if role == "user" else "Tutor"
            history_lines.append(f"{prefix}: {content}")

        return "\n".join(history_lines)

    # =========================================================================
    # INTERNAL - Utilities
    # =========================================================================

    def _require_content(self, content_id: str) -> None:
        """
        Ensure content exists.

        Args:
            content_id: Content identifier

        Raises:
            ContentNotFoundError: If content doesn't exist
        """
        if not self._metadata.exists(content_id):
            raise ContentNotFoundError(content_id)

    def _get_context_window_seconds(self, override: float | None) -> float:
        """
        Get context window seconds.

        Args:
            override: Optional override value

        Returns:
            Context window in seconds
        """
        default_value = 30.0
        min_value = 1.0
        max_value = 600.0

        if override is None:
            value = default_value
        else:
            try:
                value = float(override)
            except (TypeError, ValueError):
                value = default_value

        if value < min_value:
            return min_value
        if value > max_value:
            return max_value
        return value

    @staticmethod
    def _get_timestamp() -> str:
        """
        Get current timestamp in ISO format.

        Returns:
            ISO 8601 timestamp string
        """
        return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
