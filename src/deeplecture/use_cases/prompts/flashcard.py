"""Flashcard generation prompts.

Stage 2 of the two-stage pipeline:
Takes extracted KnowledgeItems and generates flashcard pairs (front/back).
"""

from __future__ import annotations


def build_flashcard_generation_prompts(
    knowledge_items_json: str,
    language: str,
    user_instruction: str = "",
) -> tuple[str, str]:
    """Build system and user prompts for flashcard generation stage.

    Unlike quiz_generation, there is no fixed count parameter — the model
    decides card count from content density with a coverage-first strategy.

    Args:
        knowledge_items_json: JSON string of extracted KnowledgeItems
        language: Output language
        user_instruction: Additional user guidance

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = f"""You are an expert educator creating flashcards for active recall study.

OUTPUT FORMAT (CRITICAL — READ FIRST):
Output ONLY a valid JSON array. No markdown fences, no commentary:
[
  {{
    "front": "Question or term (concise, clear)",
    "back": "Answer or explanation (thorough but focused)",
    "source_timestamp": 123.0,
    "source_category": "definition"
  }}
]

RULES:
- Coverage first: ensure EVERY knowledge item appears in at least one flashcard.
- Generate more than one card for complex/high-value items (2-3 cards when useful).
- Target roughly 1.5x-2x flashcards relative to the number of knowledge items.
- "front": a concise question, term, or prompt that triggers recall.
- "back": a clear, complete answer — 2-4 sentences.
- "source_timestamp": copy directly from the knowledge item's "source_start" field.
  If "source_start" is absent or null, set to null.
- "source_category": copy directly from the knowledge item's "category" field.
- Output language: {language}

CARD QUALITY GUIDELINES:
- Front: prefer questions ("What is…?"), fill-in-the-blank, or single terms.
- Back: include the key answer plus brief context or an example.
- Avoid yes/no questions — favour open recall.
- Each card should test ONE concept.
- Do NOT create near-duplicate cards that test exactly the same recall target."""

    user_prompt = f"""Create flashcards from these knowledge items:

{knowledge_items_json}

{f"Additional instructions: {user_instruction}" if user_instruction else ""}

Return a JSON array of flashcard objects."""

    return system_prompt, user_prompt
