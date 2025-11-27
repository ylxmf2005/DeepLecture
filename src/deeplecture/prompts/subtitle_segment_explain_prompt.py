"""
Prompt builder for generating segment‑level explanations from subtitles.

The LLM receives a small window of the transcript (with timestamps)
and decides whether learners need an additional explanation panel for
this window. If yes, it returns structured JSON describing the panel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from deeplecture.transcription.interactive import SubtitleSegment


def _format_segment_for_prompt(segment: "SubtitleSegment") -> str:
    """
    Render a single subtitle segment into a compact line for the prompt.
    """
    # Avoid backslashes inside f-string expression parts (Python restriction).
    cleaned_text = segment.text.replace("\n", " ")
    return (
        f"[{segment.start:8.3f}s -> {segment.end:8.3f}s] "
        f"(#{segment.id}) {cleaned_text}"
    )


def build_segment_explanation_prompt(
    segments: List["SubtitleSegment"],
    *,
    language: str,
    chunk_start: float,
    chunk_end: float,
    learner_profile: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Build (user_prompt, system_prompt) for a single subtitle chunk.

    The LLM must decide whether to create an explanation and, if so,
    return only JSON with this shape:

    {
      "should_explain": true | false,
      "title": "short title",
      "trigger_time": 123.45,
      "markdown": "explanation in Markdown"
    }
    """
    # System prompt focuses on pedagogy and strict JSON output.
    system_prompt = f"""You are an expert teaching assistant helping students follow a recorded lecture.
You receive a short continuous slice of the transcript, with precise timestamps in seconds.

Your job for each slice:
- Decide whether students would benefit from ONE short extra explanation panel.
- Only create an explanation when the slice introduces an important new concept,
  formula, definition, algorithm, or subtle point that is likely to confuse learners.
- If the slice is simple, repetitive, or purely organizational, you must respond with
  "should_explain": false.

When you decide to explain, follow these guidelines:
- Explain in {language}.
- Use clear Markdown with headings, bullet points, and short paragraphs.
- When you write formulas, you may use LaTeX-style math inside the Markdown, with $...$ for inline math and $$...$$ for block equations.
- Focus strictly on the content in this slice (do not assume future context).
- Be concise but concrete: include intuition, simple examples, or contrasts to related ideas.

Output format rules (very important):
- Respond with a single JSON object.
- Do NOT wrap the JSON in backticks or any other text.
- JSON keys must be: should_explain, title, trigger_time, markdown.
- trigger_time is a float in seconds between {chunk_start:.3f} and {chunk_end:.3f}
  and should point to the moment in the slice where the explanation becomes relevant.
"""

    profile = (learner_profile or "").strip()
    if profile:
        system_prompt += (
            "\nLearner profile (background, goals, expectations):\n"
            f"{profile}\n"
            "Only propose an explanation when this learner is likely to need extra help.\n"
        )

    formatted_segments = "\n".join(
        _format_segment_for_prompt(seg) for seg in segments
    )

    user_prompt = f"""Here is a continuous slice of the lecture transcript with timestamps:

{formatted_segments}

Decide whether to create ONE explanation panel for this slice.

If you decide that NO explanation is needed, answer:
{{"should_explain": false}}

If you decide that an explanation IS needed, answer:
{{
  "should_explain": true,
  "title": "a short, student-friendly title in {language}",
  "trigger_time": <float seconds between {chunk_start:.3f} and {chunk_end:.3f}>,
  "markdown": "the explanation in Markdown"
}}
"""

    return user_prompt, system_prompt
