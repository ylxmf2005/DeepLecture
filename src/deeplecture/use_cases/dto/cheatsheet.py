"""Cheatsheet DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

# =============================================================================
# Internal DTOs
# =============================================================================


@dataclass
class KnowledgeItem:
    """Single knowledge item extracted from content.

    Used internally between extraction and rendering stages.
    """

    category: str  # formula | definition | condition | algorithm | constant | example | explanation | derivation | comparison | application | pitfall | relationship
    content: str  # The actual content
    criticality: str  # high | medium | low
    tags: list[str] = field(default_factory=list)
    source_start: float | None = None  # Video timestamp in seconds (from timestamped context)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        d: dict[str, Any] = {
            "category": self.category,
            "content": self.content,
            "criticality": self.criticality,
            "tags": self.tags,
        }
        if self.source_start is not None:
            d["source_start"] = self.source_start
        return d


# =============================================================================
# Request DTOs
# =============================================================================


@dataclass
class GenerateCheatsheetRequest:
    """Request to generate AI cheatsheet.

    All language parameters must be provided by the frontend.
    """

    content_id: str
    language: str  # Required: output language
    context_mode: str = "both"  # subtitle | slide | both
    user_instruction: str = ""
    min_criticality: str = "medium"  # high | medium | low
    target_pages: int = 2  # Approximate target length
    subject_type: str = "auto"  # stem | humanities | auto
    llm_model: str | None = None  # Optional model override
    prompts: dict[str, str] | None = None  # Optional prompt overrides


@dataclass
class SaveCheatsheetRequest:
    """Request to save cheatsheet content."""

    content_id: str
    content: str


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class CheatsheetStats:
    """Statistics about generated cheatsheet."""

    total_items: int = 0
    by_category: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_items": self.total_items,
            "by_category": self.by_category,
        }


@dataclass
class CheatsheetResult:
    """Result of cheatsheet retrieval or save."""

    content_id: str
    content: str
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "content": self.content,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class GeneratedCheatsheetResult:
    """Result of AI-generated cheatsheet creation."""

    content_id: str
    content: str
    updated_at: datetime | None
    used_sources: list[str]  # ["subtitle", "slide"]
    stats: CheatsheetStats = field(default_factory=CheatsheetStats)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "content": self.content,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "used_sources": self.used_sources,
            "stats": self.stats.to_dict(),
        }
