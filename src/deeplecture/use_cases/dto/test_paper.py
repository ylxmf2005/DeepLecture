"""Test paper DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

VALID_BLOOM_LEVELS = frozenset(
    {
        "remember",
        "understand",
        "apply",
        "analyze",
        "evaluate",
        "create",
    }
)


@dataclass
class TestQuestion:
    """Single open-ended exam-style question."""

    question_type: str
    stem: str
    reference_answer: str
    scoring_criteria: list[str]
    bloom_level: str
    source_timestamp: float | None = None
    source_category: str | None = None
    source_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question_type": self.question_type,
            "stem": self.stem,
            "reference_answer": self.reference_answer,
            "scoring_criteria": self.scoring_criteria,
            "bloom_level": self.bloom_level,
            "source_timestamp": self.source_timestamp,
            "source_category": self.source_category,
            "source_tags": self.source_tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestQuestion:
        """Create from dictionary."""
        return cls(
            question_type=data.get("question_type", ""),
            stem=data.get("stem", ""),
            reference_answer=data.get("reference_answer", ""),
            scoring_criteria=data.get("scoring_criteria", []),
            bloom_level=data.get("bloom_level", ""),
            source_timestamp=data.get("source_timestamp"),
            source_category=data.get("source_category"),
            source_tags=data.get("source_tags", []),
        )


@dataclass
class GenerateTestPaperRequest:
    """Request to generate AI test paper questions."""

    content_id: str
    language: str
    context_mode: str = "both"  # subtitle | slide | both
    user_instruction: str = ""
    min_criticality: str = "medium"  # high | medium | low
    subject_type: str = "auto"  # auto | stem | humanities
    llm_model: str | None = None
    prompts: dict[str, str] | None = None


@dataclass
class TestPaperStats:
    """Statistics about generated test paper questions."""

    total_questions: int = 0
    valid_questions: int = 0
    filtered_questions: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_bloom_level: dict[str, int] = field(default_factory=dict)
    by_question_type: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_questions": self.total_questions,
            "valid_questions": self.valid_questions,
            "filtered_questions": self.filtered_questions,
            "by_category": self.by_category,
            "by_bloom_level": self.by_bloom_level,
            "by_question_type": self.by_question_type,
        }


@dataclass
class TestPaperResult:
    """Result of test paper retrieval."""

    content_id: str
    language: str
    questions: list[TestQuestion] = field(default_factory=list)
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "language": self.language,
            "questions": [question.to_dict() for question in self.questions],
            "count": len(self.questions),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class GeneratedTestPaperResult:
    """Result of AI-generated test paper creation."""

    content_id: str
    language: str
    questions: list[TestQuestion]
    updated_at: datetime | None
    used_sources: list[str]
    stats: TestPaperStats = field(default_factory=TestPaperStats)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "language": self.language,
            "questions": [question.to_dict() for question in self.questions],
            "count": len(self.questions),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "used_sources": self.used_sources,
            "stats": self.stats.to_dict(),
        }
