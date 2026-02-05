# Bold Proposal: Quiz Feature Prompt Algorithms

## Innovation Summary

A knowledge-category-aware MCQ generator using structured prompt templates with misconception-based distractor generation, difficulty-calibrated question framing, and bilingual technical term preservation.

## Research Findings

**Key insights from SOTA research:**

1. **Knowledge injection via prompts** is critical - researchers recommend injecting domain knowledge into prompts rather than relying on LLM's internal knowledge to prevent hallucinations.

2. **81.7% of GPT-4 generated MCQs pass all evaluation criteria** - but 57% had at least one implausible distractor.

3. **Chain-of-Thought for distractor generation** - instructing LLMs to generate feedback/reasoning before distractors creates a "scaffold that guides subsequent generation of plausible distractors".

4. **Misconception diversity is critical** - each distractor should reflect a different misconception on the topic.

5. **Explanation inclusion is essential** - ablation studies show excluding explanations "results in a huge performance drop-off" in distractor quality.

6. **Difficulty encoding challenges** - GPT-4o achieves only 37.75% accuracy on difficulty classification.

## Proposed Prompt Design

### Complete Implementation (~150 LOC)

```python
"""Quiz generation prompts."""

from __future__ import annotations

# =============================================================================
# Category-to-Question-Type Mapping
# =============================================================================

CATEGORY_QUESTION_GUIDANCE = {
    "formula": """
For FORMULA items, create questions that test:
- Correct variable identification (which symbol represents what?)
- Correct formula application (given inputs, what is the output?)
- Boundary conditions (what happens at edge values?)
- Common sign/order errors (where do students typically make mistakes?)

Distractor strategy for formulas:
- Swap numerator/denominator
- Use wrong operator (+/- confusion)
- Missing/extra terms
- Wrong variable subscripts""",

    "definition": """
For DEFINITION items, create questions that test:
- Precise terminology (which term matches this description?)
- Scope boundaries (what does this concept include/exclude?)
- Distinction from similar concepts (how is X different from Y?)
- Necessary vs sufficient conditions

Distractor strategy for definitions:
- Use related but distinct terms
- Include partial definitions (missing key qualifier)
- Swap cause and effect
- Use colloquial misunderstandings""",

    "condition": """
For CONDITION items, create questions that test:
- When does this condition apply?
- What triggers this condition?
- What are the exceptions?
- Boundary cases (edge of condition range)

Distractor strategy for conditions:
- Necessary but not sufficient conditions
- Conditions from similar but different contexts
- Inverted conditions (opposite of correct)
- Off-by-one boundary errors""",

    "algorithm": """
For ALGORITHM items, create questions that test:
- Correct step ordering (what comes first/next?)
- Termination conditions (when does it stop?)
- Input/output relationships (given X, what is the result?)
- Time/space complexity awareness

Distractor strategy for algorithms:
- Swapped step order
- Wrong loop termination
- Off-by-one iteration count
- Confusing similar algorithms""",

    "constant": """
For CONSTANT items, create questions that test:
- Exact value recall (what is the value of X?)
- Unit associations (what unit does this constant use?)
- Context of use (when would you use this constant?)
- Related constants (distinguish from similar values)

Distractor strategy for constants:
- Close but incorrect values (order of magnitude errors)
- Wrong units
- Values from similar but different constants
- Common memorization errors""",

    "example": """
For EXAMPLE items, create questions that test:
- Pattern recognition (which scenario matches this example?)
- Generalization (what principle does this example illustrate?)
- Counter-example identification (which would NOT be an example?)
- Application to new contexts

Distractor strategy for examples:
- Similar but incorrect scenarios
- Partial matches (correct in some aspects only)
- Over-generalization errors
- Edge cases that break the pattern"""
}

# =============================================================================
# Difficulty Level Instructions
# =============================================================================

DIFFICULTY_INSTRUCTIONS = {
    "easy": """
EASY difficulty requirements:
- Test direct recall from the knowledge content
- Question stem should closely mirror the original phrasing
- Distractors should be clearly wrong to someone who studied the material
- No inference or synthesis required
- Single concept per question

Example easy question structure:
- "According to [topic], what is [direct fact]?"
- "Which of the following correctly states [definition]?"
- "What is the value of [constant]?" """,

    "medium": """
MEDIUM difficulty requirements:
- Test application of knowledge to new situations
- Require one step of inference or transformation
- Distractors should be plausible misconceptions
- May combine two related concepts
- Require understanding, not just memorization

Example medium question structure:
- "If [condition], what would be the result using [formula]?"
- "Which scenario best demonstrates [concept]?"
- "What would happen if [variation on standard case]?" """,

    "hard": """
HARD difficulty requirements:
- Test edge cases, exceptions, or synthesis
- Require multi-step reasoning
- Distractors should represent sophisticated errors
- May require combining 3+ concepts
- Test limits of applicability

Example hard question structure:
- "Under which condition would [standard rule] NOT apply?"
- "If both [condition A] and [condition B], what is the result?"
- "Which of the following represents a valid exception to [rule]?" """
}

# =============================================================================
# Main Prompt Builder
# =============================================================================

def build_quiz_generation_prompts(
    knowledge_items_json: str,
    language: str,
    question_count: int = 10,
    difficulty: str = "medium",
    user_instruction: str = "",
) -> tuple[str, str]:
    """Build system and user prompts for quiz generation."""

    difficulty_guidance = DIFFICULTY_INSTRUCTIONS.get(
        difficulty, DIFFICULTY_INSTRUCTIONS["medium"]
    )

    category_guidance_block = "\n\n".join(
        f"### {cat.upper()}\n{guidance}"
        for cat, guidance in CATEGORY_QUESTION_GUIDANCE.items()
    )

    system_prompt = f"""You are an expert educational assessment designer creating MCQs.

Output language: {language}
Target question count: {question_count}

{difficulty_guidance}

=== CATEGORY-SPECIFIC QUESTION DESIGN ===

{category_guidance_block}

=== DISTRACTOR GENERATION RULES ===

1. PLAUSIBILITY: Each distractor must be wrong but believable
2. MISCONCEPTION DIVERSITY: Each distractor should target a DIFFERENT error type
3. NO GIVEAWAYS: Distractors must not be obviously absurd
4. FEEDBACK REASONING: Consider "What misconception would lead to this choice?"

=== BILINGUAL HANDLING ===

- Write question stems and explanations in {language}
- PRESERVE technical terms, formulas, and proper nouns in original language

=== OUTPUT FORMAT ===

Output ONLY valid JSON array:

[
  {{
    "stem": "The question text in {language}",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer_index": 0,
    "explanation": "Why option A is correct and why each distractor is wrong",
    "source_category": "formula|definition|condition|algorithm|constant|example",
    "source_tags": ["tag1", "tag2"]
  }}
]

CRITICAL: "answer_index" is 0-based. "options" must have EXACTLY 4 items."""

    user_prompt = f"""Generate {question_count} MCQs from:

KNOWLEDGE ITEMS:
{knowledge_items_json}

{f"ADDITIONAL INSTRUCTIONS: {user_instruction}" if user_instruction else ""}

Return ONLY the JSON array."""

    return system_prompt, user_prompt
```

### Distractor Generation Strategy

| Category | Primary Misconception Types |
|----------|---------------------------|
| `formula` | Sign errors, operator confusion, missing terms |
| `definition` | Related term confusion, partial definitions |
| `condition` | Necessary vs sufficient confusion, boundary errors |
| `algorithm` | Step order swaps, termination errors |
| `constant` | Magnitude errors, unit confusion |
| `example` | Over-generalization, partial matches |

### Difficulty Control

| Level | Cognitive Load | Characteristics |
|-------|---------------|-----------------|
| `easy` | Direct recall | Close to original, single concept |
| `medium` | One-step inference | Application, two concepts |
| `hard` | Multi-step synthesis | Edge cases, 3+ concepts |

## Sources

- [MCQ Generation Using LLMs](https://arxiv.org/abs/2506.04851)
- [AI vs Human MCQs Study](https://dl.acm.org/doi/fullHtml/10.1145/3636243.3636256)
- [Automated Distractor Generation](https://arxiv.org/html/2404.02124v2)
- [Personalized Distractors via MCTS](https://arxiv.org/html/2508.11184)
