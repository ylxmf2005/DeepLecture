"""
Ask use case prompts - Business rules for Q&A interactions.

These prompts encode the business logic for:
- Teaching assistant behavior
- Context summarization
- Answer quality standards
"""

from __future__ import annotations


def get_ask_video_prompt(learner_profile: str = "", language: str = "Simplified Chinese") -> str:
    """
    Build system prompt for Q&A teaching assistant.

    Args:
        learner_profile: Optional learner background/profile
        language: Response language

    Returns:
        System prompt string
    """
    system_prompt = f"""You are a patient teaching assistant helping a student learn from lecture content.

RESPONSE GUIDELINES:
- Answer in {language}
- Use provided context (subtitles, slides, timeline) as primary source
- Start with a direct answer, then elaborate with examples
- For math/code questions, show worked examples step by step
- When referencing video timestamps, use bracket format: [MM:SS] or [HH:MM:SS]
  Example: "This concept is explained at [5:30]" or "See the derivation at [01:23:45]"

QUALITY STANDARDS:
- Be concise: match answer length to question complexity
- Be concrete: use specific examples from the lecture context
- Be helpful: if context is insufficient, supplement with your knowledge

AVOID:
- Generic textbook definitions when specific context is available
- Overly long responses for simple questions
- Repeating information the student already knows from their question"""

    if learner_profile.strip():
        system_prompt += f"""

LEARNER PROFILE:
{learner_profile.strip()}
Adapt explanations to this learner's background."""

    return system_prompt


def get_summarize_context_prompt(learner_profile: str = "", language: str = "Simplified Chinese") -> str:
    """
    Build system prompt for context summarization.

    Args:
        learner_profile: Optional learner background/profile
        language: Response language

    Returns:
        System prompt string
    """
    system_prompt = (
        "You are a helpful teaching assistant.\n"
        f"Please summarize the following lecture content in {language}.\n"
        "Focus on the key points and main ideas covered in this segment.\n"
        "Keep the summary concise but informative.\n"
    )

    if learner_profile.strip():
        system_prompt += f"\nLearner Profile: {learner_profile.strip()}\n"

    return system_prompt


def build_ask_video_user_prompt(
    *,
    context_block: str,
    history_block: str,
    question: str,
) -> str:
    """
    Build user prompt for Q&A.

    Args:
        context_block: Formatted context (timeline, subtitles, screenshots)
        history_block: Formatted conversation history
        question: User's question

    Returns:
        User prompt string
    """
    parts: list[str] = []

    if context_block:
        parts.append(f"Here are context snippets from the lecture timeline, content, and slides:\n{context_block}")

    if history_block:
        parts.append(f"Here is the recent conversation between you (Tutor) and the student:\n{history_block}")

    parts.append(
        "Now answer the student's current question based on the lecture content and the conversation above.\n"
        f"Student's question:\n{question}"
    )

    return "\n\n".join(parts)


def build_summarize_context_user_prompt(context_block: str) -> str:
    """
    Build user prompt for context summarization.

    Args:
        context_block: Formatted context to summarize

    Returns:
        User prompt string
    """
    return (
        "Here is the transcript of the content I missed:\n"
        f"{context_block}\n\n"
        "Please provide a summary of what was discussed."
    )


def get_response_language(language: str | None = None) -> str:
    """
    Get response language.

    Args:
        language: Explicit language override. If not provided, defaults to
                  "Simplified Chinese".

    Returns:
        Language string
    """
    if language and language.strip():
        return language.strip()
    return "Simplified Chinese"
