"""DTOs for Note Read-Aloud feature."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReadAloudRequest:
    """Request to start read-aloud streaming."""

    content_id: str
    target_language: str  # ISO 639-1, e.g. "en", "zh"
    source_language: str | None = None  # None = same as target (no translation)
    tts_model: str | None = None  # None = use task_models config
    start_paragraph: int = 0  # For paragraph-jump reconnect


@dataclass
class ParagraphMeta:
    """Metadata for a single paragraph."""

    index: int
    title: str | None
    sentence_count: int


@dataclass
class ReadAloudMeta:
    """First SSE event: total counts and paragraph metadata."""

    total_paragraphs: int
    total_sentences: int
    paragraphs: list[ParagraphMeta] = field(default_factory=list)


@dataclass
class SentenceReady:
    """SSE event: a sentence's audio is ready for retrieval."""

    paragraph_index: int
    sentence_index: int
    sentence_key: str  # e.g. "p0_s2" — used to fetch audio via REST
    original_text: str
    spoken_text: str  # May differ from original if translated


@dataclass
class ReadAloudComplete:
    """SSE event: read-aloud generation finished."""

    total_paragraphs: int
    total_sentences: int
    total_errors: int
