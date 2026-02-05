# External Consensus Review Task

You are an expert software architect tasked with synthesizing a consensus implementation plan from three different perspectives on the same feature.

## Context

Three specialized agents have analyzed the following requirement:

**Feature Request**: Unknown Feature

Each agent provided a different perspective:
1. **Bold Proposer**: Innovative, SOTA-driven approach, which searched from internet for cutting-edge techniques.
   - The bold proposal includes the "Original User Request" section with the verbatim feature description.
2. **Critique Agent**: Feasibility analysis and risk assessment for the aggressive solution from the **Bold Proposer**.
3. **Reducer Agent**: Simplified, "less is more" approach focusing on the core functionality from a minimalistic standpoint, by simplifying the **Bold Proposer**'s design.

## Your Task

Review all three perspectives and synthesize a **balanced, consensus implementation plan** that:

1. **Incorporates the best ideas** from each perspective
2. **Resolves conflicts** between the proposals
3. **Balances innovation with pragmatism**
4. **Maintains simplicity** while not sacrificing essential features
5. **Addresses critical risks** identified in the critique
6. **Verifies documentation accuracy** - ensure proposals cite `docs/` for current command interfaces

## Input: Combined Report

Below is the combined report containing all three perspectives:

---

# Multi-Agent Debate Report: Unknown Feature

**Generated**: 2026-01-28 10:09

This document combines three perspectives from our multi-agent debate-based planning system:
1. **Report 1**: issue-refine-6-bold-proposal.md
2. **Report 2**: issue-refine-6-critique.md
3. **Report 3**: issue-refine-6-reducer.md

---

## Part 1: issue-refine-6-bold-proposal.md

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

---

## Part 2: issue-refine-6-critique.md

# Proposal Critique: Quiz Prompt Algorithm Refinement

## Executive Summary

The proposal demonstrates solid research grounding and aligns with existing codebase patterns, but the ~150 LOC system prompt is significantly longer than established patterns (existing prompts range 35-90 lines). The 37.75% LLM accuracy on difficulty classification raises serious questions about whether difficulty levels should be included at all in v1.

## Critical Issues

### Issue 1: Prompt Length vs Existing Patterns

| Existing File | System Prompt Lines |
|---------------|---------------------|
| `cheatsheet.py` | ~25-35 lines |
| `slide_lecture.py` | ~40 lines |
| `timeline.py` | ~30 lines |
| `note.py` | ~20 lines |
| **Proposed quiz.py** | **~150 lines** |

**Problem**: The proposal is 3-4x larger than any existing pattern.

### Issue 2: Difficulty Parameter Self-Contradiction

The proposal cites: "GPT-4o achieves only 37.75% accuracy on difficulty classification"

This is **worse than random guessing** (33% for 3 classes). Including difficulty in v1 creates a broken feature.

**Recommendation**: Remove difficulty from v1. Add as experimental flag in v2.

### Issue 3: Category Guidance Redundancy

The 6 category-specific guidance blocks (~60 LOC) duplicate information already in the cheatsheet extraction stage. If a `KnowledgeItem` is categorized as "formula", the LLM already knows it is a formula.

### Issue 4: LLM Attention Degradation

LLMs may ignore later instructions in very long prompts. The ~150 line system prompt places distractor rules and output format at the end - these may be deprioritized.

**Mitigation**: Move CRITICAL instructions (output format, answer_index rules) to the TOP.

### Issue 5: No Validation Strategy

Missing:
- `answer_index` out of bounds handling
- Duplicate options detection
- Empty explanations handling
- Malformed JSON fallback

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Prompt too long - attention degradation | High | High | Reduce to ~60-80 LOC |
| Difficulty parameter misleading | High | Medium | Remove from v1 |
| Category guidance doesn't improve quality | Medium | Low | Test empirically |
| JSON validation missing | Medium | Medium | Add validation layer |

## Recommendations

### Must Address

1. **Remove difficulty parameter from v1** - Research shows 37.75% accuracy
2. **Reduce system prompt to ~60-80 LOC**
3. **Add JSON validation specification**

### Should Consider

1. **Consolidate category guidance into compact table**:
   ```python
   {"formula": "Test: calculation. Distractors: sign/operator errors"}
   ```

2. **Add prompt version tracking for A/B testing**

3. **Test prompt length impact empirically** (50 vs 100 vs 150 LOC)

## Overall Assessment

**Feasibility**: Medium-High
**Complexity**: Over-engineered (3x existing prompt lengths)
**Readiness**: Needs revision

**Bottom line**: Remove difficulty levels, cut system prompt length by 40-50%. Ship minimal viable prompt (~80 LOC) first, iterate based on output quality.

---

## Part 3: issue-refine-6-reducer.md

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

---

## Next Steps

This combined report will be reviewed by an external consensus agent (Codex or Claude Opus) to synthesize a final, balanced implementation plan.

---

## Output Requirements

Generate a final implementation plan that follows the plan-guideline structure and rules:
- **Design-first TDD ordering**: Documentation → Tests → Implementation (never invert).
- **Use LOC estimates only** (no time-based estimates).
- **Be concrete**: cite exact repo-relative files/sections; avoid vague audit steps.
- **Include dependencies** for each step so ordering is enforced.
- **For every step, list correspondence** to documentation and test cases (what it updates, depends on, or satisfies).
- **If this is a bug fix**, include Bug Reproduction (or explicit skip reason).

```markdown
# Implementation Plan: Unknown Feature

## Consensus Summary

[2-3 sentences explaining the balanced approach chosen]

## Goal
[1-2 sentence problem statement]

**Success criteria:**
- [Criterion 1]
- [Criterion 2]

**Out of scope:**
- [What we're not doing]
- However, it it a good idea for future work?
  - If so, briefly describe it here. ✅ Good to have in the future: Briefly describe it in 1-2 sentences.
  - If not, explain why it's excluded. ❌ Not needed: Explain why it is a bad idea.

## Bug Reproduction
*(Optional - include only for bug fixes where reproduction was attempted)*

**Steps tried:**
- [Command or action performed]
- [Files examined]

**Observed symptoms:**
- [Error messages, test failures, unexpected behavior]

**Environment snapshot:**
- [Relevant file state, dependencies, configuration]

**Root cause hypothesis:**
- [Diagnosis based on observations]

**Skip reason** *(if reproduction not attempted)*:
- [Why reproduction was skipped]

**Unreproducible constraints** *(if reproduction failed)*:
- [What was tried and why it didn't reproduce]
- [Hypothesis for proceeding without reproduction]

## Codebase Analysis

**Files verified (docs/code checked by agents):**
- [File path 1]: [What was verified]
- [File path 2]: [What was verified]

**File changes:**

| File | Level | Purpose |
|------|-------|---------|
| `path/to/file1` | major | Significant changes description |
| `path/to/file2` | medium | Moderate changes description |
| `path/to/file3` | minor | Small changes description |
| `path/to/new/file` (new) | major | New file purpose (Est: X LOC) |
| `path/to/deprecated/file` | remove | Reason for removal |

**Modification level definitions:**
- **minor**: Cosmetic or trivial changes (comments, formatting, <10 LOC changed)
- **medium**: Moderate changes to existing logic (10-50 LOC, no interface changes)
- **major**: Significant structural changes (>50 LOC, interface changes, or new files)
- **remove**: File deletion

**Current architecture notes:**
[Key observations about existing code]

## Interface Design

**New interfaces:**
- Interface signatures and descriptions. Especially talk about:
  - Exposed functionalities to internal use or user usage
  - Internal implmentation based on the complexity
    - If it is less than 20 LoC, you can just talk about the semantics of the interface omit this
    - If it is with for loop and complicated conditional logics, put the steps here:
      - Step 1: Get ready for input
      - Step 2: Iterate over the input
        - Step 2.1: Check condition A
        - Step 2.2: Check condition B
        - Step 2.3: If condition A and B met, do X, if not go back to Step 2
        - Step 2.3: Return output based on conditionals
      - Step 3: Return final output
  - If any data structures or bookkeepings are needed, describe them here
    - What attributes are needed?
    - What are they recording?
    - Do they have any member methods associated?

**Modified interfaces:**
- [Before/after comparisons]
- It is preferred to have `diff` format if the change is less than 20 LoC:
```diff
- old line 1
- old line 2
+ new line 1
+ new line 2
```

**Documentation changes:**
- [Doc files to update with sections]

## Documentation Planning

**REQUIRED**: Explicitly identify all documentation impacts using these categories:

**High-level design docs (docs/):**
- `docs/workflows/*.md` — workflow and process documentation
- `docs/tutorial/*.md` — tutorial and getting-started guides
- `docs/architecture/*.md` — architectural design docs

**Folder READMEs:**
- `path/to/module/README.md` — module purpose and organization

**Interface docs:**
- Source file companion `.md` files documenting interfaces

Each document modifications should be as details as using `diff` format:
```diff
- Old document on interface(a, b, c)
+ New document on new_interface(a, b, c, d)
+ d handles the new feature by...
```

**Format:**
```markdown
## Documentation Planning

### High-level design docs (docs/)
- `docs/path/to/doc.md` — create/update [brief rationale]

### Folder READMEs
- `path/to/README.md` — update [what aspect]

### Interface docs
- `src/module/component.md` — update [which interfaces]
```

**Citation requirement:** When referencing existing command interfaces (e.g., `/ultra-planner`, `/issue-to-impl`), cite the actual `docs/` files (e.g., `docs/workflows/ultra-planner.md`, `docs/tutorial/02-issue-to-impl.md`) to ensure accuracy.

## Test Strategy

**Test modifications:**
- `test/file1` - What to test
  - Test case: Description
  - Test case: Description

**New test files:**
- `test/new_file` - Purpose (Estimated: X LOC)
  - Test case: Description
  - Test case: Description

**Test data required:**
- [Fixtures, sample data, etc.]

## Implementation Steps

**Step 1: [Documentation change]** (Estimated: X LOC)
- File changes
Dependencies: None
Correspondence:
- Docs: [What this step adds/updates]
- Tests: [N/A or what this enables]

**Step 2: [Test case changes]** (Estimated: X LOC)
- File changes
Dependencies: Step 1
Correspondence:
- Docs: [Which doc changes define these tests]
- Tests: [New/updated cases introduced here]

**Step 3: [Implementation change]** (Estimated: X LOC)
- File changes
Dependencies: Step 2
Correspondence:
- Docs: [Which doc behaviors are implemented here]
- Tests: [Which test cases this step satisfies]

If is preffered to put some implementation snippets here, if it is less than 20 LoC, use this format:
\`\`\`diff
- the code to be modified
+ the modified code
\`\`\`
where gives plan reviewer a quick idea of the implementation.

...

**Total estimated complexity:** X LOC ([Complexity level])
**Recommended approach:** [Single session / Milestone commits]
**Milestone strategy** *(only if large)*:
- **M1**: [What to complete in milestone 1]
- **M2**: [What to complete in milestone 2]
- **Delivery**: [Final deliverable]

## Success Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk 1] | [H/M/L] | [H/M/L] | [How to mitigate] |
| [Risk 2] | [H/M/L] | [H/M/L] | [How to mitigate] |

## Dependencies

[Any external dependencies or requirements]
```

## Evaluation Criteria

Your consensus plan should:

✅ **Be balanced**: Not too bold, not too conservative
✅ **Be practical**: Implementable with available tools/time
✅ **Be complete**: Include all essential components
✅ **Be clear**: Unambiguous implementation steps
✅ **Address risks**: Mitigate critical concerns from critique
✅ **Stay simple**: Remove unnecessary complexity per reducer
✅ **Correct measurement**: Use LOC estimates only; no time-based estimates
✅ **Accurate modification levels**: Every file must have correct level (minor/medium/major/remove)

❌ **Avoid**: Over-engineering, ignoring risks, excessive scope creep, vague specifications, or "audit the codebase" steps

## Final Privacy Note

As this plan will be published in a Github Issue, ensure no sensitive or proprietary information is included.

- No absolute paths from `/` or `~` or some other user-specific directories included
  - Use relative path from the root of the repo instead
- No API keys, tokens, or credentials
- No internal project names or codenames
- No personal data of any kind of users or developers
- No confidential business information
