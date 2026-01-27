"""Cheatsheet generation prompts.

Two-stage pipeline:
1. Extraction: Extract structured KnowledgeItems from content
2. Rendering: Convert KnowledgeItems to scannable Markdown cheatsheet
"""

from __future__ import annotations


def build_cheatsheet_extraction_prompts(
    context: str,
    language: str,
    subject_type: str = "auto",
    user_instruction: str = "",
) -> tuple[str, str]:
    """Build system and user prompts for knowledge extraction stage.

    Args:
        context: Source content (subtitles/slides text)
        language: Output language
        subject_type: "stem" | "humanities" | "auto"
        user_instruction: Additional user guidance

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    subject_hint = ""
    if subject_type == "stem":
        subject_hint = "Focus on formulas, algorithms, constants, and technical definitions."
    elif subject_type == "humanities":
        subject_hint = "Focus on key concepts, dates, names, and theoretical frameworks."

    system_prompt = f"""You are an expert knowledge extractor for exam preparation.
Your task is to extract high-value knowledge items from educational content.

Output language: {language}
{subject_hint}

IMPORTANT: Extract items that are:
- Hard to memorize (formulas, exact values, specific conditions)
- Easy to forget under pressure
- Frequently tested in exams

DO NOT extract:
- General explanations that are easy to derive
- Obvious definitions
- Lengthy narratives

Output ONLY valid JSON array with this structure:
[
  {{
    "category": "formula|definition|condition|algorithm|constant|example",
    "content": "The actual knowledge item content",
    "criticality": "high|medium|low",
    "tags": ["topic1", "topic2"]
  }}
]"""

    user_prompt = f"""Extract knowledge items from the following content:

{context}

{f"Additional instructions: {user_instruction}" if user_instruction else ""}

Return a JSON array of knowledge items. Focus on exam-critical information."""

    return system_prompt, user_prompt


def build_cheatsheet_rendering_prompts(
    knowledge_items_json: str,
    language: str,
    target_pages: int = 2,
    min_criticality: str = "medium",
) -> tuple[str, str]:
    """Build system and user prompts for cheatsheet rendering stage.

    Args:
        knowledge_items_json: JSON string of extracted KnowledgeItems
        language: Output language
        target_pages: Target length in pages (approximate)
        min_criticality: Minimum criticality to include ("high", "medium", "low")

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    criticality_filter = {
        "high": "only HIGH criticality items",
        "medium": "HIGH and MEDIUM criticality items",
        "low": "all items (HIGH, MEDIUM, LOW)",
    }.get(min_criticality, "HIGH and MEDIUM criticality items")

    system_prompt = f"""You are an expert at creating scannable exam cheatsheets.
Your task is to render knowledge items into a high-density, easy-to-scan format.

Output language: {language}
Target length: approximately {target_pages} page(s)
Include: {criticality_filter}

FORMAT GUIDELINES:
- Use tables for comparative information
- Use bullet points for conditions/rules
- Keep formulas in LaTeX ($...$) for clarity
- Group by topic/category
- Use bold for key terms
- Minimize prose, maximize information density

The output should be immediately usable during an open-book exam."""

    user_prompt = f"""Render the following knowledge items into a scannable Markdown cheatsheet:

{knowledge_items_json}

Create a well-organized, high-density cheatsheet that a student can quickly scan during an exam."""

    return system_prompt, user_prompt
