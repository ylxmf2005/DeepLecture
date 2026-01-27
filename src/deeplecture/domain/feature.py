"""
Feature Status State Machine

Defines strict state transitions for content features (subtitle, video, timeline, etc.)
Follows Open/Closed Principle - extend by adding new transitions, not modifying logic.
"""

from __future__ import annotations

from enum import Enum


class FeatureStatus(str, Enum):
    """
    Status values for content features.

    State machine:
        none -> processing (start job)
        processing -> ready (success)
        processing -> error (failure)
        processing -> none (cancelled/reset)
        error -> processing (retry)
        error -> none (reset)
        ready -> processing (regenerate)
        ready -> none (delete)
    """

    NONE = "none"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, value: str | None) -> FeatureStatus:
        """Convert string to FeatureStatus, defaulting to NONE."""
        if not value:
            return cls.NONE
        try:
            return cls(value.lower())
        except ValueError:
            return cls.NONE


class FeatureType(str, Enum):
    """Content feature types that have status tracking."""

    VIDEO = "video"
    SUBTITLE = "subtitle"
    TRANSLATION = "translation"
    ENHANCED = "enhanced"
    ENHANCE_TRANSLATE = "enhance_translate"
    TIMELINE = "timeline"
    NOTES = "notes"
    CHEATSHEET = "cheatsheet"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, value: str) -> FeatureType:
        """Convert string to FeatureType."""
        return cls(value.lower())


class StatusTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""

    def __init__(
        self,
        feature: FeatureType | str,
        from_status: FeatureStatus | str,
        to_status: FeatureStatus | str,
        message: str | None = None,
    ):
        self.feature = (
            feature if isinstance(feature, FeatureType) else FeatureType.from_str(feature)
        )
        self.from_status = (
            from_status
            if isinstance(from_status, FeatureStatus)
            else FeatureStatus.from_str(from_status)
        )
        self.to_status = (
            to_status
            if isinstance(to_status, FeatureStatus)
            else FeatureStatus.from_str(to_status)
        )
        self.message = (
            message
            or f"Invalid transition for {self.feature}: {self.from_status} -> {self.to_status}"
        )
        super().__init__(self.message)


# Valid transitions: from_status -> set of allowed to_statuses
VALID_TRANSITIONS: dict[FeatureStatus, frozenset[FeatureStatus]] = {
    FeatureStatus.NONE: frozenset({FeatureStatus.PROCESSING}),
    FeatureStatus.PROCESSING: frozenset(
        {FeatureStatus.READY, FeatureStatus.ERROR, FeatureStatus.NONE}
    ),
    FeatureStatus.READY: frozenset({FeatureStatus.PROCESSING, FeatureStatus.NONE}),
    FeatureStatus.ERROR: frozenset({FeatureStatus.PROCESSING, FeatureStatus.NONE}),
}


def validate_transition(
    from_status: FeatureStatus | str,
    to_status: FeatureStatus | str,
) -> bool:
    """
    Check if a status transition is valid.

    Args:
        from_status: Current status
        to_status: Target status

    Returns:
        True if transition is valid, False otherwise
    """
    if isinstance(from_status, str):
        from_status = FeatureStatus.from_str(from_status)
    if isinstance(to_status, str):
        to_status = FeatureStatus.from_str(to_status)

    if from_status == to_status:
        return True

    allowed = VALID_TRANSITIONS.get(from_status, frozenset())
    return to_status in allowed
