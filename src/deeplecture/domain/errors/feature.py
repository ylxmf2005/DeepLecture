"""Feature-related errors."""

from __future__ import annotations

from deeplecture.domain.errors.base import DomainError


class InvalidFeatureStatusTransitionError(DomainError):
    """Raised when feature status transition is invalid."""

    def __init__(self, feature: str, from_status: str, to_status: str) -> None:
        self.feature = feature
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Invalid status transition for {feature}: {from_status} -> {to_status}")
