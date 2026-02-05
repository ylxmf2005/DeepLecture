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

**Generated**: 2026-02-03 15:57

This document combines three perspectives from our multi-agent debate-based planning system:
1. **Report 1**: issue-8-bold-proposal.md
2. **Report 2**: issue-8-critique.md
3. **Report 3**: issue-8-reducer.md

---

## Part 1: issue-8-bold-proposal.md

# Bold Proposal: Optimized Video-to-Notes Generation

## Innovation Summary

Replace the current "N parts x full context" parallel expansion with a three-stage **Extract-Assign-Render** pipeline: (1) extract a deduplicated concept graph from the transcript, (2) assign concepts to outline parts during outline generation, then (3) expand each part using only its assigned context segments -- eliminating repetition at the architectural level and cutting token usage by 60-80%.

## Research Findings

1. **Map-Reduce with Concept Reduction** (Google Cloud Blog): The "reduce" step should merge/deduplicate, not just concatenate.
2. **Hierarchical Summarization with CoT** (CoTHSSum, Springer 2025): Structured intermediate representations outperform direct summarization.
3. **One-Shot vs. Chunked Tradeoffs** (Snowflake RAG study): For detailed notes, retrieval/chunking still outperforms stuffing. Key is concept-aligned chunks.
4. **G2: Guided Generation for Diversity** (arXiv 2025): Making later steps aware of earlier output prevents repetition.
5. **Cheatsheet Pattern (Internal)**: Two-stage extract-render naturally prevents repetition.

## Strategy A: Outline with Concept Assignment + Targeted Context (Recommended)

Three-stage pipeline: Outline+Assignment → Parallel Part Expansion with targeted context → Join
- Solves repetition: concepts assigned to exactly one part
- Solves token waste: 60-80% reduction (only relevant segments per part)
- Preserves parallelism
- ~350 LOC

## Strategy B: Knowledge Extraction + Rendering (Cheatsheet Pattern)

Two-stage: Extract KnowledgeItems → Render full note in one call
- Maximum token efficiency (2 LLM calls total)
- Zero repetition
- Risk: output length limits for long notes
- ~400 LOC

## Strategy C: Sequential Generation with "Previously Covered" Tracking

Sequential pipeline with accumulating concept list
- Simplest change (~150 LOC)
- Does NOT solve token waste
- Loses parallelism
- Repetition reduced but not eliminated

## Comparative Analysis

| Criterion | A (Concept Assignment) | B (Extract-Render) | C (Sequential) |
|---|---|---|---|
| Repetition | Structural | Structural | Soft |
| Token reduction | 60-80% | 80-90% | 0% |
| Parallelism | Yes | N/A | No |
| Quality risk | Low | Medium (length limits) | Low |
| LOC | ~350 | ~400 | ~150 |

**Recommendation: Strategy A** — best quality-to-complexity ratio.

---

## Part 2: issue-8-critique.md

# Proposal Critique: Note Generation Improvement Strategies

## Executive Summary

Strategy A has a **critical LLM reliability risk**: asking a model to simultaneously design an outline AND identify precise transcript line ranges in a single JSON call is a task that current LLMs frequently get wrong. Strategy B is more aligned with a proven pattern but output-length concern is real. Strategy C is correctly identified as weakest.

## Key Assumption Validations

### Assumption 1: LLM can reliably assign concepts AND identify transcript line ranges
**Status: Questionable**
Current subtitle context in `_load_subtitle_context()` joins segment text into plain newline-separated lines WITHOUT line numbers. LLMs are notoriously unreliable at accurately identifying line numbers in long documents.

### Assumption 2: 60-80% token reduction from targeted context slicing
**Status: Questionable**
Assumes concepts are cleanly separable within a transcript — rarely true for lectures that revisit concepts and build incrementally.

### Assumption 3: Strategy B output length limits
**Status: Questionable**
The `LLMModelConfig.max_tokens = 2000` is defined but never passed to `OpenAILLM.complete()`. Real limit may be higher than assumed.

### Assumption 5: Strategy A estimated at ~350 LOC
**Status: Underestimated**
450-550 LOC more realistic including error handling for malformed LLM responses.

## High Priority Risks

1. **LLM line-range hallucination (Strategy A)** — HIGH likelihood
2. **Quality degradation from aggressive context slicing** — HIGH for interdisciplinary lectures
3. **Output truncation (Strategy B)** — MEDIUM-HIGH for long content

## Critical Recommendations

### Must Address

1. **Replace LLM line-range extraction with deterministic context retrieval** using focus_points as search queries
2. **Measure current token waste** before choosing a strategy
3. **Investigate the `max_tokens=2000` config disconnect**

### Quick Win (Zero infrastructure)
Add explicit anti-repetition instructions to current part prompt: "You are ONLY responsible for the focus points listed above. Do NOT explain concepts that are covered in other parts."

## Overall Assessment
**Feasibility**: Medium — Strategy A is feasible but line-range mechanism is wrong implementation
**Readiness**: Needs revision — replace LLM line ranges with deterministic retrieval based on focus_points

---

## Part 3: issue-8-reducer.md

# Simplified Proposal: Note Generation Improvement

## Simplification Summary

The core problems — content repetition and token waste — can be solved with a **single, minimal change**: improve prompts to assign concepts exclusively and make parts aware of siblings. No new DTOs, no context slicing infrastructure needed. This is fundamentally a **prompt engineering problem**, not an architecture problem.

## What Was Removed

1. **Strategy B: Knowledge Extraction + Rendering** — Notes need multi-part parallel expansion, cheatsheet pattern would truncate or require splitting anyway
2. **Strategy C: Sequential Generation** — Destroys parallelism, doesn't reduce tokens
3. **`assigned_concepts` DTO field** — Existing `focus_points` already serves this purpose
4. **`context_segments` with line-range slicing** — Over-engineered; LLM line-range targeting is fragile

## Minimal Viable Solution (~55 LOC)

### 1. Outline prompt improvement (prompt-only)
- Make LLM assign each concept to exactly one part with no overlap
- ~15 lines changed in `build_note_outline_prompt`

### 2. Part prompt improvement (prompt + minor signature)
- Pass full outline as formatted string so each part knows its siblings
- Add "do NOT explain concepts from other parts" instruction
- ~25 lines changed in `build_note_part_prompt`

### 3. Caller wiring
- Thread outline list through to part prompt builder
- ~10 lines in `note.py`

## Comparison

| Aspect | Original Strategy A | Simplified |
|--------|---------------------|------------|
| Total LOC | ~350 | ~55 |
| New DTO fields | 2 | 0 |
| Solves repetition | Yes | Yes |
| Solves token waste | 60-80% | No (deferred) |
| Risk | Medium (context slicing bugs) | Very low |

## Trade-off Justification

**Token waste deferred because:**
1. Repetition is the user-facing quality problem; tokens are a cost problem
2. Modern LLM pricing trends make this less urgent
3. Full context ensures each part can reference any relevant material
4. Can add keyword-based filtering later (~100 additional LOC) if needed

## Red Flags Eliminated

1. **Premature infrastructure** for context slicing when better prompts suffice
2. **Strategy proliferation** — three strategies when one minimal approach works
3. **DTO expansion** for speculative needs
4. **Cheatsheet pattern cargo-culting** — notes have different requirements

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
