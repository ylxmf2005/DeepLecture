"""Timeline generation prompts (business rules)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.timeline import SubtitleSegment


def _format_segment_for_prompt(segment: SubtitleSegment) -> str:
    """
    Render a single subtitle segment into a compact line for the prompt.

    Args:
        segment: SubtitleSegment to format.

    Returns:
        Formatted string with timestamp and text.
    """
    cleaned_text = segment.text.replace("\n", " ")
    return f"[{segment.start:8.3f}s -> {segment.end:8.3f}s] (#{segment.id}) {cleaned_text}"


def build_lecture_segmentation_prompt(
    segments: list[SubtitleSegment],
    *,
    language: str,
    learner_profile: str | None = None,
) -> tuple[str, str]:
    """
    Build (user_prompt, system_prompt) for segmenting the whole lecture
    into knowledge units.

    Args:
        segments: List of SubtitleSegment objects with timestamps and text.
        language: Target language for knowledge unit titles.
        learner_profile: Optional learner background and goals description.

    Returns:
        Tuple of (user_prompt, system_prompt) for lecture segmentation.

    Raises:
        ValueError: If segments list is empty.

    Notes:
        The model receives the full transcript (all subtitle segments with
        timestamps) and must return JSON of the form:

            {
              "knowledge_units": [
                {
                  "id": 1,
                  "title": "short title (in {language})",
                  "start": 123.45,
                  "end": 234.56
                },
                ...
              ]
            }

        Each knowledge unit:
        - must cover a contiguous time range;
        - must not overlap with others;
        - should correspond to ONE coherent concept, example, derivation,
          or short cluster of tightly related ideas;
        - should only be created when an extra explanation panel on the
          timeline would meaningfully help the learner.
    """
    if not segments:
        raise ValueError("build_lecture_segmentation_prompt requires at least one segment")

    global_start = segments[0].start
    global_end = segments[-1].end

    system_prompt = f"""You are an expert course designer helping learners navigate a recorded lecture.
You receive the FULL transcript of the lecture, split into many short subtitle segments
with precise timestamps (seconds).

Your task:
- Group *contiguous* segments into a small set of pedagogical "knowledge units".
- Each knowledge unit should correspond to one main concept, algorithm, example,
  definition, or subtle idea that deserves its own explanation panel on a timeline.
- Do NOT create units for trivial remarks, small repetitions, or purely logistical talk.
- Avoid splitting a single concept across multiple units. If a concept spans several
  neighbouring segments, keep them in ONE unit.

Constraints:
- Units must cover contiguous time ranges with no overlaps.
- Use at most about 25–30 units for the entire lecture, even if it is long.
- Choose a short, student-friendly title for each unit written in {language}.
- For each unit, choose:
  - "start": the time (in seconds) where that concept really begins,
  - "end": the time where that concept has essentially finished.
- "start" and "end" must be within [{global_start:.3f}, {global_end:.3f}] and should
  align with segment boundaries (use the start of the first and the end of the last
  segment that belong to the unit).

Output format rules (very important):
- Respond with a SINGLE JSON object.
- Do NOT wrap the JSON in backticks or any extra text.
- The top-level object must have a key "knowledge_units" whose value is a list.
- Each item in "knowledge_units" must have keys: id, title, start, end.
"""

    profile = (learner_profile or "").strip()
    if profile:
        system_prompt += (
            "\nLearner profile (background, goals, expectations):\n"
            f"{profile}\n"
            "Focus your units on concepts where this learner is likely to need extra help.\n"
        )

    formatted_segments = "\n".join(_format_segment_for_prompt(seg) for seg in segments)

    user_prompt = f"""Here is the full lecture transcript, split into subtitle segments:

{formatted_segments}

Now group these segments into a small set of important knowledge units.

Return ONLY JSON in the following shape:
{{
  "knowledge_units": [
    {{
      "id": 1,
      "title": "short, student-friendly title in {language}",
      "start": <float seconds>,
      "end": <float seconds>
    }},
    ...
  ]
}}
"""

    return user_prompt, system_prompt


def build_segment_explanation_prompt(
    segments: list[SubtitleSegment],
    *,
    language: str,
    chunk_start: float,
    chunk_end: float,
    learner_profile: str | None = None,
) -> tuple[str, str]:
    """
    Build (user_prompt, system_prompt) for a single subtitle chunk.

    Args:
        segments: List of SubtitleSegment objects in the chunk.
        language: Target language for the explanation.
        chunk_start: Start time (seconds) of the chunk.
        chunk_end: End time (seconds) of the chunk.
        learner_profile: Optional learner background and goals description.

    Returns:
        Tuple of (user_prompt, system_prompt) for segment explanation.

    Notes:
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
- If the slice is simple, repetitive, or purely organizational, respond with
  "should_explain": false.

DECISION GUIDE:
- YES explain: new technical term, non-obvious insight, complex formula, algorithm step
- NO explain: transitions, repetitions, greetings, simple statements, organizational remarks

When you decide to explain:
- Explain in {language}.
- Use clear Markdown with headings, bullet points, and short paragraphs.
- Use LaTeX math ($...$ inline, $$...$$ block) when needed.
- Be concise: 100-300 words is ideal.
- Focus strictly on the content in this slice.
- When referencing other timestamps, use bracket format: [MM:SS] or [HH:MM:SS].

Output format rules:
- Respond with a single JSON object (no backticks).
- Keys: should_explain, title, trigger_time, markdown.
- trigger_time: float in seconds between {chunk_start:.3f} and {chunk_end:.3f}."""

    profile = (learner_profile or "").strip()
    if profile:
        system_prompt += (
            "\nLearner profile (background, goals, expectations):\n"
            f"{profile}\n"
            "Only propose an explanation when this learner is likely to need extra help.\n"
        )

    formatted_segments = "\n".join(_format_segment_for_prompt(seg) for seg in segments)

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
