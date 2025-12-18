"""Explanation DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GenerateExplanationRequest:
    """Request to generate slide/frame explanation.

    All parameters must be provided by the frontend.
    """

    content_id: str
    entry_id: str  # Pre-generated ID for the explanation entry
    image_path: str  # Local path to screenshot image
    image_url: str  # API URL for the screenshot (stored with result)
    timestamp: float  # Video timestamp in seconds
    subtitle_language: str | None = None  # Source language for subtitle context
    output_language: str = ""  # Target language for LLM output
    learner_profile: str | None = None
    subtitle_context_window_seconds: float = 60.0
    # Runtime model/prompt selection (None = use defaults)
    llm_model: str | None = None
    prompts: dict[str, str] | None = None  # {func_id: impl_id}


@dataclass
class ExplanationEntry:
    """A single explanation entry for a captured slide/frame."""

    id: str
    timestamp: float
    explanation: str
    created_at: str
    image_url: str
    language: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "explanation": self.explanation,
            "created_at": self.created_at,
            "image_url": self.image_url,
            "language": self.language,
        }


@dataclass
class ExplanationResult:
    """Result of explanation generation."""

    content_id: str
    entry: ExplanationEntry
    status: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "content_id": self.content_id,
            "explanation": self.entry.explanation,
            "data": self.entry.to_dict(),
            "status": self.status,
        }
