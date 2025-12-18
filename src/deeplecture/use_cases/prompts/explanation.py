"""
Explanation use case prompts - Business rules for slide/frame explanation.

These prompts encode the business logic for:
- Teaching assistant behavior for visual content
- Subtitle context integration
- Learner profile adaptation
"""

from __future__ import annotations


def build_explain_system_prompt(learner_profile: str = "", output_language: str = "") -> str:
    """
    Build system prompt for slide/frame explanation.

    Args:
        learner_profile: Optional learner background/profile
        output_language: Target language for the explanation output

    Returns:
        System prompt string
    """
    prompt = """You are a helpful teaching assistant explaining lecture content.

GUIDELINES:
- Explain what is being discussed at this point in the lecture
- Use the provided subtitle context to understand the topic
- Be concise but thorough

FOCUS ON:
- Key concepts being presented
- How this fits into the broader topic
- Any important details or examples mentioned

TIMESTAMP REFERENCES:
- When referencing other parts of the video, use bracket format: [MM:SS] or [HH:MM:SS]
- Example: "This builds on the concept introduced at [3:45]" """

    if output_language.strip():
        prompt += f"""

OUTPUT LANGUAGE:
You MUST write your explanation in {output_language.strip()}."""
    else:
        prompt += """

OUTPUT LANGUAGE:
Answer in the same language as the subtitle content."""

    if learner_profile.strip():
        prompt += f"""

LEARNER PROFILE:
{learner_profile.strip()}
Adapt your explanation to this learner's background."""

    return prompt


def build_explain_user_prompt(timestamp: float, subtitle_context: str = "") -> str:
    """
    Build user prompt for slide/frame explanation.

    Args:
        timestamp: Video timestamp in seconds
        subtitle_context: Surrounding subtitle text

    Returns:
        User prompt string
    """
    parts = [f"Timestamp: {timestamp:.1f} seconds"]

    if subtitle_context:
        parts.append(f"Subtitle context:\n{subtitle_context}")

    parts.append("Please explain what is being discussed at this point in the lecture.")

    return "\n\n".join(parts)
