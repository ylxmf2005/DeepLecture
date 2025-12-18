"""Slide lecture generation prompts (business rules)."""

from __future__ import annotations


def build_slide_lecture_prompt(
    *,
    deck_id: str,
    page_index: int,
    total_pages: int,
    source_language: str,
    target_language: str,
    neighbor_images: str,
    previous_transcript: str,
    accumulated_summaries: str,
) -> tuple[str, str]:
    """
    Build (user_prompt, system_prompt) for generating a narrated lecture for one slide.

    Args:
        deck_id: Identifier for the slide deck.
        page_index: Current page number (1-based).
        total_pages: Total number of pages in the deck.
        source_language: Language of the source content.
        target_language: Language for translation.
        neighbor_images: Image context mode ("next", "prev_next", or "none").
        previous_transcript: Transcript from the previous page.
        accumulated_summaries: Summaries of topics already covered.

    Returns:
        Tuple of (user_prompt, system_prompt) for slide lecture generation.
    """
    mode = (neighbor_images or "none").strip().lower()
    image_desc = {
        "next": "FIRST image = CURRENT page to explain. SECOND image (if present) = NEXT page for context only.",
        "prev_next": "FIRST image = CURRENT page. SECOND image (if present) = NEXT page. Previous context provided via transcript text.",
    }.get(mode, "You receive ONE image: the CURRENT page to explain.")

    system_prompt = f"""You are a university professor giving a live lecture. TEACH concepts, don't describe slides.

{image_desc}

OUTPUT FORMAT (strict JSON, no markdown/comments):
{{
  "deck_id": "{deck_id}",
  "page_index": {page_index},
  "source_language": "{source_language}",
  "target_language": "{target_language}",
  "one_sentence_summary": "<one sentence summarizing this page in {source_language}>",
  "segments": [
    {{"id": 1, "source": "<{source_language} explanation>", "target": "<{target_language} translation>"}}
  ]
}}

CRITICAL RULES:

1. TTS-READY TEXT ONLY
   - Plain spoken language, no formatting (no markdown, LaTeX, bullets, symbols)
   - Convert code/paths to speech: `foo_bar()` → \"the function foo bar\"
   - Numbers as words when natural: \"3.5\" → \"three point five\"

2. NEVER REPEAT COVERED CONTENT
   - If previous transcript or summaries mention a topic, students already know it
   - For repeated topics: only add NEW insights, skip basics
   - For recap slides: be extremely brief (\"This summarizes what we covered...\")
   - For incremental slides (same layout + new elements): explain ONLY the delta

3. TEACHING STYLE
   - Conversational, warm, direct - like talking TO students
   - Focus on WHY and HOW, not just WHAT
   - Use guiding questions and emphasis
   - 5-15 short segments (1-3 sentences each)

4. LANGUAGE SEPARATION
   - \"source\" field: ONLY {source_language}
   - \"target\" field: ONLY {target_language}
   - Both must convey the same meaning
"""

    user_prompt = (
        f'Page {page_index}/{total_pages}, deck "{deck_id}". Source: {source_language}, Target: {target_language}.\n'
    )

    if previous_transcript:
        user_prompt += f"\n--- PREVIOUS PAGE TRANSCRIPT (already heard by students) ---\n{previous_transcript}\n---\n"

    if accumulated_summaries:
        user_prompt += f"\n--- TOPICS ALREADY COVERED (don't repeat) ---\n{accumulated_summaries}\n---\n"

    return user_prompt, system_prompt
