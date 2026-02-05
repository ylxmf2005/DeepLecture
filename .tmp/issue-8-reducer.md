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
