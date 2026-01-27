"""JSON parsing utilities for LLM responses.

Handles common issues with LLM-generated JSON:
- Markdown code fences (```json ... ```)
- Minor syntax errors
- Whitespace issues
"""

from __future__ import annotations

import re
from typing import Any

import json_repair


def parse_llm_json(raw: str, context: str = "LLM response") -> dict | list | Any:
    """
    Parse JSON from LLM response, handling common issues.

    Args:
        raw: Raw LLM response text.
        context: Description of what the JSON represents (for error messages).

    Returns:
        Parsed JSON data (usually dict or list).

    Raises:
        ValueError: If JSON cannot be parsed.
    """
    raw_clean = (raw or "").strip()

    # Remove markdown code fences if present
    if raw_clean.startswith("```"):
        match = re.match(
            r"^```(?:json)?\s*(.*?)\s*```$", raw_clean, re.DOTALL | re.IGNORECASE
        )
        if match:
            raw_clean = match.group(1).strip()

    if not raw_clean:
        raise ValueError(f"Empty {context} JSON response")

    try:
        return json_repair.loads(raw_clean)
    except Exception as e:
        raise ValueError(f"Failed to parse {context} JSON: {e}") from e
