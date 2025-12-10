"""
Prompts for the combined Enhance and Translate workflow.
"""

from typing import Any, Dict, List, Tuple

from deeplecture.transcription.interactive import SubtitleSegment


def build_background_prompt(transcript_text: str) -> Tuple[str, str]:
    """
    Build prompt to extract background context/topics from the transcript.
    """
    system_prompt = (
        "You are an expert content analyzer. Your task is to analyze a video transcript "
        "and extract the core background context, key entities, and terminology.\n"
        "Output must be valid JSON."
    )

    user_prompt = (
        "Analyze the following transcript and provide a background summary.\n"
        "Return a JSON object with this structure:\n"
        "{\n"
        '  "topic": "Main topic of the video",\n'
        '  "summary": "Brief summary of the content",\n'
        '  "keywords": ["list", "of", "key", "terms", "and", "entities"],\n'
        '  "tone": "formal/casual/technical/etc"\n'
        "}\n\n"
        f"Transcript:\n{transcript_text}"
    )

    return user_prompt, system_prompt


def build_enhance_and_translate_prompt(
    background: Dict[str, Any],
    segments: List[SubtitleSegment],
    target_language: str = "zh",
) -> Tuple[str, str]:
    """
    Build prompt to enhance (fix ASR errors, merge segments) and translate subtitles.
    """
    background_str = (
        f"Topic: {background.get('topic', 'Unknown')}\n"
        f"Keywords: {', '.join(background.get('keywords', []))}\n"
        f"Tone: {background.get('tone', 'Neutral')}"
    )

    # Convert segments to a numbered list for the LLM
    transcript_lines = []
    for i, seg in enumerate(segments):
        transcript_lines.append(f"[{i+1}] {seg.text.strip()}")
    transcript_text = "\n".join(transcript_lines)

    system_prompt = (
        f"You are a subtitle editor and translator ({target_language}). "
        "Process raw ASR subtitles into bilingual subtitles.\n\n"
        "Tasks:\n"
        "1. Fix ASR errors (typos, punctuation, capitalization)\n"
        "2. Merge short fragments into coherent sentences (2-4 segments max)\n"
        "3. Translate to {target_language}\n\n"
        "Output JSON:\n"
        '{{"subtitles": [{{"start_index": 1, "end_index": 2, "text_en": "...", "text_zh": "..."}}]}}\n\n'
        "Rules:\n"
        "- Indices are 1-based\n"
        "- Timeline must be contiguous: each start_index = previous end_index + 1\n"
        "- No overlapping: each input segment belongs to exactly one output entry\n"
        "- Keep text under 80 chars; if too long, merge fewer segments instead\n"
        "- Cover all input segments"
    )

    user_prompt = (
        f"Context:\n{background_str}\n\n"
        f"Target Language: {target_language}\n\n"
        "Input Subtitles:\n"
        f"{transcript_text}\n\n"
        "Process these subtitles and return the JSON output."
    )

    return user_prompt, system_prompt
