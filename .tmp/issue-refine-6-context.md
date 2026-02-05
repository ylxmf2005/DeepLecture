# Context Summary: Quiz Feature Prompt Design Refinement

## Feature Understanding
**Intent**: Refine the Quiz feature implementation plan (Issue #6) by expanding algorithmic details and designing specific LLM prompts for the two-stage knowledge extraction → quiz generation pipeline.

**Scope signals**: "prompt design", "algorithmic details", "knowledge extraction", "MCQ generation", "distractor selection", "two-stage pipeline", "bilingual output"

## Existing Prompt Patterns in Codebase

### Pattern 1: Two-Stage Prompt Builder (Cheatsheet)
```python
def build_cheatsheet_extraction_prompts(
    context: str,
    language: str,
    subject_type: str = "auto",
    user_instruction: str = "",
) -> tuple[str, str]:
    system_prompt = f"""You are an expert knowledge extractor...
Output language: {language}
{subject_hint}

Output ONLY valid JSON array with this structure:
[
  {{
    "category": "formula|definition|condition|algorithm|constant|example",
    "content": "The actual knowledge item content",
    "criticality": "high|medium|low",
    "tags": ["topic1", "topic2"]
  }}
]"""
```

### Pattern 2: Bilingual Output (Subtitle)
```python
OUTPUT FORMAT (strict JSON, no markdown):
{{"subtitles": [{{"start_index": 1, "end_index": 2, "text_source": "...", "text_target": "..."}}]}}
```

### Pattern 3: Decision Logic in JSON (Timeline)
```python
If you decide that NO explanation is needed, answer:
{"should_explain": false}

If you decide that an explanation IS needed, answer:
{
  "should_explain": true,
  "title": "...",
  ...
}
```

### Pattern 4: JSON Parsing with Fallback
- Uses `parse_llm_json()` with `json_repair` library
- Handles markdown fences, missing quotes, malformed structures
- Falls back to empty array/dict on parse failure

## Constraints Discovered

1. **Prompt return type**: `tuple[str, str]` (system_prompt, user_prompt)
2. **JSON schema**: Must be explicit with examples in system prompt
3. **Language handling**: Explicitly state output language
4. **No markdown fences**: Strict JSON without code blocks
5. **Criticality levels**: high=3, medium=2, low=1
6. **Context modes**: "auto"|"subtitle"|"slide"|"both"
7. **Security**: Use `sanitize_user_input()` for all user inputs

## Focus Areas for Prompt Design

### Area 1: MCQ Distractor Generation
- No existing patterns for plausible wrong answer generation
- Need single-shot MCQ generation with 3-4 distractors

### Area 2: Knowledge → Quiz Mapping
- `formula` → calculation questions
- `definition` → recognition questions
- `condition` → scenario questions
- `algorithm` → sequence questions

### Area 3: Difficulty Levels (Simple)
- Easy: Direct recall
- Medium: Application/inference
- Hard: Synthesis/edge cases

### Area 4: Question Count Control
- Filter by criticality first
- Truncation strategy for fewer results

**Recommended path**: `full` (research-heavy prompt engineering task)
