"""Flashcard DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

# =============================================================================
# Internal DTOs
# =============================================================================


@dataclass
class FlashcardItem:
    """Single flashcard for active recall study.

    Front: question, term, or prompt that triggers recall.
    Back: answer, definition, or explanation.
    """

    front: str  # Question or term
    back: str  # Answer or explanation
    source_timestamp: float | None = None  # Video timestamp in seconds
    source_category: str | None = None  # formula | definition | concept | ...

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "front": self.front,
            "back": self.back,
            "source_timestamp": self.source_timestamp,
            "source_category": self.source_category,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FlashcardItem:
        """Create from dictionary."""
        return cls(
            front=data.get("front", ""),
            back=data.get("back", ""),
            source_timestamp=data.get("source_timestamp"),
            source_category=data.get("source_category"),
        )


# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class GenerateFlashcardRequest:
    """Request to generate AI flashcards.

    All language parameters must be provided by the frontend.
    Card count is determined by the model (not configurable).
    """

    content_id: str
    language: str  # Required: output language
    context_mode: str = "both"  # subtitle | slide | both
    user_instruction: str = ""
    min_criticality: str = "low"  # high | medium | low
    subject_type: str = "auto"  # stem | humanities | auto
    llm_model: str | None = None  # Optional model override
    prompts: dict[str, str] | None = None  # Optional prompt overrides


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class FlashcardStats:
    """Statistics about generated flashcards."""

    total_items: int = 0  # Items from LLM
    valid_items: int = 0  # Items after validation
    filtered_items: int = 0  # Items removed by validation
    by_category: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_items": self.total_items,
            "valid_items": self.valid_items,
            "filtered_items": self.filtered_items,
            "by_category": self.by_category,
        }


@dataclass
class FlashcardResult:
    """Result of flashcard retrieval."""

    content_id: str
    language: str
    items: list[FlashcardItem] = field(default_factory=list)
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "language": self.language,
            "items": [item.to_dict() for item in self.items],
            "count": len(self.items),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class GeneratedFlashcardResult:
    """Result of AI-generated flashcard creation."""

    content_id: str
    language: str
    items: list[FlashcardItem]
    updated_at: datetime | None
    used_sources: list[str]  # ["subtitle", "slide"]
    stats: FlashcardStats = field(default_factory=FlashcardStats)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "language": self.language,
            "items": [item.to_dict() for item in self.items],
            "count": len(self.items),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "used_sources": self.used_sources,
            "stats": self.stats.to_dict(),
        }
