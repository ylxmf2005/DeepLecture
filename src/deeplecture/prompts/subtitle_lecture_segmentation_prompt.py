"""
Prompt builder for splitting a full lecture transcript into
pedagogical "knowledge units" based on subtitles.

Step 1 of the timeline generation pipeline uses this prompt: the LLM
sees the *entire* transcript (as timestamped subtitle segments) and
groups contiguous segments into a small set of important knowledge
points that are worth showing on the learning timeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from deeplecture.transcription.interactive import SubtitleSegment


def _format_segment_for_prompt(segment: "SubtitleSegment") -> str:
    """
    Render a single subtitle segment into a compact line for the prompt.
    """
    cleaned_text = segment.text.replace("\n", " ")
    return (
        f"[{segment.start:8.3f}s -> {segment.end:8.3f}s] "
        f"(#{segment.id}) {cleaned_text}"
    )


def build_lecture_segmentation_prompt(
    segments: List["SubtitleSegment"],
    *,
    language: str,
    learner_profile: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Build (user_prompt, system_prompt) for segmenting the whole lecture
    into knowledge units.

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
- Group *contiguous* segments into a small set of pedagogical \"knowledge units\".
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
  - \"start\": the time (in seconds) where that concept really begins,
  - \"end\": the time where that concept has essentially finished.
- \"start\" and \"end\" must be within [{global_start:.3f}, {global_end:.3f}] and should
  align with segment boundaries (use the start of the first and the end of the last
  segment that belong to the unit).

Output format rules (very important):
- Respond with a SINGLE JSON object.
- Do NOT wrap the JSON in backticks or any extra text.
- The top-level object must have a key \"knowledge_units\" whose value is a list.
- Each item in \"knowledge_units\" must have keys: id, title, start, end.
"""

    profile = (learner_profile or "").strip()
    if profile:
        system_prompt += (
            "\nLearner profile (background, goals, expectations):\n"
            f"{profile}\n"
            "Focus your units on concepts where this learner is likely to need extra help.\n"
        )

    formatted_segments = "\n".join(
        _format_segment_for_prompt(seg) for seg in segments
    )

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
