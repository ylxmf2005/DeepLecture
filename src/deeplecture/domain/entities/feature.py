"""
Feature Status Entity

Defines feature types and their status states.
"""

from __future__ import annotations

from enum import Enum


class FeatureType(str, Enum):
    """Types of features that can be generated for content."""

    SUBTITLE = "subtitle"
    ENHANCE_TRANSLATE = "enhance_translate"
    TIMELINE = "timeline"
    NOTES = "notes"
    VIDEO = "video"  # For slide-to-video generation


class FeatureStatus(str, Enum):
    """Status of a feature generation process."""

    NONE = "none"  # Not started
    PROCESSING = "processing"  # In progress
    READY = "ready"  # Completed successfully
    ERROR = "error"  # Failed

    @classmethod
    def is_valid_transition(cls, from_status: FeatureStatus, to_status: FeatureStatus) -> bool:
        """
        Check if a status transition is valid.

        Valid transitions:
        - none -> processing (start)
        - processing -> ready (success)
        - processing -> error (failure)
        - error -> processing (retry)
        - any -> none (reset)
        """
        valid_transitions = {
            cls.NONE: {cls.PROCESSING, cls.NONE},
            cls.PROCESSING: {cls.READY, cls.ERROR, cls.NONE},
            cls.READY: {cls.PROCESSING, cls.NONE},  # Allow reprocessing
            cls.ERROR: {cls.PROCESSING, cls.NONE},  # Allow retry or reset
        }
        return to_status in valid_transitions.get(from_status, set())
