---
status: pending
priority: p2
issue_id: "005"
tags: [code-review, tests, read-aloud, reliability]
dependencies: []
---

# Add Read-Aloud Integration and Unit Tests

## Problem Statement

The new read-aloud feature spans API route, use case orchestration, SSE events, cache storage, and frontend playback hook, but there is currently no dedicated test coverage for this stack.

## Findings

- Search found prompt-template tests only; no read-aloud tests under `tests/`.
- New backend modules added without corresponding tests:
  - [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/read_aloud.py)
  - [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py)
  - [markdown_text_filter.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/shared/markdown_text_filter.py)
  - [fs_read_aloud_cache.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_read_aloud_cache.py)
- This increases risk for concurrency/order regressions and cache correctness defects.

## Proposed Solutions

### Option 1: Targeted backend contract tests first (recommended)

**Approach:** Add unit tests for use case event order and cache keying, plus integration tests for `/stream` and `/audio` behavior.

**Pros:**
- Fast confidence on highest-risk paths
- Catches regressions before UI-level tests

**Cons:**
- Does not validate browser playback behavior

**Effort:** Medium

**Risk:** Low

---

### Option 2: Full-stack browser tests for read-aloud tab

**Approach:** Add frontend e2e tests for start/pause/resume/jump and sentence progression.

**Pros:**
- Validates user-visible behavior end-to-end

**Cons:**
- Slower and more brittle than unit/integration

**Effort:** Large

**Risk:** Medium

## Recommended Action


## Technical Details

**Suggested test areas:**
- Event stream ordering and completion semantics
- Parallel/restart behavior with same `content_id`
- Audio cache lookup and error fallback
- Markdown filtering edge cases (code blocks, links, latex)

## Resources

- Branch under review: `feat/notes-read-aloud`

## Acceptance Criteria

- [ ] Unit tests cover `ReadAloudUseCase` success/fallback/error branches
- [ ] Integration tests cover `/api/read-aloud/stream` and `/api/read-aloud/audio`
- [ ] Tests include restart/jump scenario for same content
- [ ] CI includes these tests in normal backend suite

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Searched repository test paths for read-aloud coverage
- Enumerated untested modules in new feature stack

**Learnings:**
- Coverage gap is broad enough to hide high-impact regressions.
