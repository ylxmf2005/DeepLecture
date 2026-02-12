"""Timeline domain errors."""

from __future__ import annotations

from deeplecture.domain.errors.base import DomainError


class TimelineError(DomainError):
    """Base class for timeline errors."""


class TimelineGenerationError(TimelineError):
    """Raised when timeline generation fails."""
