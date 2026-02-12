---
module: DeepLecture Context Pipeline
date: 2026-02-12
problem_type: logic_error
component: development_workflow
symptoms:
  - "`cheatsheet_generation` failed on slide content with `ValueError: No content available for <content_id>` despite valid `source.pdf`."
  - "`quiz_generation` accepted `context_mode=slide|both` at API layer but only loaded subtitle context in UseCase."
  - "`context_mode` semantics diverged across tasks (`note`, `quiz`, `cheatsheet`) and frontend still sent `auto`."
  - "`subtitle only` language selection was not explicitly anchored to requested original language preference."
root_cause: logic_error
resolution_type: code_fix
severity: high
tags: [context-mode, note-generation, quiz-generation, cheatsheet-generation, subtitle-fallback, slide-context]
---

# Troubleshooting: Unify Context Mode Across Note/Quiz/Cheatsheet

## Problem
`note_generation`, `quiz_generation`, and `cheatsheet_generation` did not follow a single context-source contract. This caused runtime failures (especially for slide-only content) and inconsistent behavior between frontend options and backend execution.

## Environment
- Module: DeepLecture context-selection pipeline (API routes + UseCases + frontend API clients)
- Rails Version: N/A (Python/Flask + Next.js project)
- Affected Component: Context mode validation, subtitle selection, slide text fallback
- Date: 2026-02-12

## Symptoms
- `cheatsheet_generation` async worker error:
  - `ValueError: No content available for 7425bdd8-1491-4b81-af60-cab9d22357c1`
- Slide content had `source.pdf` and no subtitles, but generation still failed.
- `quiz` route exposed `context_mode=slide|both`, but `QuizUseCase` loaded subtitles only.
- `auto` mode was intended to be removed, but code paths still accepted/mapped it.

## What Didn't Work

**Attempted Solution 1:** Fix only `CheatsheetUseCase` subtitle/slide loading.
- **Why it failed:** `quiz` and parts of route/frontend behavior still diverged, so system-level semantics remained inconsistent.

**Attempted Solution 2:** Keep `auto -> both` compatibility mapping while introducing 3-mode behavior.
- **Why it failed:** It preserved hidden legacy behavior and violated the explicit requirement to remove `auto` as a valid mode.

**Attempted Solution 3:** Initial shared slide extractor checked filesystem existence before calling extractor in tests.
- **Why it failed:** Unit tests used mocked extractor paths (`/tmp/slides.pdf`) and the pre-check short-circuited extraction, causing false negatives.

## Solution
Implemented a full-stack context-mode unification for `note`, `quiz`, and `cheatsheet`.

### 1) Standardize allowed modes to 3 values
- Allowed: `subtitle | slide | both`
- Removed runtime `auto` mapping
- Default mode is `both`

**Code changes (routes):**
```python
# Before
valid_context_modes = {"auto", "subtitle", "slide", "both"}
if context_mode == "auto":
    context_mode = "both"

# After
valid_context_modes = {"subtitle", "slide", "both"}
if context_mode not in valid_context_modes:
    return bad_request(...)
```

### 2) Unify UseCase source-selection behavior
- `subtitle`: require subtitle context
- `slide`: require slide/PDF text context
- `both`: use whichever exists, use both if both exist

This was applied consistently in:
- `NoteUseCase`
- `QuizUseCase`
- `CheatsheetUseCase`

### 3) Add explicit subtitle language preference (`subtitle_language`)
- Added to generation DTOs and route parsing.
- Used to prioritize subtitle candidates as:
  1. `<subtitle_language>_enhanced`
  2. `<subtitle_language>`
  3. remaining available languages (enhanced before base)

### 4) Centralize shared helpers
- Added shared subtitle candidate builder in `use_cases/shared/subtitle.py`.
- Added shared slide text extractor + candidate PDF paths in `use_cases/shared/context.py`.
- Reused by note/quiz/cheatsheet to avoid future drift.

### 5) Align frontend request defaults
- Frontend generation calls now default `context_mode` to `both`.
- Frontend sends `subtitle_language` derived from current source language overrides.
- Frontend context-mode types were narrowed to `subtitle | slide | both`.

### 6) Verify via tests and type checks
**Commands run:**
```bash
uv run pytest tests/unit/use_cases/test_note.py tests/unit/use_cases/test_cheatsheet.py tests/unit/use_cases/test_quiz.py tests/unit/use_cases/shared/test_subtitle.py -q
cd frontend && npm run -s typecheck
```

**Result:** all targeted tests passed and frontend typecheck passed.

## Why This Works
1. **Root cause addressed:** The issue was mode-policy drift across layers (UI/API/UseCase), not a single missing fallback.
2. **Single policy path:** Shared helpers removed duplicated/partial implementations.
3. **Mode semantics now explicit:** Each mode has clear failure and fallback behavior.
4. **Language priority deterministic:** `subtitle only` now follows the requested original-language preference with enhanced-first behavior.
5. **No legacy ambiguity:** Removing `auto` acceptance prevents hidden behavior mismatch and enforces explicit contract.

## Prevention
- Introduce one shared context resolver API for all generation tasks (note/quiz/cheatsheet/future tasks).
- Add API contract tests asserting `context_mode=auto` returns `400` for affected endpoints.
- Add consistency tests across the three UseCases for identical mode semantics.
- Require any new context-aware task to use shared helpers from `use_cases/shared/`.
- Add a docs sync check whenever mode enum changes (frontend type + backend validation + DTO defaults).

## Related Issues
No related issues documented yet in `docs/solutions/`.

Design/background references:
- `docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md`
- `docs/plans/2026-02-10-feat-cascading-task-configuration-plan.md`
