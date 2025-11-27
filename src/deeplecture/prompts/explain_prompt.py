"""
Prompt builder for slide explanation with an image frame.

The output language is controlled via configuration:

    subtitle.timeline.output_language

For example:
    subtitle:
      timeline:
        output_language: "Simplified Chinese"

This same setting is also used by the subtitle‑based interactive
timeline so that all “AI notes” are in a consistent language.

As of the screenshot‑and‑ASK features, the explainer can also receive
surrounding subtitle context (e.g. ±30 seconds of the original
transcript) so that explanations are grounded both in the visual slide
and the spoken narration.
"""

from typing import Optional, Tuple

from deeplecture.config.config import load_config


def _get_explanation_language() -> str:
    """
    Resolve the language code / name used for AI explanations.

    We reuse subtitle.timeline.output_language as a single knob
    for all note‑like features. Defaults to "Simplified Chinese" if missing.
    """
    config = load_config()
    subtitle_cfg = (config or {}).get("subtitle") or {}
    timeline_cfg = subtitle_cfg.get("timeline") or {}
    language = timeline_cfg.get("output_language", "Simplified Chinese")
    # Always return a string
    return str(language)


def get_explain_prompt(
    user_instruction: Optional[str] = None,
    learner_profile: Optional[str] = None,
    subtitle_context: Optional[str] = None,
    subtitle_window_seconds: Optional[float] = None,
) -> Tuple[str, str]:
    """
    Build system and user prompts for explaining a slide/frame.

    Args:
        user_instruction: Optional instruction from the client. If None,
            a default instruction is generated based on configuration.
        learner_profile: Optional free‑form description of the learner.
        subtitle_context: Optional snippet of the original‑language
            transcript (typically ±N seconds around the frame).
        subtitle_window_seconds: Approximate half‑window (seconds) used
            when collecting ``subtitle_context``. Used only for wording.

    Returns:
        Tuple of (user_prompt, system_prompt).
    """
    language = _get_explanation_language()

    system_prompt = f"""You are a patient teaching assistant who explains lecture slides for students.

Your goals:
- Help the student truly understand the topic, not just translate the words.
- Teach in {language}.
- Start from basic intuition and gradually move to more advanced details.
- Use clear Markdown with headings and bullet points so the notes are easy to review.
- When you write formulas, you may use LaTeX-style math inside the Markdown, with $...$ for inline math and $$...$$ for block equations.

Teaching style:
- Carefully unpack every concept that appears on the slide.
- When helpful, bring in your own knowledge: intuitive explanations, analogies, real‑world scenarios,
  short tables, code snippets, or step‑by‑step calculations.
- Prefer short, focused sections over long, dense paragraphs.
- Stay focused on the subject matter; do not talk about being an AI or about the interface."""

    if subtitle_context:
        # Nudge the model to jointly use the visual frame and the
        # transcript context instead of treating them as unrelated.
        window_desc = ""
        try:
            if subtitle_window_seconds and float(subtitle_window_seconds) > 0:
                window_desc = f" (roughly ±{float(subtitle_window_seconds):.0f} seconds around this frame)"
        except (TypeError, ValueError):
            window_desc = ""

        system_prompt += f"""

You can also use a short snippet of the original‑language transcript{window_desc}
around this frame. Combine what you see on the slide with what is said in the
transcript to produce a coherent, well‑grounded explanation."""

    profile = (learner_profile or "").strip()
    if profile:
        system_prompt += f"""

Learner profile:
{profile}

Adapt the depth, pace, and choice of examples to this learner."""

    if not user_instruction:
        user_instruction = f"""Explain the content of this lecture slide so that a student can really learn the topic.

Work in {language}.

1. Give a very brief overview of what the slide is about.
2. Then go through the slide from top to bottom, covering every part (titles, bullets, formulas, diagrams, and examples).
3. When there are examples (on the slide or natural ones you can create), walk through them step by step.
4. Add a short recap section at the end with the key takeaways."""

    if subtitle_context:
        # Append transcript context to the end of the user prompt so
        # that the model can read it alongside the image.
        user_instruction = (
            f"{user_instruction}\n\n"
            "Here is nearby transcript text from the original‑language subtitles. "
            "Use it together with the slide image when you explain, but do not just translate it verbatim:\n\n"
            f"{subtitle_context}"
        )

    user_prompt = user_instruction

    return user_prompt, system_prompt
