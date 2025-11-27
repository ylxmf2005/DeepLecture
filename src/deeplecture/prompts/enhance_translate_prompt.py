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
        f"You are a professional subtitle editor and translator specialized in {target_language}. "
        "Your task is to process raw ASR subtitles to create high-quality bilingual subtitles.\n"
        "Follow these steps:\n"
        "1. **Enhance**: Fix ASR errors (typos, punctuation, capitalization) using the provided background context.\n"
        "2. **Merge**: Combine short, fragmented segments into coherent sentences or phrases. "
        "   - You can merge multiple input segments into one output segment.\n"
        "   - You can split a long input segment if needed (though merging is more common).\n"
        "3. **Translate**: Translate the enhanced text into fluent {target_language}.\n"
        "4. **Output**: Return a JSON list of objects. Each object represents a new subtitle entry.\n\n"
        "Output JSON Structure:\n"
        "{\n"
        '  "subtitles": [\n'
        "    {\n"
        '      "start_index": <int, index of the first input segment covered>,\n'
        '      "end_index": <int, index of the last input segment covered>,\n'
        '      "text_en": "<string, enhanced English text>",\n'
        '      "text_zh": "<string, translated Chinese text>"\n'
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}\n\n"
        "Constraints:\n"
        "- `start_index` and `end_index` refer to the 1-based indices in the input list.\n"
        "- Ensure all input content is covered; do not skip information.\n"
        "- The sequence of `start_index` to `end_index` must be contiguous and non-overlapping across the output list.\n"
        "- `text_en` should be the corrected, enhanced version of the source text.\n"
        "- `text_zh` should be the translation of `text_en`.\n"
        "- **CRITICAL LENGTH CONSTRAINT**: Each `text_en` MUST NOT exceed 80 characters (approximately 2 lines on screen). "
        "If a merged sentence would exceed this limit, split it into multiple subtitle entries at natural break points "
        "(commas, semicolons, conjunctions like 'and', 'but', 'so', 'then', or after complete clauses). "
        "This is essential for video player readability - subtitles that are too long will obscure the video content."
    )

    user_prompt = (
        f"Context:\n{background_str}\n\n"
        f"Target Language: {target_language}\n\n"
        "Input Subtitles:\n"
        f"{transcript_text}\n\n"
        "Process these subtitles and return the JSON output."
    )

    return user_prompt, system_prompt
