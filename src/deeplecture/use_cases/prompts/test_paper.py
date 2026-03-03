"""Test paper generation prompts.

Stage 2 of the two-stage pipeline:
Takes extracted KnowledgeItems and generates open-ended exam-style questions.
"""

from __future__ import annotations


def build_test_paper_generation_prompts(
    knowledge_items_json: str,
    language: str,
    user_instruction: str = "",
) -> tuple[str, str]:
    """Build system and user prompts for test paper generation stage."""
    system_prompt = f"""You are an expert educator creating exam-style open-ended questions.

OUTPUT FORMAT (CRITICAL — READ FIRST):
Output ONLY a valid JSON array. No markdown fences, no commentary:
[
  {{
    "question_type": "short_answer",
    "stem": "Question text",
    "reference_answer": "Comprehensive reference answer",
    "scoring_criteria": ["Criterion 1", "Criterion 2"],
    "bloom_level": "analyze",
    "source_timestamp": 123.0,
    "source_category": "definition",
    "source_tags": ["tag1", "tag2"]
  }}
]

REQUIREMENTS:
- Generate mixed open-ended question types (for example: short_answer, essay, case_analysis, compare_contrast).
- Ensure at least 2 different question types overall.
- Ensure no single question type dominates more than 60%.
- Cover at least 3 Bloom levels across the output.
- Allowed bloom_level values: remember, understand, apply, analyze, evaluate, create.
- Prefer higher-order levels (analyze/evaluate/create) when content supports it.
- Target 5-15 questions based on content density.

FIELD RULES:
- "stem": clear, specific, exam-style question.
- "reference_answer": complete and directly answers the stem.
- "scoring_criteria": list of concrete, gradable points (at least 1 item).
- "question_type": short snake_case label chosen by you.
- "source_timestamp": best matching timestamp (seconds) if available, else null.
- "source_category": copy from source knowledge item category when possible.
- "source_tags": copy or derive relevant tags from source knowledge item.
- Output language: {language}

QUALITY:
- Avoid trivia-only questions.
- Prefer questions that require explanation, reasoning, comparison, or application.
- Keep each question focused on a single concept or tightly related concept group.
"""

    user_prompt = f"""Create exam-style open-ended questions from these knowledge items:

{knowledge_items_json}

{f"Additional instructions: {user_instruction}" if user_instruction else ""}

Return a JSON array of test paper question objects."""

    return system_prompt, user_prompt
