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
