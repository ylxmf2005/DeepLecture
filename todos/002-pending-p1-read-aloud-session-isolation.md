---
status: pending
priority: p1
issue_id: "002"
tags: [code-review, backend, frontend, read-aloud, reliability]
dependencies: []
---

# Isolate Read-Aloud Sessions and Cache Keys

## Problem Statement

The read-aloud pipeline is keyed only by `content_id` and sentence index, so concurrent or sequential runs for the same content can mix events and reuse stale audio. This can return incorrect spoken text/audio to users (wrong language, wrong paragraph offset, or mixed runs).

## Findings

- Stream channel is shared per content (`read_aloud:{content_id}`) with no per-run identifier in [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/read_aloud.py:54) and [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py:37).
- Audio cache key only uses `sentence_key` (`p{paragraph}_s{sentence}`), not run/language/model, in [fs_read_aloud_cache.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_read_aloud_cache.py:64) and [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py:142).
- Frontend audio URL is stable across reruns (no run/version token) in [readAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/api/readAloud.ts:87).
- Existing learnings show cross-layer contract drift causes production regressions (Known Pattern): [context-mode-unification-note-quiz-cheatsheet-20260212.md](/Users/EthanLee/Desktop/CourseSubtitle/docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md).

## Proposed Solutions

### Option 1: Add `session_id` everywhere (recommended)

**Approach:** Generate a UUID per stream request; include it in SSE channel, event payload, cache path, and audio URL.

**Pros:**
- Hard isolation between runs
- Fixes mixed-event and stale-audio classes of bugs in one change

**Cons:**
- Touches backend + frontend contract
- Requires migration of current cache layout

**Effort:** Medium

**Risk:** Medium

---

### Option 2: Keep channel as-is, add run version for audio only

**Approach:** Add `run_version` query param or cache busting token only to audio URLs, keep SSE channel shared.

**Pros:**
- Smaller frontend change
- Solves stale-browser-audio issue

**Cons:**
- Does not fully prevent mixed SSE events across concurrent runs

**Effort:** Small

**Risk:** High

---

### Option 3: Single-flight lock per content

**Approach:** Allow only one active read-aloud generation per `content_id`; reject/replace prior run.

**Pros:**
- Simple operational model
- Reduces resource contention

**Cons:**
- Limits user actions (e.g., parallel previews)
- Needs explicit cancellation semantics

**Effort:** Medium

**Risk:** Medium

## Recommended Action


## Technical Details

**Affected files:**
- [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/read_aloud.py)
- [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py)
- [fs_read_aloud_cache.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_read_aloud_cache.py)
- [readAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/api/readAloud.ts)
- [useReadAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useReadAloud.ts)

## Resources

- Branch under review: `feat/notes-read-aloud`
- Related learning: [context-mode-unification-note-quiz-cheatsheet-20260212.md](/Users/EthanLee/Desktop/CourseSubtitle/docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md)

## Acceptance Criteria

- [ ] SSE events are scoped to a run/session and cannot leak across reruns
- [ ] Audio cache key contains session or deterministic content hash including language/model
- [ ] Audio URLs include run/session identity to prevent stale browser cache playback
- [ ] Integration test covers two overlapping runs for same `content_id`

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Reviewed stream channel and cache key construction end-to-end
- Traced frontend URL generation against backend cache layout
- Identified cross-run collision path

**Learnings:**
- Session-less channel + sentence-key-only cache is the dominant correctness risk in this feature.
