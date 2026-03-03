"""Text filter protocol for converting rich text to speakable sentences."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class FilteredParagraph:
    """A paragraph of filtered, speakable text."""

    index: int
    title: str | None = None
    sentences: list[str] = field(default_factory=list)


class TextFilterProtocol(Protocol):
    """
    Contract for converting rich text (e.g. Markdown) to speakable sentences.

    Implementations should strip non-speakable elements (code blocks, formulas,
    URLs, images, etc.) and split the remaining text into paragraphs and sentences.
    """

    def filter_to_sentences(self, text: str) -> list[FilteredParagraph]:
        """
        Filter text and split into speakable paragraphs/sentences.

        Args:
            text: Raw text (e.g. Markdown content)

        Returns:
            List of paragraphs, each containing speakable sentences
        """
        ...
