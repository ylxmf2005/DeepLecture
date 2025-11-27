"""Subtitle-related Data Transfer Objects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SubtitleGenerationResult:
    subtitle_path: str
    status: str
    message: str
    job_id: Optional[str] = None


@dataclass
class SubtitleEnhanceTranslateResult:
    translated_path: str
    status: str
    message: str
    job_id: Optional[str] = None
