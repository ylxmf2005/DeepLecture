---
status: pending
priority: p3
issue_id: "007"
tags: [code-review, frontend, performance, read-aloud]
dependencies: []
---

# Reduce O(n^2) Rendering in Sentence List

## Problem Statement

`SentenceList` computes `globalIndex` with `sentences.indexOf(sentence)` during render for each sentence item. This creates quadratic behavior as sentence count grows and can degrade UI responsiveness on long notes.

## Findings

- Index lookup is performed per sentence item in [ReadAloudTab.tsx](/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/ReadAloudTab.tsx:268).
- For large notes (hundreds/thousands of sentences), repeated linear lookup inside map loops causes avoidable render overhead.

## Proposed Solutions

### Option 1: Precompute index map once per render (recommended)

**Approach:** Build `Map<sentenceKey, index>` or include `globalIndex` in state when ingesting events.

**Pros:**
- Linear render complexity
- Minimal behavior change

**Cons:**
- Slightly more state/derived-data management

**Effort:** Small

**Risk:** Low

---

### Option 2: Flatten grouped rendering with indexed iteration

**Approach:** Render from a single indexed list and derive paragraph boundaries from metadata.

**Pros:**
- Eliminates repeated lookups naturally

**Cons:**
- More refactor effort and code churn

**Effort:** Medium

**Risk:** Medium

## Recommended Action


## Technical Details

**Affected file:**
- [ReadAloudTab.tsx](/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/ReadAloudTab.tsx)

## Resources

- Feature branch: `feat/notes-read-aloud`

## Acceptance Criteria

- [ ] Render path avoids `indexOf` in per-item loop
- [ ] Profiling shows stable render time as sentence count increases
- [ ] No behavior regressions in active/past sentence highlighting

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Reviewed sentence rendering logic and index derivation
- Flagged avoidable complexity in hot render loop

**Learnings:**
- This is optimization/maintainability, not a functional blocker.
