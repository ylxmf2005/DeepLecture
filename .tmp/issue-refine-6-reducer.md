# Simplified Proposal: Quiz Generation Prompt Design

## Simplification Summary

The bold proposal's 150-line system prompt with CATEGORY_QUESTION_GUIDANCE and DIFFICULTY_INSTRUCTIONS is over-engineered. Modern LLMs can infer category-appropriate questions and difficulty levels from minimal guidance. This simplification reduces the prompt from ~150 lines to ~35 lines.

## Core Problem Restatement

**What we're solving**: Generate MCQs with 4 options, correct answer, and explanation from lecture content.

**What we're NOT solving** (removed):
- Per-category distractor strategies (LLM knows common misconceptions)
- Bloom's taxonomy calibration (over-specifies cognitive levels)
- Detailed difficulty instructions with examples
- Chain-of-thought reasoning requirements
- TwinStar dual-LLM review stage

## Existing Prompt Patterns in Codebase

| File | System Prompt Lines |
|------|---------------------|
| `cheatsheet.py` | ~25 lines |
| `explanation.py` | ~20 lines |
| `note.py` | ~30 lines |
| `ask.py` | ~25 lines |
| `timeline.py` | ~35 lines |

**Pattern**: Existing prompts are 20-35 lines. They rely on LLM capabilities, not exhaustive instruction.

## Minimal Quiz Prompt (~35 lines)

```python
def build_quiz_generation_prompt(
    knowledge_context: str,
    language: str,
    n_questions: int = 5,
    difficulty: str = "medium",
) -> tuple[str, str]:
    """Build minimal MCQ generation prompt."""

    system_prompt = f"""You are an expert educator creating quiz questions.

Generate {n_questions} multiple-choice questions (MCQs) from the provided content.

REQUIREMENTS:
- Each question has exactly 4 options (A, B, C, D)
- Exactly one option is correct
- Distractors should be plausible but clearly wrong
- Include a brief explanation for the correct answer
- Difficulty: {difficulty}
- Output language: {language}

Output ONLY a JSON array:
[
  {{
    "question": "...",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "correct_index": 0,
    "explanation": "..."
  }}
]"""

    user_prompt = f"""Generate quiz questions from this content:

{knowledge_context}"""

    return system_prompt, user_prompt
```

## Comparison

| Aspect | Original | Simplified |
|--------|----------|------------|
| Prompt LOC | ~150 | ~35 |
| LLM calls | 3 (stages) | 1 |
| Token cost | ~3200-4200/quiz | ~900/quiz |
| Complexity | High | Low |

## What We Sacrifice (and Why It's OK)

1. **Per-category distractor strategies**
   - LLMs generate appropriate distractors without explicit guidance
   - Recovery: Add category hints if testing shows weak distractors

2. **Bloom's taxonomy calibration**
   - "easy/medium/hard" covers 99% of use cases
   - Recovery: Add optional `bloom_level` if requested

3. **Distractor reasoning metadata**
   - Explanation field explains correct answer, which is sufficient
   - Recovery: Extend schema if users request detailed wrong-answer explanations

## Token Cost Analysis

| Approach | Tokens/Quiz | Cost Savings |
|----------|-------------|--------------|
| Original (3-stage, 150-line prompt) | ~3200-4200 | - |
| Simplified (1-stage, 35-line prompt) | ~900 | **70-80%** |

## Red Flags Eliminated

1. **CATEGORY_QUESTION_GUIDANCE**: Pre-optimizes for categories that may not need special handling
2. **Three-stage pipeline**: Adds orchestration complexity for marginal quality gain
3. **Bloom's definitions in prompt**: LLMs already know educational theory
4. **TwinStar review**: Second LLM call rarely catches issues a good primary prompt wouldn't avoid

## Summary

Start with a 35-line prompt. Measure quality. Add complexity only when empirical evidence demands it.

**The best prompt is the shortest one that works.**
