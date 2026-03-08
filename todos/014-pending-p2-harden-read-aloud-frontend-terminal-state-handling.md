---
status: pending
priority: p2
issue_id: "014"
tags: [code-review, frontend, reliability, state-machine]
dependencies: []
---

# Harden Read-Aloud Frontend Terminal State Handling

## Problem Statement

The frontend hook can remain in non-terminal states when stream completion/errors occur without enough buffered sentences, producing stuck UI/playback states.

## Findings

- `play()` sets state to `loading`: [useReadAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useReadAloud.ts:306).
- On `read_aloud_complete`, handler only closes SSE and does not transition state: [useReadAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useReadAloud.ts:253).
- On `es.onerror`, if sentences exist, no error/idle transition occurs: [useReadAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useReadAloud.ts:278).
- Playback loop can wait indefinitely for next sentence when stream is already closed: [useReadAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useReadAloud.ts:164).

## Proposed Solutions

### Option 1: Explicit Terminal-State Rules on Complete/Error

**Approach:** On `read_aloud_complete`, set `idle` if not actively playing; on SSE error with closed stream and pending next sentence, set recoverable error state.

**Pros:**
- Predictable UI behavior
- Minimal refactor

**Cons:**
- Requires careful branch conditions

**Effort:** Small

**Risk:** Low

---

### Option 2: Introduce Reducer-Based State Machine

**Approach:** Replace ad-hoc state updates with explicit finite-state transitions.

**Pros:**
- Easier to reason about edge cases
- Better testability

**Cons:**
- Refactor overhead

**Effort:** Medium

**Risk:** Medium

---

### Option 3: Add Stall Watchdog

**Approach:** If no new sentence arrives for N seconds after stream close while not complete, transition to error/idle.

**Pros:**
- Protects UX under transient failures

**Cons:**
- Timer complexity; may need tuning

**Effort:** Small-Medium

**Risk:** Medium

## Recommended Action


## Technical Details

**Affected files:**
- [useReadAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useReadAloud.ts)

## Resources

- **Review target:** `master...feat/notes-read-aloud`

## Acceptance Criteria

- [ ] UI never remains indefinitely in loading/playing after stream termination
- [ ] Completion with zero ready sentences transitions to a terminal state
- [ ] Disconnect mid-stream shows recoverable status and does not hang playback
- [ ] Edge cases covered with hook tests

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Audited `useReadAloud` state transitions for completion/error branches
- Traced conditions where no sentence-ready events arrive
- Identified wait-path with closed stream and no forward progress

**Learnings:**
- Terminal-state handling is incomplete for non-happy paths

## Notes

- Reliability issue with high user-visible impact during network/provider instability.
