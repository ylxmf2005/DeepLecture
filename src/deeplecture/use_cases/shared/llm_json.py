"""
LLM JSON Parsing Utilities.

Thin wrapper around json_repair for LLM output parsing.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from json_repair import loads as repair_json_loads

logger = logging.getLogger(__name__)

T = TypeVar("T", dict, list)


def parse_llm_json(
    raw: str,
    *,
    default_type: type[T] = dict,
    context: str = "LLM output",
    allow_any_type: bool = False,
) -> T:
    """
    Parse JSON from LLM output using json_repair.

    json_repair handles:
    - Markdown code blocks (```json ... ```)
    - Missing quotes, commas, brackets
    - Malformed JSON structures
    - Non-Latin characters

    Args:
        raw: Raw LLM output string
        default_type: Expected return type (dict or list)
        context: Context string for logging
        allow_any_type: If True, return parsed result even if type doesn't match

    Returns:
        Parsed JSON as dict or list, or empty default on failure
    """
    if not raw or not raw.strip():
        return default_type()

    try:
        result = repair_json_loads(raw)

        if (
            (default_type is dict and isinstance(result, dict))
            or (default_type is list and isinstance(result, list))
            or isinstance(result, default_type)
        ):
            return result

        if allow_any_type and isinstance(result, dict | list):
            logger.info(
                "JSON type mismatch in %s: expected %s, got %s (allowed)",
                context,
                default_type.__name__,
                type(result).__name__,
            )
            return result  # type: ignore[return-value]

        logger.warning(
            "Unexpected JSON type in %s: expected %s, got %s",
            context,
            default_type.__name__,
            type(result).__name__,
        )
        return default_type()

    except Exception as e:
        logger.warning(
            "Failed to parse JSON from %s: %s (preview: %.100s)",
            context,
            e,
            raw,
        )
        return default_type()
