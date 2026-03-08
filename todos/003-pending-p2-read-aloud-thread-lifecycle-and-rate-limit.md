---
status: pending
priority: p2
issue_id: "003"
tags: [code-review, backend, performance, operations, read-aloud]
dependencies: ["002"]
---

# Bound Read-Aloud Worker Lifecycle

## Problem Statement

Each read-aloud stream request starts a new daemon thread with no cancellation or admission control. Stopping/restarting on the client does not stop backend generation, creating avoidable CPU/network load and potential service instability under burst traffic.

## Findings

- New stream requests always spawn a daemon thread in [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/read_aloud.py:45).
- `stop()` on frontend only closes SSE/audio locally in [useReadAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useReadAloud.ts:328); backend task keeps running.
- Global limiter explicitly skips `/stream/` paths in [rate_limiter.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/shared/rate_limiter.py:184), so this endpoint can bypass default request throttling.

## Proposed Solutions

### Option 1: Move read-aloud generation to TaskManager with cancellation token

**Approach:** Submit generation as managed task keyed by `(content_id, session_id)`; cancel prior task on stop/jump.

**Pros:**
- Reuses existing task infra
- Explicit cancellation and observability

**Cons:**
- Moderate refactor effort

**Effort:** Medium

**Risk:** Low

---

### Option 2: Keep threads, add per-content semaphore + cancellation flags

**Approach:** Maintain in-memory registry of active runs; refuse or cancel excess runs.

**Pros:**
- Smaller change than TaskManager migration

**Cons:**
- More custom concurrency code to maintain

**Effort:** Small

**Risk:** Medium

## Recommended Action


## Technical Details

**Affected files:**
- [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/read_aloud.py)
- [useReadAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useReadAloud.ts)
- [rate_limiter.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/shared/rate_limiter.py)

## Resources

- Branch under review: `feat/notes-read-aloud`

## Acceptance Criteria

- [ ] Backend generation can be cancelled when user stops or restarts read-aloud
- [ ] Concurrent run limits are enforced per content/user
- [ ] Metrics/logs expose active read-aloud runs and cancellation counts
- [ ] Load test confirms bounded worker growth under repeated start/stop cycles

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Validated stream lifecycle from route thread creation to frontend stop behavior
- Verified stream route bypasses default pre-request limiter

**Learnings:**
- This is primarily an operational/reliability risk that increases with adoption.
