"""Note-related Data Transfer Objects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class NoteDTO:
    video_id: str
    content: str
    updated_at: Optional[str]


@dataclass
class NotePart:
    id: int
    title: str
    summary: str
    focus_points: List[str]


@dataclass
class GeneratedNoteResult:
    video_id: str
    content: str
    updated_at: Optional[str]
    outline: List[NotePart]
    used_sources: List[str]


@dataclass
class NoteGenerationJobResult:
    note_path: str
    status: str
    message: str
    job_id: Optional[str]
