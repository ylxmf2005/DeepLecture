"""
Markdown text filter for TTS read-aloud.

Converts Markdown content into clean, speakable sentences by:
1. Parsing Markdown to HTML
2. Removing code blocks, images, and other non-speakable elements
3. Extracting plain text via BeautifulSoup
4. Cleaning LaTeX, URLs, and special characters
5. Splitting into paragraphs and sentences
"""

from __future__ import annotations

import re

from deeplecture.use_cases.interfaces.text_filter import FilteredParagraph

# ---------------------------------------------------------------------------
# Regex patterns for cleaning
# ---------------------------------------------------------------------------

# LaTeX: $...$ and $$...$$
_LATEX_INLINE = re.compile(r"\$[^$]+\$")
_LATEX_BLOCK = re.compile(r"\$\$[\s\S]+?\$\$")

# URLs: http(s)://... or bare www.
_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

# Markdown image references that survive HTML conversion: ![alt](url)
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")

# Markdown link: keep text, drop URL → captured in HTML conversion, but just in case
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")

# Residual HTML entities
_HTML_ENTITY = re.compile(r"&[a-zA-Z]+;|&#\d+;")

# Multiple whitespace / newlines
_MULTI_WHITESPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINES = re.compile(r"\n{2,}")

# Sentence-ending punctuation (Western + CJK)
_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?。！？\u2026])\s+"  # split after sentence-enders followed by whitespace
)

# Non-speakable residual characters
_NON_SPEAKABLE = re.compile(r"[#*_~`|<>{}[\]\\]")


class MarkdownTextFilter:
    """Converts Markdown to speakable paragraphs and sentences."""

    def __init__(self, *, min_sentence_length: int = 2) -> None:
        self._min_len = min_sentence_length

    def filter_to_sentences(self, text: str) -> list[FilteredParagraph]:
        """
        Parse Markdown text into speakable paragraphs/sentences.

        Steps:
        1. Convert Markdown → HTML (via ``markdown`` library)
        2. Remove <pre>/<code> blocks and <img> tags
        3. Extract plain text via BeautifulSoup
        4. Clean LaTeX, URLs, residual Markdown syntax
        5. Split into paragraphs (by blank lines) and sentences
        """
        import markdown
        from bs4 import BeautifulSoup

        if not text or not text.strip():
            return []

        # Pre-clean: remove LaTeX blocks before Markdown parsing
        cleaned = _LATEX_BLOCK.sub("", text)
        cleaned = _LATEX_INLINE.sub("", cleaned)

        # Remove Markdown images before parsing
        cleaned = _MD_IMAGE.sub("", cleaned)

        # Convert Markdown links to just their text
        cleaned = _MD_LINK.sub(r"\1", cleaned)

        # Parse Markdown → HTML
        html = markdown.markdown(cleaned, extensions=["tables", "fenced_code"])

        # Parse HTML
        soup = BeautifulSoup(html, "html.parser")

        # Remove non-speakable HTML elements
        for tag in soup.find_all(["pre", "code", "img", "table", "script", "style"]):
            tag.decompose()

        # Extract headings for paragraph titles
        headings: dict[int, str] = {}
        for idx, h in enumerate(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])):
            headings[idx] = h.get_text(strip=True)

        # Split by block-level elements into paragraphs
        paragraphs: list[FilteredParagraph] = []
        para_idx = 0
        heading_idx = 0

        for element in soup.children:
            tag_name = getattr(element, "name", None)

            if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                # Next paragraph gets this heading as title
                heading_idx = para_idx
                headings[heading_idx] = element.get_text(strip=True)
                continue

            raw_text = element.get_text(" ", strip=True) if hasattr(element, "get_text") else str(element).strip()
            if not raw_text:
                continue

            clean = self._clean_text(raw_text)
            if not clean:
                continue

            sentences = self._split_sentences(clean)
            if not sentences:
                continue

            title = headings.pop(heading_idx, None) if heading_idx == para_idx else None
            paragraphs.append(
                FilteredParagraph(
                    index=para_idx,
                    title=title,
                    sentences=sentences,
                )
            )
            para_idx += 1

        # If HTML parsing produced no paragraphs, fall back to plain-text splitting
        if not paragraphs:
            plain = soup.get_text("\n", strip=True)
            plain = self._clean_text(plain)
            if plain:
                return self._split_plain_text(plain)

        return paragraphs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clean_text(self, text: str) -> str:
        """Remove non-speakable artifacts from text."""
        s = text
        s = _URL_PATTERN.sub("", s)
        s = _HTML_ENTITY.sub("", s)
        s = _NON_SPEAKABLE.sub("", s)
        s = _MULTI_WHITESPACE.sub(" ", s)
        return s.strip()

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences, filtering short/empty ones."""
        parts = _SENTENCE_SPLIT.split(text)
        result: list[str] = []
        for part in parts:
            sentence = part.strip()
            if len(sentence) >= self._min_len:
                result.append(sentence)
        return result

    def _split_plain_text(self, text: str) -> list[FilteredParagraph]:
        """Fallback: split plain text by double newlines into paragraphs."""
        blocks = _MULTI_NEWLINES.split(text)
        paragraphs: list[FilteredParagraph] = []
        for idx, block in enumerate(blocks):
            block = block.strip()
            if not block:
                continue
            sentences = self._split_sentences(block)
            if sentences:
                paragraphs.append(FilteredParagraph(index=idx, sentences=sentences))
        return paragraphs
