"""
Prompt builders for the ask/Q&A service.

Provides system and user prompts for:
- ask_video: Teaching assistant answering student questions
- summarize_context: Summarizing missed lecture content
"""

from typing import Optional

from deeplecture.prompts.explain_prompt import _get_explanation_language


def get_ask_video_prompt(
    learner_profile: Optional[str] = None,
) -> str:
    """
    Build system prompt for ask_video Q&A.

    Args:
        learner_profile: Optional free-form description of the learner.

    Returns:
        System prompt string.
    """
    try:
        language = _get_explanation_language()
    except Exception:
        language = "Simplified Chinese"

    system_prompt = f"""You are a patient teaching assistant helping a student learn from lecture content.

RESPONSE GUIDELINES:
- Answer in {language}
- Use provided context (subtitles, slides, timeline) as primary source
- Start with a direct answer, then elaborate with examples
- For math/code questions, show worked examples step by step

QUALITY STANDARDS:
- Be concise: match answer length to question complexity
- Be concrete: use specific examples from the lecture context
- Be helpful: if context is insufficient, supplement with your knowledge

AVOID:
- Generic textbook definitions when specific context is available
- Overly long responses for simple questions
- Repeating information the student already knows from their question"""

    if learner_profile and learner_profile.strip():
        system_prompt += f"""

LEARNER PROFILE:
{learner_profile.strip()}
Adapt explanations to this learner's background."""

    return system_prompt


def get_summarize_context_prompt(
    learner_profile: Optional[str] = None,
) -> str:
    """
    Build system prompt for summarizing missed lecture content.

    Args:
        learner_profile: Optional free-form description of the learner.

    Returns:
        System prompt string.
    """
    try:
        language = _get_explanation_language()
    except Exception:
        language = "Simplified Chinese"

    system_prompt = (
        "You are a helpful teaching assistant.\n"
        f"Please summarize the following lecture content in {language}.\n"
        "Focus on the key points and main ideas covered in this segment.\n"
        "Keep the summary concise but informative.\n"
    )

    if learner_profile and learner_profile.strip():
        system_prompt += f"\nLearner Profile: {learner_profile.strip()}\n"

    return system_prompt
