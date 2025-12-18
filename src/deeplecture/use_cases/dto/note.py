"""Note DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class GenerateNoteRequest:
    """Request to generate AI notes.

    All language parameters must be provided by the frontend.
    """

    content_id: str
    language: str  # Required: output language for generated notes
    context_mode: str = "both"  # subtitle | slide | both
    user_instruction: str = ""
    learner_profile: str = ""
    max_parts: int | None = None
    # Runtime model/prompt selection (None = use defaults)
    llm_model: str | None = None
    prompts: dict[str, str] | None = None  # {func_id: impl_id}


@dataclass
class SaveNoteRequest:
    """Request to save note content."""

    content_id: str
    content: str


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class NotePart:
    """Single section within a structured note."""

    id: int
    title: str
    summary: str
    focus_points: list[str] = field(default_factory=list)


@dataclass
class NoteResult:
    """Result of note retrieval or save."""

    content_id: str
    content: str
    updated_at: datetime | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "content": self.content,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class GeneratedNoteResult:
    """Result of AI-generated note creation."""

    content_id: str
    content: str
    updated_at: datetime | None
    outline: list[NotePart]
    used_sources: list[str]  # ["subtitle", "slide"]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "content": self.content,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "outline": [
                {
                    "id": part.id,
                    "title": part.title,
                    "summary": part.summary,
                    "focus_points": part.focus_points,
                }
                for part in self.outline
            ],
            "used_sources": self.used_sources,
        }
