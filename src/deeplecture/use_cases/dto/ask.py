"""Ask use case DTOs - Data Transfer Objects for Q&A functionality."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Conversation:
    """
    Conversation domain object.

    Represents a Q&A conversation thread between user and assistant.
    """

    id: str
    content_id: str
    title: str
    messages: list[Message]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [msg.to_dict() for msg in self.messages],
        }


@dataclass
class Message:
    """Single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }


@dataclass
class ConversationSummary:
    """Lightweight conversation summary for listing."""

    id: str
    title: str
    created_at: str
    updated_at: str
    last_message_preview: str


# =========================================================================
# REQUEST DTOs
# =========================================================================


@dataclass
class CreateConversationRequest:
    """Request to create new conversation."""

    content_id: str
    title: str = "New chat"


@dataclass
class ContextItem:
    """
    Context item for Q&A.

    Can be:
    - timeline: Timeline segment (title, content, start, end)
    - subtitle: Subtitle segment (text, startTime)
    - screenshot: Screenshot with timestamp (timestamp, imagePath/imageUrl)
    """

    type: str  # "timeline", "subtitle", "screenshot"
    data: dict[str, Any]

    @property
    def timeline_title(self) -> str | None:
        """Get timeline title if this is a timeline item."""
        return self.data.get("title") if self.type == "timeline" else None

    @property
    def timeline_content(self) -> str | None:
        """Get timeline content if this is a timeline item."""
        return self.data.get("content") if self.type == "timeline" else None

    @property
    def timeline_start(self) -> float | None:
        """Get timeline start time if this is a timeline item."""
        return self.data.get("start") if self.type == "timeline" else None

    @property
    def timeline_end(self) -> float | None:
        """Get timeline end time if this is a timeline item."""
        return self.data.get("end") if self.type == "timeline" else None

    @property
    def subtitle_text(self) -> str | None:
        """Get subtitle text if this is a subtitle item."""
        return self.data.get("text") if self.type == "subtitle" else None

    @property
    def subtitle_start_time(self) -> float | None:
        """Get subtitle start time if this is a subtitle item."""
        return self.data.get("startTime") if self.type == "subtitle" else None

    @property
    def screenshot_timestamp(self) -> float | None:
        """Get screenshot timestamp if this is a screenshot item."""
        return self.data.get("timestamp") if self.type == "screenshot" else None

    @property
    def screenshot_path(self) -> str | None:
        """Get screenshot path if this is a screenshot item."""
        path = (
            self.data.get("imagePath")
            or self.data.get("image_path")
            or self.data.get("imageUrl")
            or self.data.get("image_url")
        )
        return path if self.type == "screenshot" else None


@dataclass
class AskQuestionRequest:
    """Request to ask a question within a conversation."""

    content_id: str
    conversation_id: str
    question: str
    context_items: list[ContextItem] = field(default_factory=list)
    learner_profile: str = ""
    context_window_seconds: float | None = None
    # Runtime model/prompt selection (None = use defaults)
    llm_model: str | None = None
    prompts: dict[str, str] | None = None  # {func_id: impl_id}


@dataclass
class SummarizeContextRequest:
    """Request to summarize context (e.g., missed content)."""

    context_items: list[ContextItem]
    learner_profile: str = ""
    # Runtime model/prompt selection (None = use defaults)
    llm_model: str | None = None
    prompts: dict[str, str] | None = None  # {func_id: impl_id}


# =========================================================================
# RESPONSE DTOs
# =========================================================================


@dataclass
class AskQuestionResponse:
    """Response from asking a question."""

    answer: str
    conversation: Conversation


@dataclass
class SummarizeContextResponse:
    """Response from summarizing context."""

    summary: str
