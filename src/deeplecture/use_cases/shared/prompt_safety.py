"""
Prompt Injection Protection.

Provides sanitization and detection for prompt injection attacks.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Common prompt injection patterns (case-insensitive)
INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Direct instruction override attempts
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", "instruction_override"),
    (r"disregard\s+(all\s+)?(previous|prior|above)", "instruction_override"),
    (r"forget\s+(everything|all)\s+(you|above)", "instruction_override"),
    # Role manipulation
    (r"you\s+are\s+now\s+(?:a|an|the)\s+\w+", "role_manipulation"),
    (r"pretend\s+(you\s+are|to\s+be)", "role_manipulation"),
    (r"act\s+as\s+(if|a|an|the)", "role_manipulation"),
    (r"roleplay\s+as", "role_manipulation"),
    # System prompt extraction
    (
        r"(reveal|show|tell|display|print|output)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions?)",
        "prompt_extraction",
    ),
    (r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?)", "prompt_extraction"),
    # Delimiter injection
    (r"```system", "delimiter_injection"),
    (r"\[system\]", "delimiter_injection"),
    (r"<\|im_start\|>", "delimiter_injection"),
    (r"<\|system\|>", "delimiter_injection"),
    # Output manipulation
    (r"respond\s+only\s+with", "output_manipulation"),
    (r"output\s+only", "output_manipulation"),
    (r"(do\s+not|don'?t)\s+(include|add|mention)", "output_manipulation"),
]

_COMPILED_PATTERNS: list[tuple[re.Pattern[str], str]] | None = None


def _get_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Get compiled injection patterns (lazy initialization)."""
    global _COMPILED_PATTERNS
    if _COMPILED_PATTERNS is None:
        _COMPILED_PATTERNS = [
            (re.compile(pattern, re.IGNORECASE), category) for pattern, category in INJECTION_PATTERNS
        ]
    return _COMPILED_PATTERNS


def detect_injection(text: str) -> tuple[bool, str | None]:
    """
    Detect potential prompt injection in text.

    Args:
        text: Text to analyze

    Returns:
        Tuple of (is_suspicious, category)
    """
    if not text:
        return False, None

    for pattern, category in _get_patterns():
        if pattern.search(text):
            logger.warning(
                "Potential prompt injection detected: category=%s, text_preview=%s",
                category,
                text[:100],
            )
            return True, category

    return False, None


def sanitize_user_input(
    text: str,
    *,
    max_length: int = 10000,
    strip_control_chars: bool = True,
    normalize_whitespace: bool = True,
) -> str:
    """
    Sanitize user input for safe inclusion in prompts.

    Args:
        text: Raw user input
        max_length: Maximum allowed length (truncate if exceeded)
        strip_control_chars: Remove control characters
        normalize_whitespace: Collapse multiple whitespace to single space

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    result = str(text)
    original_length = len(result)

    if len(result) > max_length:
        result = result[:max_length]
        logger.warning("User input truncated from %d to %d chars", original_length, max_length)

    if strip_control_chars:
        result = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", result)

    if normalize_whitespace:
        result = re.sub(r"[ \t]+", " ", result)
        result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def wrap_user_content(content: str, label: str = "USER_INPUT") -> str:
    """
    Wrap user content with clear delimiters to prevent confusion with instructions.

    Args:
        content: User-provided content
        label: Label for the content block

    Returns:
        Wrapped content with delimiters
    """
    if not content:
        return ""

    return f"<{label}>\n{content}\n</{label}>"


def create_safe_prompt_builder(
    *,
    max_input_length: int = 10000,
    detect_injections: bool = True,
    log_detections: bool = True,
) -> Callable[[str], str]:
    """
    Create a configured prompt sanitizer function.

    Args:
        max_input_length: Maximum input length
        detect_injections: Whether to scan for injection patterns
        log_detections: Whether to log detected injections

    Returns:
        Sanitizer function
    """

    def sanitizer(text: str) -> str:
        sanitized = sanitize_user_input(text, max_length=max_input_length)

        if detect_injections:
            is_suspicious, _category = detect_injection(sanitized)
            if is_suspicious and log_detections:
                pass  # Logged in detect_injection

        return sanitized

    return sanitizer


# Pre-configured sanitizers
sanitize_question = create_safe_prompt_builder(max_input_length=5000)
sanitize_learner_profile = create_safe_prompt_builder(max_input_length=2000)
sanitize_context = create_safe_prompt_builder(max_input_length=50000)


# Unicode whitespace characters that should be normalized to ASCII space
# LLMs sometimes emit these, breaking Markdown parsers (e.g., "###\u00A0Title")
_UNICODE_SPACES = re.compile(
    r"[\u00A0\u2000-\u200A\u202F\u205F\u3000]"
)

# LLM sometimes generates nested heading syntax like "#### ### Title" or "###### ### Title"
# This should be normalized to a single heading level
_NESTED_HEADINGS = re.compile(
    r"^(#{1,6})\s+(#{1,6})\s+",
    re.MULTILINE,
)


# LLM sometimes escapes markdown bold/italic markers: \*\*text\*\* -> **text**
_ESCAPED_BOLD = re.compile(r"\\\*\\\*(.+?)\\\*\\\*")
_ESCAPED_ITALIC = re.compile(r"\\\*(.+?)\\\*")

# LLM sometimes includes leading/trailing whitespace inside bold markers, breaking CommonMark parsing:
# "**text **" or "** text**" or "** text **" will often render as literal asterisks instead of <strong>.
_BOLD_INNER_TRIM = re.compile(r"\*\*([^\n]*?)\*\*")

# Avoid rewriting Markdown inside code spans/blocks where users may want to show raw syntax.
_FENCED_CODE_BLOCK = re.compile(r"```[\s\S]*?```", flags=re.DOTALL)
_INLINE_CODE_SPAN = re.compile(r"`[^`]*`")


def normalize_llm_markdown(text: str) -> str:
    """
    Normalize LLM-generated Markdown for proper rendering.

    Fixes:
    - Unicode whitespace characters (NBSP, em-space, etc.)
    - Nested heading syntax (e.g., "#### ### Title" -> "### Title")
    - Escaped bold/italic markers (e.g., "\\*\\*text\\*\\*" -> "**text**")

    Args:
        text: LLM-generated Markdown text

    Returns:
        Normalized Markdown text
    """
    if not text:
        return ""

    def _trim_bold_inner_ws(m: re.Match[str]) -> str:
        inner = m.group(1)
        trimmed = inner.strip(" \t")
        if not trimmed or trimmed == inner:
            return m.group(0)
        return f"**{trimmed}**"

    def _normalize_plain(segment: str) -> str:
        # Fix Unicode whitespace
        result = _UNICODE_SPACES.sub(" ", segment)

        # Fix nested headings: keep the inner (more specific) heading level
        # e.g., "#### ### Title" -> "### Title"
        result = _NESTED_HEADINGS.sub(r"\2 ", result)

        # Fix escaped bold/italic: \*\*text\*\* -> **text**, \*text\* -> *text*
        # Bold must be fixed before italic to avoid partial matches
        result = _ESCAPED_BOLD.sub(r"**\1**", result)
        result = _ESCAPED_ITALIC.sub(r"*\1*", result)

        # Fix whitespace inside bold markers: "** text **" -> "**text**"
        result = _BOLD_INNER_TRIM.sub(_trim_bold_inner_ws, result)
        return result

    def _apply_outside_code_spans(segment: str) -> str:
        parts: list[str] = []
        cursor = 0
        for m in _INLINE_CODE_SPAN.finditer(segment):
            parts.append(_normalize_plain(segment[cursor : m.start()]))
            parts.append(m.group(0))
            cursor = m.end()
        parts.append(_normalize_plain(segment[cursor:]))
        return "".join(parts)

    out: list[str] = []
    cursor = 0
    for m in _FENCED_CODE_BLOCK.finditer(text):
        out.append(_apply_outside_code_spans(text[cursor : m.start()]))
        out.append(m.group(0))
        cursor = m.end()
    out.append(_apply_outside_code_spans(text[cursor:]))
    return "".join(out)
