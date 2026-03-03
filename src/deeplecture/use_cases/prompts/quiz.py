"""Quiz generation prompts.

Single-stage pipeline that generates MCQs from structured KnowledgeItems.
Uses misconception-based distractor generation strategy.
"""

from __future__ import annotations


def build_quiz_generation_prompts(
    knowledge_items_json: str,
    language: str,
    question_count: int = 5,
    user_instruction: str = "",
) -> tuple[str, str]:
    """Build system and user prompts for quiz generation.

    Uses a balanced approach (~60-80 lines) with:
    - Output format at the top (critical for LLM attention)
    - Misconception-based distractor strategy
    - Category-specific hints (condensed)
    - No difficulty parameter (unreliable per research)

    Args:
        knowledge_items_json: JSON string of KnowledgeItems
        language: Output language
        question_count: Number of questions to generate
        user_instruction: Additional user guidance

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = f"""You are an expert educator creating quiz questions.

OUTPUT FORMAT (CRITICAL - READ FIRST):
Output ONLY a JSON array:
[
  {{
    "stem": "Question text",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer_index": 0,
    "explanation": "Why correct + why each distractor is wrong",
    "source_category": "formula|definition|condition|algorithm|constant|example",
    "source_tags": ["tag1", "tag2"]
  }}
]

REQUIREMENTS:
- Generate {question_count} questions
- Each question has EXACTLY 4 options
- answer_index is 0-based (0, 1, 2, or 3)
- Output language: {language}
- Preserve technical terms, formulas, and proper nouns in original language
- Coverage priority: cover ALL knowledge items before repeating a topic
- If question_count exceeds knowledge item count, generate extra questions from
  different angles (definition, application, contrast, error diagnosis)

DISTRACTOR GENERATION (CRITICAL):
Each distractor MUST target a DIFFERENT misconception type:
1. Computational errors - sign mistakes, operator confusion, boundary errors
2. Conceptual confusions - similar but distinct terms, cause-effect reversal
3. Partial understanding - missing key conditions, necessary vs sufficient
4. Over-generalization - applying rules beyond their valid scope

Rules:
- Distractors must be plausible but clearly wrong
- NO obviously absurd options
- Each distractor should represent a real student mistake

CATEGORY-SPECIFIC HINTS:
- formula: Test calculation, variable identification. Distractors: sign/operator errors
- definition: Test precise terminology. Distractors: related but distinct terms
- condition: Test when/triggers/exceptions. Distractors: necessary vs sufficient
- algorithm: Test step order, termination. Distractors: swapped steps, off-by-one
- constant: Test exact values, units. Distractors: magnitude errors, wrong units
- example: Test pattern recognition. Distractors: similar but incorrect scenarios

EXPLANATION FORMAT:
"[Correct answer explanation]. A/B/C/D is wrong because [specific misconception]."
"""

    user_prompt = f"""Generate {question_count} multiple-choice questions from these knowledge items:

{knowledge_items_json}

{f"Additional instructions: {user_instruction}" if user_instruction else ""}

Return ONLY the JSON array. Ensure each distractor represents a different type of misconception."""

    return system_prompt, user_prompt
