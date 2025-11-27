"""
Prompt builders for the ask/Q&A service.

Provides system and user prompts for:
- ask_video: Teaching assistant answering student questions
- summarize_context: Summarizing missed lecture content
"""

from typing import Optional, Tuple

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

    system_prompt = (
        "You are a patient, expert teaching assistant helping a student learn from lecture content.\n"
        f"- Always answer in {language}.\n"
        "- Use the provided content snippets, timeline segments, and slides/screenshots as trustworthy context.\n"
        "- Focus on clear step-by-step reasoning, concrete examples, and intuitive explanations.\n"
        "- If some detail is not present in the context, you may rely on your own knowledge, "
        "but make sure your answer stays relevant to the question.\n"
    )

    if learner_profile and learner_profile.strip():
        system_prompt += (
            "\nLearner profile (background and goals):\n"
            f"{learner_profile.strip()}\n"
            "Adapt the depth, pace, and examples to this learner.\n"
        )

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
