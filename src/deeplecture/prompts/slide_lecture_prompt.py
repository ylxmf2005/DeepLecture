"""
Prompt builder for PDF slide lecture generation.

Produces JSON transcripts with bilingual spoken explanations for TTS.
"""
from __future__ import annotations

from typing import Optional, Tuple


def build_slide_lecture_prompt(
    *,
    deck_id: str,
    page_index: int,
    total_pages: int,
    source_language: str,
    target_language: str,
    previous_transcript: Optional[str] = None,
    accumulated_summaries: Optional[str] = None,
    previous_transcripts_text: Optional[str] = None,
    neighbor_images: str = "none",
) -> Tuple[str, str]:
    """Build (user_prompt, system_prompt) for slide lecture generation."""

    # Image input description based on mode
    mode = (neighbor_images or "none").lower()
    if mode == "next":
        image_desc = "FIRST image = CURRENT page to explain. SECOND image (if present) = NEXT page for context only."
    elif mode == "prev_next":
        image_desc = "FIRST image = CURRENT page. Additional images may be NEXT/PREVIOUS pages for context."
    else:
        image_desc = "You receive ONE image: the CURRENT page to explain."

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
   - Convert code/paths to speech: `foo_bar()` → "the function foo bar"
   - Numbers as words when natural: "3.5" → "three point five"

2. NEVER REPEAT COVERED CONTENT
   - If previous transcript or summaries mention a topic, students already know it
   - For repeated topics: only add NEW insights, skip basics
   - For recap slides: be extremely brief ("This summarizes what we covered...")
   - For incremental slides (same layout + new elements): explain ONLY the delta

3. TEACHING STYLE
   - Conversational, warm, direct - like talking TO students
   - Focus on WHY and HOW, not just WHAT
   - Use guiding questions and emphasis
   - 5-15 short segments (1-3 sentences each)

4. LANGUAGE SEPARATION
   - "source" field: ONLY {source_language}
   - "target" field: ONLY {target_language}
   - Both must convey the same meaning
"""

    user_prompt = f"Page {page_index}/{total_pages}, deck \"{deck_id}\". Source: {source_language}, Target: {target_language}.\n"

    if previous_transcript:
        user_prompt += f"\n--- PREVIOUS PAGE TRANSCRIPT (already heard by students) ---\n{previous_transcript}\n---\n"

    if accumulated_summaries:
        user_prompt += f"\n--- TOPICS ALREADY COVERED (don't repeat) ---\n{accumulated_summaries}\n---\n"

    if previous_transcripts_text and not previous_transcript and not accumulated_summaries:
        user_prompt += f"\n--- CONTEXT ---\n{previous_transcripts_text}\n---\n"

    return user_prompt, system_prompt
