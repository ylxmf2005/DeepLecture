"""Fact verification DTOs (Data Transfer Objects)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime


VerdictType = Literal["supported", "disputed", "unverifiable", "context_missing"]


@dataclass
class Evidence:
    """A piece of evidence supporting or refuting a claim."""

    url: str
    title: str
    publisher: str
    quote: str
    retrieved_at: str


@dataclass
class Claim:
    """A factual claim extracted from video content."""

    claim_id: str
    text: str
    start: float
    end: float
    verdict: VerdictType
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    notes: str = ""


@dataclass
class GenerateVerificationRequest:
    """Request to generate fact verification report."""

    content_id: str
    language: str


@dataclass
class VerificationReport:
    """Complete fact verification report."""

    report_id: str
    content_id: str
    language: str
    created_at: datetime
    claims: list[Claim]
    summary: str

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "report_id": self.report_id,
            "content_id": self.content_id,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "text": c.text,
                    "start": c.start,
                    "end": c.end,
                    "verdict": c.verdict,
                    "confidence": c.confidence,
                    "evidence": [
                        {
                            "url": e.url,
                            "title": e.title,
                            "publisher": e.publisher,
                            "quote": e.quote,
                            "retrieved_at": e.retrieved_at,
                        }
                        for e in c.evidence
                    ],
                    "notes": c.notes,
                }
                for c in self.claims
            ],
            "summary": self.summary,
        }
