---
status: pending
priority: p2
issue_id: "004"
tags: [code-review, frontend, api-contract, settings, quality]
dependencies: []
---

# Fix Description Clearing in Template Editor

## Problem Statement

Backend now supports clearing optional fields (`description`, `user_template`) on update, but frontend update payload still omits empty `description`. Users cannot clear an existing description from the settings UI.

## Findings

- Backend update route distinguishes provided vs omitted fields and supports explicit clearing in [prompt_templates.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/prompt_templates.py:100).
- Frontend sends `description: description.trim() || undefined` in edit flow, which omits the field when empty in [TemplateDrawer.tsx](/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/dialogs/settings/prompt/TemplateDrawer.tsx:220).
- Integration tests validate backend clear behavior only (no UI-path test) in [test_prompt_templates_api.py](/Users/EthanLee/Desktop/CourseSubtitle/tests/integration/presentation/api/test_prompt_templates_api.py:77).

## Proposed Solutions

### Option 1: Send explicit empty string/null for clear

**Approach:** In edit mode, send `description: ""` (or `null`) when input is empty, and align payload types accordingly.

**Pros:**
- Minimal code change
- Unlocks expected user behavior immediately

**Cons:**
- Requires clear API contract decision (`""` vs `null`)

**Effort:** Small

**Risk:** Low

---

### Option 2: Add explicit "Clear description" action

**Approach:** Keep implicit behavior unchanged, add dedicated clear control that sends explicit clear value.

**Pros:**
- UX is explicit

**Cons:**
- More UI complexity for a basic text field behavior

**Effort:** Small

**Risk:** Low

## Recommended Action


## Technical Details

**Affected files:**
- [TemplateDrawer.tsx](/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/dialogs/settings/prompt/TemplateDrawer.tsx)
- [types.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/api/types.ts)
- [prompt_templates.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/prompt_templates.py)

## Resources

- Backend clear-field test: [test_prompt_templates_api.py](/Users/EthanLee/Desktop/CourseSubtitle/tests/integration/presentation/api/test_prompt_templates_api.py:77)

## Acceptance Criteria

- [ ] Clearing description in UI persists as cleared after refresh
- [ ] Update payload semantics for optional clear are documented and type-checked
- [ ] Add frontend test covering clear-description flow

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Compared backend update semantics with frontend payload generation
- Confirmed omission behavior prevents clear path

**Learnings:**
- The current state is a frontend/backend contract mismatch, not a backend logic bug.
