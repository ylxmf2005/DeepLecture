---
status: complete
priority: p1
issue_id: "001"
tags: [python, frontend, llm, test-paper]
dependencies: []
---

# Implement AI Test Paper Generation

## Problem Statement

The `test` tab exists but still renders a placeholder. We need full backend + frontend implementation for exam-style open-ended test paper generation with Bloom-level labels, aligned with existing quiz/flashcard architecture.

## Findings

- Plan and brainstorm are defined in `docs/plans/2026-03-03-feat-ai-test-paper-generation-plan.md` and `docs/brainstorms/2026-03-03-test-exam-brainstorm.md`.
- Existing patterns already exist for quiz/flashcard in DTOs, use cases, prompt registry, DI, routes, API clients, and SSE refresh wiring.
- The task type for this feature is `test_paper_generation` and API prefix should be `/api/test-paper`.

## Proposed Solutions

### Option 1: Mirror quiz implementation with minimal adaptation

**Approach:** Copy quiz skeleton and adapt data model + prompt/use-case specifics.

**Pros:**
- Fast implementation
- Lower architectural risk

**Cons:**
- Might miss flashcard timestamp/linking nuances

**Effort:** 5-7 hours

**Risk:** Medium

---

### Option 2: Mirror flashcard implementation with test-paper data model

**Approach:** Reuse flashcard two-stage flow (timestamp-aware extraction) with test-paper-specific validation and UI.

**Pros:**
- Best match for timestamped source linking in UI
- Strong consistency with latest feature patterns

**Cons:**
- Slightly larger adaptation for scoring/bloom stats

**Effort:** 5-7 hours

**Risk:** Low

## Recommended Action

Execute Option 2 and keep implementation strictly aligned with existing flashcard/quiz conventions.

## Acceptance Criteria

- [x] Backend test-paper DTO/storage/use-case/route implemented and wired
- [x] Prompt registry supports `test_paper_generation`
- [x] Frontend API + `TestTab` + tab wiring + SSE refresh implemented
- [x] New test-paper unit tests pass
- [x] Relevant quality checks pass
- [x] Plan checklist updated to completed state

## Work Log

### 2026-03-03 - Setup

**By:** Codex

**Actions:**
- Created feature branch `codex/feat-test-paper-generation`
- Reviewed plan + brainstorm docs and implementation references
- Created this tracking todo

**Learnings:**
- Existing flashcard architecture is the strongest baseline for this feature.

### 2026-03-03 - Implementation + Verification

**By:** Codex

**Actions:**
- Implemented backend test-paper stack:
  - DTO: `src/deeplecture/use_cases/dto/test_paper.py`
  - Storage protocol + FS repo + DI wiring + API route/blueprint registration
  - Prompt builder + registry registration for `test_paper_generation`
  - Use case pipeline with validation, bloom/question-type stats, and timestamp-aware context loading
- Implemented frontend delivery:
  - API client: `frontend/lib/api/test-paper.ts`
  - UI: `frontend/components/features/TestTab.tsx`
  - Tab wiring + SSE refresh state (`refreshTest`) in video page flows
  - Task label and tests updated for `test_paper_generation`
- Added tests:
  - `tests/unit/use_cases/test_test_paper.py`
  - Updated `frontend/lib/__tests__/taskTypes.test.ts`
- Updated plan file checklist to reflect completed work.

**Verification:**
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/unit/use_cases/test_test_paper.py tests/unit/use_cases/test_flashcard.py tests/unit/presentation/api/test_model_resolution.py`
- `cd frontend && npm run test -- lib/__tests__/taskTypes.test.ts`
- `cd frontend && npm run typecheck`
- `ruff check` on all changed backend/test files (clean)

**Learnings:**
- Two-stage reuse from flashcard reduced implementation risk significantly.
- Environment-level pytest plugin autoload (`logfire`) requires `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` in this workspace.
