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
