"""
Task - Re-export from domain layer.

DEPRECATED: Import from deeplecture.domain instead.
This module exists only for backwards compatibility.
"""

from __future__ import annotations

# Re-export from domain layer (canonical location)
from deeplecture.domain.entities.task import Task, TaskStatus

__all__ = ["Task", "TaskStatus"]
