"""Quiz DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

# =============================================================================
# Internal DTOs
# =============================================================================


@dataclass
class QuizItem:
    """Single quiz item (MCQ question).

    Represents a multiple-choice question with 4 options.
    """

    stem: str  # Question text
    options: list[str]  # Exactly 4 options
    answer_index: int  # Correct answer index (0-3)
    explanation: str  # Why correct + why distractors are wrong
    source_category: str | None = None  # formula | definition | condition | etc.
    source_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stem": self.stem,
            "options": self.options,
            "answer_index": self.answer_index,
            "explanation": self.explanation,
            "source_category": self.source_category,
            "source_tags": self.source_tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuizItem:
        """Create from dictionary."""
        return cls(
            stem=data.get("stem", ""),
            options=data.get("options", []),
            answer_index=data.get("answer_index", 0),
            explanation=data.get("explanation", ""),
            source_category=data.get("source_category"),
            source_tags=data.get("source_tags", []),
        )


# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class GenerateQuizRequest:
    """Request to generate AI quiz.

    All language parameters must be provided by the frontend.
    """

    content_id: str
    language: str  # Required: output language
    question_count: int = 0  # 0 = auto (derived from knowledge items count)
    context_mode: str = "both"  # subtitle | slide | both
    user_instruction: str = ""
    min_criticality: str = "low"  # high | medium | low
    subject_type: str = "auto"  # stem | humanities | auto
    llm_model: str | None = None  # Optional model override
    prompts: dict[str, str] | None = None  # Optional prompt overrides


@dataclass
class SaveQuizRequest:
    """Request to save quiz content."""

    content_id: str
    language: str
    items: list[QuizItem]


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class QuizStats:
    """Statistics about generated quiz."""

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
class QuizResult:
    """Result of quiz retrieval or save."""

    content_id: str
    language: str
    items: list[QuizItem] = field(default_factory=list)
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
class GeneratedQuizResult:
    """Result of AI-generated quiz creation."""

    content_id: str
    language: str
    items: list[QuizItem]
    updated_at: datetime | None
    used_sources: list[str]  # ["subtitle", "slide"]
    stats: QuizStats = field(default_factory=QuizStats)

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
