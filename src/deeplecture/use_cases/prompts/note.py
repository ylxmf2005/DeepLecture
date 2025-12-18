"""Prompts for AI note generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.note import NotePart


def build_note_outline_prompt(
    *,
    language: str,
    context_block: str,
    instruction: str = "",
    profile: str = "",
    max_parts: int | None = None,
) -> tuple[str, str]:
    """
    Build prompt for outline design step.

    Args:
        language: Target language for the note outline
        context_block: Lecture context text (transcript/slides)
        instruction: User-provided instruction for note generation
        profile: Learner profile describing background and goals
        max_parts: Optional maximum number of parts to generate

    Returns:
        (user_prompt, system_prompt)
    """
    system_prompt = (
        "You are an expert course note designer for university students.\n"
        f"- You write detailed, structured Markdown notes in {language}.\n"
        "- Start from prerequisites and intuition, then move to more advanced ideas.\n"
        "- You only design the NOTE OUTLINE in this step, not the full content.\n"
        "- The final notes may include LaTeX math, tables, code blocks, and rich examples.\n\n"
        "OUTLINE DESIGN PRINCIPLES:\n"
        "- Group by conceptual coherence, not just chronological order.\n"
        "- Earlier parts: prerequisites and foundational concepts.\n"
        "- Later parts: advanced ideas, applications, and synthesis.\n"
        "- Each part should be self-contained enough to study independently.\n\n"
        "Output rules:\n"
        "- Respond with a SINGLE JSON object.\n"
        "- Do NOT wrap JSON in markdown fences or add commentary.\n"
        '- The JSON object must have a top-level key "parts" which is a list.\n'
        '- Each item in "parts" must have keys: id, title, summary, focus_points.\n'
    )

    if profile:
        system_prompt += (
            "\nLearner profile (background and goals):\n"
            f"{profile}\n"
            "Design the outline so that this learner can follow step by step.\n"
        )

    parts_hint = ""
    if max_parts is not None:
        try:
            count = int(max_parts)
            if count > 0:
                parts_hint = f"Try to produce at most {count} parts.\n"
        except (TypeError, ValueError):
            parts_hint = ""

    user_prompt_lines = []
    user_prompt_lines.append(
        "You will see transcript and/or slide text for a lecture.\n"
        "Design a multi-part outline for high-quality study notes."
    )
    user_prompt_lines.append(
        "Constraints for the outline:\n"
        "- Use 5–12 parts for a typical lecture, fewer for short content.\n"
        "- Earlier parts should cover prerequisite ideas and basic concepts.\n"
        "- Later parts may go deeper, build on previous parts, or cover applications.\n"
        "- Each part should group closely related ideas that belong together.\n"
    )

    if parts_hint:
        user_prompt_lines.append(parts_hint)

    if instruction:
        user_prompt_lines.append(f"Extra user instruction for these notes (apply if reasonable):\n{instruction}\n")

    user_prompt_lines.append("Lecture context:\n" + context_block)

    user_prompt_lines.append(
        "Return ONLY JSON in this shape:\n"
        "{\n"
        '  "parts": [\n'
        "    {\n"
        '      "id": 1,\n'
        f'      "title": "short title in {language}",\n'
        '      "summary": "1–2 sentences describing what this part will teach",\n'
        '      "focus_points": ["concept A", "concept B", "concept C"]\n'
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}\n\n"
        "EXAMPLE (for a machine learning lecture):\n"
        "{\n"
        '  "parts": [\n'
        '    {"id": 1, "title": "What is Supervised Learning", "summary": "Introduces the core idea of learning from labeled examples", "focus_points": ["input-output pairs", "training vs inference", "classification vs regression"]},\n'
        '    {"id": 2, "title": "Linear Regression Basics", "summary": "The simplest model: fitting a line to data", "focus_points": ["hypothesis function", "parameters w and b", "prediction"]},\n'
        '    {"id": 3, "title": "Loss Function and Optimization", "summary": "How to measure and minimize prediction error", "focus_points": ["MSE loss", "gradient descent", "learning rate"]}\n'
        "  ]\n"
        "}\n"
    )

    user_prompt = "\n\n".join(user_prompt_lines)
    return user_prompt, system_prompt


def build_note_part_prompt(
    *,
    language: str,
    context_block: str,
    instruction: str = "",
    profile: str = "",
    part: NotePart,
) -> tuple[str, str]:
    """
    Build prompt for a single note part expansion.

    Args:
        language: Target language for the note content
        context_block: Lecture context text (transcript/slides)
        instruction: User-provided instruction for note generation
        profile: Learner profile describing background and goals
        part: Note part to expand

    Returns:
        (user_prompt, system_prompt)
    """
    pid = int(part.id or 0)
    title = part.title or f"Part {pid}"
    summary = part.summary or ""
    focus_points = [str(item).strip() for item in (part.focus_points or []) if str(item).strip()]

    system_lines = []
    system_lines.append(
        "You are a patient university teaching assistant writing lecture notes.\n"
        f"- Always write in {language}.\n"
        "- Assume the reader is a confused undergraduate; explain every idea clearly.\n"
        "- Use Markdown with headings, bullet points, and short paragraphs.\n"
        "- You may use LaTeX math ($...$ / $$...$$), tables, and code blocks when helpful.\n"
        "- Avoid talking about slides or the interface; just teach the concepts."
    )
    system_lines.append(
        "Formatting rules for each part of the note:\n"
        "- Start with a level-2 heading: '## Part {id}: {title}'.\n"
        "- Use consistent sub-headings like '### Intuition', '### Definitions / Key Ideas',\n"
        "  '### Examples', and '### Summary' when appropriate.\n"
        "- Build explanations from simple to advanced, and include concrete examples.\n"
    )

    if profile:
        system_lines.append(f"Learner profile:\n{profile}\nAdapt explanations and examples to this learner.\n")

    system_prompt = "\n\n".join(system_lines)

    user_lines = []
    user_lines.append(f"You are now writing PART {pid} of the notes for this lecture.")
    user_lines.append(f"Part title: {title}")

    if summary:
        user_lines.append(f"Part summary: {summary}")

    if focus_points:
        bullet = "\n".join(f"- {point}" for point in focus_points)
        user_lines.append("Focus points for this part:\n" + bullet)

    if instruction:
        user_lines.append(f"Global user instruction for this note (apply if meaningful):\n{instruction}\n")

    user_lines.append("Lecture context you can rely on (transcript and/or slide text):\n" + context_block)

    user_lines.append(
        "Write ONLY the Markdown content for this part, starting exactly with:\n"
        f"## Part {pid}: {title}\n\n"
        "Do not mention that this is part of an outline, and do not add any pre- or post-text\n"
        "outside the note content itself."
    )

    user_prompt = "\n\n".join(user_lines)
    return user_prompt, system_prompt
