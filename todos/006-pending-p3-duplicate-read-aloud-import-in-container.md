---
status: pending
priority: p3
issue_id: "006"
tags: [code-review, python, lint, maintainability]
dependencies: []
---

# Remove Duplicate ReadAloudUseCase Import

## Problem Statement

`ReadAloudUseCase` is imported twice in the DI container file, causing lint failures and unnecessary noise in quality checks.

## Findings

- Duplicate import appears at two locations in [container.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/di/container.py:68) and [container.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/di/container.py:75).
- `uv run ruff check` reports `F811` redefinition and `I001` import formatting errors.

## Proposed Solutions

### Option 1: Remove duplicate import and run auto-format (recommended)

**Approach:** Keep one import, run `ruff --fix` or manual cleanup.

**Pros:**
- Immediate fix
- Restores lint cleanliness

**Cons:**
- None significant

**Effort:** Small

**Risk:** Low

## Recommended Action


## Technical Details

**Affected file:**
- [container.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/di/container.py)

## Resources

- Lint command used: `uv run ruff check ...`

## Acceptance Criteria

- [ ] Duplicate import removed
- [ ] `ruff check` passes for container module

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Ran targeted `ruff` checks on changed backend files
- Captured concrete lint diagnostics

**Learnings:**
- This is a low-risk hygiene issue but can fail strict CI gates.
