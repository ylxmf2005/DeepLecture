"""
Prompt builder for generating very short per-page slide summaries.

This is used in a first, lightweight pass so that we can:
- summarise every page in parallel; and
- later provide a small window of nearby page summaries as context when
  generating the full spoken transcript for each page.
"""

from __future__ import annotations

from typing import Tuple


def build_slide_summary_prompt(
    *,
    deck_id: str,
    page_index: int,
    total_pages: int,
    language: str,
) -> Tuple[str, str]:
    """
    Build (user_prompt, system_prompt) for generating a ONE‑sentence summary
    of a single slide page.

    The model must output exactly one short sentence in the specified language,
    with no quotes or formatting, describing what this page mainly explains.
    """

    system_prompt = f"""You are helping to organise a university course slide deck.

Your task is to look at ONE slide page image and write a single short
sentence that summarises what this page mainly explains.

OUTPUT FORMAT:
- Output exactly ONE sentence.
- The sentence must be in {language} only.
- Do NOT include quotes, bullet points, numbering, Markdown, HTML, or LaTeX.
- Do NOT add any extra comments before or after the sentence.

CONTENT GUIDELINES:
- Focus on the main idea or topic of this page, not every detail.
- Use plain, spoken-style language that could be read aloud.
- If the page contains mostly a title, summarise what the title suggests
  the page is about.
- If the page is mostly images or diagrams, describe in words what they
  are trying to show.
"""

    user_prompt = (
        f"This is page {page_index} out of {total_pages} pages in the slide deck "
        f"with ID \"{deck_id}\".\n"
        f"Look at this page and write ONE short sentence in {language} "
        "that describes what this page is mainly about."
    )

    return user_prompt, system_prompt
