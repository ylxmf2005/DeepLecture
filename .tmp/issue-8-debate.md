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
