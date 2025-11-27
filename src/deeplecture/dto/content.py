"""Content-related Data Transfer Objects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContentUploadResult:
    content_id: str
    filename: str
    content_type: str
    message: str


@dataclass
class VideoImportJobResult:
    content_id: str
    filename: str
    content_type: str
    status: str
    message: str
    job_id: Optional[str]


@dataclass
class VideoMergeJobResult:
    content_id: str
    filename: str
    content_type: str
    status: str
    message: str
    job_id: Optional[str]
    requires_reencode: bool = False
    reencode_reason: Optional[str] = None
