"""Podcast generation prompts.

Two-stage dialogue pipeline:
  Stage 2 (podcast_dialogue): KnowledgeItems → structured two-person dialogue.
  Stage 3 (podcast_dramatize): Rewrite dialogue for natural TTS delivery.
"""

from __future__ import annotations


def build_podcast_dialogue_prompts(
    knowledge_items_json: str,
    language: str,
    host_role: str = "",
    guest_role: str = "",
    user_instruction: str = "",
) -> tuple[str, str]:
    """Build prompts for podcast dialogue generation (Stage 2).

    Transforms extracted knowledge items into a structured two-person
    podcast conversation script.

    Args:
        knowledge_items_json: JSON string of extracted KnowledgeItems
        language: Output language
        host_role: Description of host's role/personality
        guest_role: Description of guest's role/personality
        user_instruction: Additional user guidance

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    host_desc = host_role or "A curious podcast host who guides the discussion and asks insightful follow-up questions"
    guest_desc = guest_role or "An expert guest who explains concepts clearly using analogies and real-world examples"

    system_prompt = f"""You are a world-class educational podcast script writer. Your podcasts are known for turning complex lectures into comprehensive audio study guides that students can listen to before exams.

TASK: Transform the provided knowledge items into a thorough, in-depth two-person podcast dialogue. The listener should be able to pass an exam on this material after hearing the full podcast.

SPEAKERS:
- "host": {host_desc}
- "guest": {guest_desc}

OUTPUT FORMAT (CRITICAL — READ FIRST):
Output ONLY a valid JSON object. No markdown fences, no commentary:
{{
  "title": "A concise, engaging episode title",
  "summary": "2-3 sentence summary of what the episode covers",
  "scratchpad": "Your planning notes: conversation flow, key topics, opening hook, transitions",
  "dialogue": [
    {{"speaker": "host", "text": "Opening line..."}},
    {{"speaker": "guest", "text": "Response..."}},
    ...
  ]
}}

DIALOGUE LENGTH:
- Adapt the number of dialogue turns to the volume and complexity of knowledge items.
- Every knowledge item MUST be discussed — do NOT skip or gloss over any item.
- A typical episode should have at least 3-5 dialogue turns per knowledge item. Dense or complex items deserve more.
- Do NOT artificially cap the length. A thorough podcast with 50 knowledge items may need 150-250+ turns.

DEPTH GUIDELINES:
- For each major concept: explain what it is, why it matters, how it works, and where it can go wrong.
- When knowledge items contain derivations or proofs, walk through the steps in the dialogue.
- Include worked examples: the host poses a problem, the guest solves it step by step.
- Cover common exam questions, pitfalls, edge cases, and frequent mistakes students make.
- When concepts are easily confused, explicitly compare and contrast them.
- The guest should teach like a master professor — thorough, patient, and rigorous.

CONVERSATION GUIDELINES:
- Start with the host introducing the topic engagingly.
- Alternate between speakers naturally — not strictly ABAB. Sometimes 2-3 consecutive lines from the same speaker are natural.
- The host represents a curious student: ask "why?", "how does that work?", "what if...?", "can you give an example?", "what's the common mistake here?"
- The guest should answer with depth — each dialogue turn can be 1-6 sentences. Allow longer explanations when needed.
- End with a comprehensive summary/wrap-up reviewing all key points.
- Output language: {language}

QUALITY GUIDELINES:
- Make transitions between topics smooth and natural.
- Use the host to bridge knowledge items with connecting questions.
- The guest should use analogies and real-world examples, but ALSO provide precise technical depth.
- Do NOT simply list facts. Create genuine intellectual exchange with thorough explanations.
- After explaining a concept, have the host ask a follow-up that probes deeper understanding."""

    user_prompt = f"""Create a podcast dialogue from these knowledge items:

{knowledge_items_json}

{f"Additional instructions: {user_instruction}" if user_instruction else ""}

Return a JSON object with title, summary, scratchpad, and dialogue array."""

    return system_prompt, user_prompt


def build_podcast_dramatize_prompts(
    dialogue_json: str,
    language: str,
    user_instruction: str = "",
) -> tuple[str, str]:
    """Build prompts for podcast dialogue dramatization (Stage 3).

    Rewrites a structured dialogue to sound natural when read by TTS engines.
    Adds filler words, reactions, non-verbal cues, and informal phrasing.

    Args:
        dialogue_json: JSON string of the dialogue from Stage 2
        language: Output language
        user_instruction: Additional user guidance

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = f"""You are an award-winning audio drama screenwriter specializing in educational content.

TASK: Rewrite the podcast dialogue to sound natural and engaging when read aloud by a TTS engine.

REWRITE RULES:
1. Add natural filler words and reactions appropriate to the language:
   - English: "Right", "Exactly", "Hmm", "Oh wow", "You know what", "I mean"
   - Chinese: "嗯", "对对对", "哇", "确实", "你知道吗", "就是说", "有意思"
   - Match the language of the input dialogue.
2. Add brief reactions and acknowledgements between speaker turns.
3. Use contractions and informal grammar where natural.
4. Break long sentences into shorter, punchier ones for better TTS delivery.
5. Add brief interruptions where the other speaker reacts.
6. Keep ALL factual content intact — change FORM, not SUBSTANCE.
7. Vary sentence length for rhythm — mix short reactions with longer explanations.

OUTPUT FORMAT (CRITICAL):
Output ONLY a valid JSON object. No markdown fences, no commentary:
{{
  "title": "Keep the original title",
  "summary": "Keep the original summary",
  "dialogue": [
    {{"speaker": "host", "text": "Rewritten line..."}},
    ...
  ]
}}

IMPORTANT:
- The output dialogue may have MORE items than input (due to added reactions/interruptions).
- Each speaker's core points must be preserved exactly.
- Keep ALL explanatory depth, derivations, worked examples, and technical details intact — change FORM, not SUBSTANCE or DEPTH.
- Do NOT shorten or summarize explanations. The dramatized version should be at least as long as the original.
- Output language: {language}"""

    user_prompt = f"""Rewrite this podcast dialogue to sound natural and engaging for audio:

{dialogue_json}

{f"Additional instructions: {user_instruction}" if user_instruction else ""}

Return a JSON object with title, summary, and dialogue array."""

    return system_prompt, user_prompt
