---
status: pending
priority: p1
issue_id: "010"
tags: [code-review, reliability, streaming, backend]
dependencies: []
---

# Fix Read-Aloud Stream Subscription Race

## Problem Statement

`/api/read-aloud/stream/<content_id>` starts background generation before the SSE subscriber is attached. Early events can be dropped, causing missing metadata or first sentences during playback.

## Findings

- `stream_read_aloud` starts the worker thread before constructing the streaming generator: [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/read_aloud.py:45).
- Subscriber attachment happens inside `EventPublisher.stream()` when iteration begins: [events.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/sse/events.py:168).
- Events published before any subscriber are discarded: [events.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/sse/events.py:79).
- The first event (`read_aloud_meta`) is emitted immediately in `_run`, so race window is real: [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py:115).

## Proposed Solutions

### Option 1: Start Generation Only After Subscriber Is Attached

**Approach:** Wrap SSE generator so subscription occurs first, then start worker thread from inside generator after first yield preparation.

**Pros:**
- Minimal architecture change
- Fixes event-loss race deterministically

**Cons:**
- Requires careful ordering in route code

**Effort:** Small

**Risk:** Low

---

### Option 2: Add Event Replay Buffer for Read-Aloud Channels

**Approach:** Store latest N events per channel and replay to new subscribers.

**Pros:**
- Handles reconnects better
- More resilient under brief disconnects

**Cons:**
- More memory/state management complexity
- Needs clear replay semantics to avoid duplicates

**Effort:** Medium

**Risk:** Medium

---

### Option 3: Move Read-Aloud to Task Manager + Event History

**Approach:** Use task IDs and task event history to stream deterministic event sequence.

**Pros:**
- Strongest long-term reliability model
- Aligns with other task-based flows

**Cons:**
- Largest refactor

**Effort:** Large

**Risk:** Medium

## Recommended Action


## Technical Details

**Affected files:**
- [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/read_aloud.py)
- [events.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/sse/events.py)
- [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py)

## Resources

- **Review target:** `master...feat/notes-read-aloud`
- **Related finding:** Session/channel isolation issue in `003`

## Acceptance Criteria

- [ ] No read-aloud events are dropped when stream starts
- [ ] `read_aloud_meta` is always received before/with sentence events
- [ ] Integration test proves deterministic first-event delivery
- [ ] Manual run confirms no missing first sentence on fast/short notes

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Reviewed read-aloud route and SSE publisher sequencing
- Traced call order for thread start vs subscription
- Confirmed pre-subscription event drop behavior in broadcaster

**Learnings:**
- Current startup ordering is inherently racy for immediate events
- This can cause hard-to-reproduce playback truncation

## Notes

- Blocks merge due functional correctness risk in core playback path.
