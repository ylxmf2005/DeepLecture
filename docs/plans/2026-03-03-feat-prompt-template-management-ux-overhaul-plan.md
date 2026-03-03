---
title: "feat: Prompt Template Management UX Overhaul"
type: feat
date: 2026-03-03
brainstorm: docs/brainstorms/2026-03-03-prompt-template-ux-brainstorm.md
---

# feat: Prompt Template Management UX Overhaul

## Overview

Redesign the prompt template management experience in the Settings → Prompts tab to solve two core problems: (1) the creation UX is hostile — users don't know what placeholders are available, there's no default template to start from, and system/user template roles are unexplained; (2) templates cannot be edited, duplicated, or deleted after creation. Additionally, fix underlying architectural issues discovered during analysis: registry cache invalidation gaps, runtime crash risks from stale template references, and frontend-backend placeholder metadata drift.

## Problem Statement

### User-Facing Problems

1. **Blind template creation**: Users must guess available placeholders. The frontend hardcodes `FUNC_PLACEHOLDERS` (PromptTab.tsx:36-101) which is already out of sync with the backend — missing `podcast_dialogue`, `podcast_dramatize`, and `coverage_mode` for `cheatsheet_extraction`.
2. **No edit/delete**: Once created, templates are permanent. No way to fix a typo, iterate on a prompt, or clean up experiments.
3. **No guidance**: System Template vs User Template distinction is unexplained. No default examples shown. Users start from a blank textarea.

### Technical Problems (discovered during analysis)

4. **Registry cache leak**: `refresh_prompt_registry()` (container.py:413) only drops the registry cache. Cached use cases (`subtitle_uc`, `note_uc`, etc.) hold stale references. Template changes silently have no effect until restart.
5. **Runtime crash on stale references**: `PromptRegistry.get()` (registry.py:~91) raises `ValueError` for unknown `impl_id`. If a template is deleted while selected (globally or per-video), any prompt-dependent feature crashes.
6. **No metadata API**: Placeholder rules exist only in Python code (`template_definitions.py`). Frontend must manually duplicate them — a known anti-pattern that has already caused drift (see `docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md`).

## Proposed Solution

### Architecture: Refactor Prompts Tab In-Place with Drawer Editor

Redesign the Prompts tab content within the existing `SettingsDialog` modal. Add a new Drawer component that slides from the right, overlaying the template list. The drawer contains the full template editor with click-to-insert placeholder panel.

### High-Level Components

```
SettingsDialog (existing)
└── PromptTab (refactored)
    ├── TemplateGroupList           # Collapsible groups by category
    │   ├── TemplateGroup           # One per category (9 total)
    │   │   ├── GroupHeader         # Category name + collapse toggle
    │   │   ├── TemplateCard[]      # One per template (default + custom)
    │   │   └── NewTemplateButton   # Opens drawer for creation
    │   └── ...
    └── TemplateDrawer              # Slide-from-right overlay
        ├── DrawerHeader            # Title + close button
        ├── TemplateForm            # Name, impl_id, description
        ├── TemplateEditor          # System + User template textareas
        │   ├── SystemTemplateArea  # With label + explanation
        │   └── UserTemplateArea    # With label + explanation
        ├── PlaceholderPanel        # Click-to-insert variable chips
        └── DrawerFooter            # Save / Cancel + validation errors
```

## Technical Approach

### Phase 1: Backend Foundation (API + Storage + Registry Fixes)

Fix the underlying infrastructure before building the UI. This phase has no user-visible changes but resolves crash risks and enables all subsequent work.

#### 1.1 Add `delete_template()` to Storage

**File**: `src/deeplecture/infrastructure/repositories/fs_prompt_template_storage.py`

```python
# Add hard-delete method. No soft-delete — brainstorm decided against activate/deactivate.
def delete_template(self, func_id: str, impl_id: str) -> bool:
    """Delete a template by func_id + impl_id. Returns True if found and deleted."""
    # Load payload, filter out matching template, atomic write back
```

- Hard delete (remove from JSON), consistent with the existing atomic-write pattern
- Returns `bool` indicating whether deletion occurred
- Raises no error if template not found (idempotent)

#### 1.2 Add PUT and DELETE API Endpoints

**File**: `src/deeplecture/presentation/api/routes/prompt_templates.py`

| Method | Path | Description |
|--------|------|-------------|
| `PUT` | `/api/prompt-templates/{func_id}/{impl_id}` | Update an existing custom template |
| `DELETE` | `/api/prompt-templates/{func_id}/{impl_id}` | Delete a custom template |

**PUT endpoint logic:**
1. Validate `func_id` is known
2. Validate `impl_id != "default"` (cannot edit built-in)
3. Validate template exists (return 404 if not)
4. Run `validate_prompt_template_definition()` on the updated data
5. Call `storage.upsert_template()` + `container.refresh_prompt_registry()`
6. Return updated template

**DELETE endpoint logic:**
1. Validate `impl_id != "default"` (cannot delete built-in)
2. Check if template is selected in global config → return 409 Conflict with message
3. Call `storage.delete_template(func_id, impl_id)`
4. If the deleted template was selected globally, reset selection to "default"
5. Call `container.refresh_prompt_registry()`
6. Return 204 No Content

> **Design decision (from SpecFlow Q9)**: Backend checks global config only. Per-video references are handled gracefully by the fallback fix in 1.4. This avoids expensive O(n) scans of all content configs.

#### 1.3 Add Placeholder Metadata API

**File**: `src/deeplecture/use_cases/prompts/template_definitions.py` — add descriptions map

```python
_PLACEHOLDER_DESCRIPTIONS: dict[str, str] = {
    "language": "Output language for generated content",
    "learner_profile": "User's learning profile and preferences",
    "question": "The user's question text",
    "context_block": "Relevant subtitle/transcript context",
    "history_block": "Previous conversation history",
    "segments": "Subtitle segments data",
    "transcript_text": "Raw transcript text",
    # ... all placeholders
}
```

**File**: `src/deeplecture/presentation/api/routes/prompt_templates.py` — extend GET response

Extend the existing `GET /api/prompt-templates` response to include:

```json
{
  "templates": [...],
  "func_ids": [...],
  "metadata": {
    "ask_video": {
      "allowed": ["learner_profile", "language", "context_block", "history_block", "question"],
      "required": ["question"],
      "descriptions": {
        "question": "The user's question text",
        "context_block": "Relevant subtitle/transcript context",
        ...
      }
    },
    ...
  }
}
```

This single endpoint provides everything the frontend needs, eliminating hardcoded `FUNC_PLACEHOLDERS`.

#### 1.4 Add Default Template Text Retrieval

**File**: `src/deeplecture/use_cases/prompts/registry.py`

Add a method to `PromptRegistry` to retrieve the raw template text of built-in builders:

```python
def get_prompt_text(self, func_id: str, impl_id: str | None = None) -> dict[str, str]:
    """Return {"system_template": "...", "user_template": "..."} for the given builder."""
```

> This method already exists at registry.py but only returns one template string. Extend it or add a new method `get_template_texts()` that returns both system and user strings.

**File**: `src/deeplecture/presentation/api/routes/prompt_templates.py` — new endpoint

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/prompt-templates/{func_id}/{impl_id}/text` | Get raw system + user template text |

This enables the drawer to pre-fill with the default template content.

#### 1.5 Fix Registry Graceful Fallback

**File**: `src/deeplecture/use_cases/prompts/registry.py` — `get()` method

Change `PromptRegistry.get()` to return the default builder when an unknown `impl_id` is requested, instead of raising `ValueError`. Log a warning for observability.

```python
def get(self, func_id: str, impl_id: str | None = None) -> PromptBuilder:
    builders = self._builders.get(func_id)
    if not builders:
        raise ValueError(f"Unknown func_id: {func_id}")
    if impl_id and impl_id in builders:
        return builders[impl_id]
    if impl_id:
        logger.warning("Unknown impl_id '%s' for func_id '%s', falling back to default", impl_id, func_id)
    default_id = self._defaults.get(func_id, "default")
    return builders[default_id]
```

This prevents runtime crashes from stale references (deleted templates still selected in per-video configs).

#### 1.6 Fix Registry Cache Invalidation

**File**: `src/deeplecture/di/container.py`

When `refresh_prompt_registry()` is called, also invalidate all cached use cases that hold a reference to the registry. The simplest approach: make use cases resolve the registry lazily through the container on each call, rather than holding a direct reference.

Alternatively, have `refresh_prompt_registry()` also clear all use case caches:

```python
def refresh_prompt_registry(self) -> None:
    self._prompt_registry = None
    # Also invalidate use cases that depend on the registry
    self._subtitle_uc = None
    self._timeline_uc = None
    self._note_uc = None
    # ... all prompt-dependent use cases
```

---

### Phase 2: Frontend API Layer + Type Updates

Bridge the backend changes to the frontend before building UI components.

#### 2.1 Update API Client

**File**: `frontend/lib/api/promptTemplates.ts`

Add missing CRUD functions:

```typescript
export const updatePromptTemplate = async (
  funcId: string, implId: string, payload: UpdatePromptTemplatePayload
): Promise<PromptTemplate> => { ... };

export const deletePromptTemplate = async (
  funcId: string, implId: string
): Promise<void> => { ... };

export const getPromptTemplateText = async (
  funcId: string, implId: string
): Promise<{ systemTemplate: string; userTemplate: string }> => { ... };
```

#### 2.2 Update Types

**File**: `frontend/lib/api/types.ts`

```typescript
// Add to existing types
export interface UpdatePromptTemplatePayload {
  name?: string;
  description?: string;
  systemTemplate?: string;
  userTemplate?: string;
}

// Extended response with metadata
export interface PlaceholderMetadata {
  allowed: string[];
  required: string[];
  descriptions: Record<string, string>;
}

export interface PromptTemplatesResponse {
  templates: PromptTemplate[];
  funcIds: string[];
  metadata: Record<string, PlaceholderMetadata>;  // keyed by func_id
}
```

#### 2.3 Remove Hardcoded `FUNC_PLACEHOLDERS`

**File**: `frontend/components/dialogs/settings/PromptTab.tsx`

Delete the hardcoded `FUNC_PLACEHOLDERS` constant (lines 36-101) and `PROMPT_LABELS` (lines 17-34). Replace with data fetched from the API's `metadata` field. This resolves the sync drift issue permanently.

Category grouping and display labels should be defined as a frontend constant (since this is a UI concern):

```typescript
const TEMPLATE_CATEGORIES: { label: string; funcIds: string[] }[] = [
  { label: "Q&A", funcIds: ["ask_video", "ask_summarize_context"] },
  { label: "Subtitles", funcIds: ["subtitle_background", "subtitle_enhance_translate"] },
  { label: "Timeline", funcIds: ["timeline_segmentation", "timeline_explanation"] },
  { label: "Slides", funcIds: ["slide_lecture"] },
  { label: "Explanation", funcIds: ["explanation_system", "explanation_user"] },
  { label: "Notes", funcIds: ["note_outline", "note_part"] },
  { label: "Knowledge", funcIds: ["cheatsheet_extraction", "cheatsheet_rendering"] },
  { label: "Assessment", funcIds: ["quiz_generation", "flashcard_generation", "test_paper_generation"] },
  { label: "Podcast", funcIds: ["podcast_dialogue", "podcast_dramatize"] },
];
```

> Note: `PROMPT_LABELS` (human-readable func_id names) can either move to the API metadata or remain as a frontend map. Keeping it frontend-side is simpler since it's a pure display concern.

---

### Phase 3: Frontend UI Components

Build the new UI components. All use Tailwind CSS v4, `cn()` utility, `lucide-react` icons, and `framer-motion` for animations, consistent with existing patterns.

#### 3.1 Drawer Component

**New file**: `frontend/components/ui/Drawer.tsx`

A reusable side drawer component:

```typescript
interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}
```

- Slides from right using `framer-motion` (`animate: { x: 0 }`, `exit: { x: "100%" }`)
- Full height of the Settings content area (not the entire viewport)
- Renders inside the Prompts tab container with `position: absolute` + `inset-y-0 right-0`
- Width: `w-full` (replaces the template list entirely when open)
- Focus trap via existing `useFocusTrap` hook pattern
- Escape key closes (with unsaved changes check)
- Semi-transparent backdrop over the template list

#### 3.2 Unsaved Changes Guard

**New file**: `frontend/components/dialogs/settings/useUnsavedChangesGuard.ts`

```typescript
function useUnsavedChangesGuard(isDirty: boolean) {
  // Returns a guard function that shows ConfirmDialog if isDirty
  // Called before: close drawer, switch tab, close settings dialog
}
```

Uses the existing `ConfirmDialog` component pattern.

#### 3.3 TemplateGroupList Component

**New file**: `frontend/components/dialogs/settings/prompt/TemplateGroupList.tsx`

- Renders 9 collapsible category groups
- Each group header: category icon (from lucide-react) + label + template count badge + collapse toggle
- Default state: all groups expanded
- Each group contains `TemplateCard` items for default + custom templates
- "New Template" button at the bottom of each group
- Uses `framer-motion` `AnimatePresence` for smooth collapse/expand

#### 3.4 TemplateCard Component

**New file**: `frontend/components/dialogs/settings/prompt/TemplateCard.tsx`

Each template row displays:
- Template name + impl_id subtitle
- "Default" badge for built-in templates (read-only indicator)
- "Active" indicator if currently selected
- Action buttons: Edit (pencil icon), Duplicate (copy icon), Delete (trash icon)
- Default templates: only Duplicate is available (no edit/delete)

Click edit/duplicate → opens Drawer. Click delete → shows ConfirmDialog.

#### 3.5 TemplateDrawer (Editor) Component

**New file**: `frontend/components/dialogs/settings/prompt/TemplateDrawer.tsx`

The main editor, rendered inside the Drawer:

**Layout (top to bottom):**

1. **Header**: Mode label ("New Template" / "Edit Template" / "Duplicate Template") + func_id display name
2. **Form fields**:
   - Template Name (text input, required)
   - Template ID / impl_id (text input, auto-generated from name via slugify, editable; disabled during edit)
   - Description (optional text input)
3. **Role explanation banner**:
   > "**System Template** sets the AI's role, persona, and behavioral constraints. **User Template** defines the per-request prompt with dynamic context."
4. **Template editors** (two textareas, stacked):
   - System Template (label + textarea, pre-filled with default content)
   - User Template (label + textarea, pre-filled with default content)
   - Each textarea: monospace font, ~8-12 rows, resizable
   - Track which textarea was last focused (for placeholder insertion)
5. **Placeholder Panel** (below textareas or as a collapsible section):
   - Grouped as: Required placeholders (bold, `*` marker) + Optional placeholders
   - Each chip: `{placeholder_name}` + description tooltip
   - Click chip → insert `{placeholder_name}` at cursor position in last-focused textarea
   - If no textarea focused, show hint "Click a template field first"
6. **Validation messages**: Inline errors for missing required placeholders, invalid impl_id format, duplicate impl_id
7. **Footer**: Cancel button + Save button (primary)

**Modes:**
- **Create**: Pre-fill from default template, impl_id editable, save calls POST
- **Edit**: Load existing template, impl_id disabled (read-only), save calls PUT
- **Duplicate**: Pre-fill from source template, impl_id editable (pre-filled as `{source}_copy`), save calls POST

#### 3.6 Cursor Insertion Logic

**In TemplateDrawer**: Track cursor position with `useRef` per textarea.

```typescript
const systemRef = useRef<HTMLTextAreaElement>(null);
const userRef = useRef<HTMLTextAreaElement>(null);
const lastFocusedRef = useRef<HTMLTextAreaElement | null>(null);

const insertPlaceholder = (name: string) => {
  const textarea = lastFocusedRef.current;
  if (!textarea) return;
  const { selectionStart, selectionEnd } = textarea;
  const value = textarea.value;
  const insertion = `{${name}}`;
  const newValue = value.slice(0, selectionStart) + insertion + value.slice(selectionEnd);
  // Update React state + restore cursor position after render
};
```

#### 3.7 Refactor PromptTab

**File**: `frontend/components/dialogs/settings/PromptTab.tsx` — major refactor

Replace the entire content with:

1. Fetch templates + metadata from API on mount (or use cached data from Zustand)
2. Render `TemplateGroupList` as main content
3. Render `TemplateDrawer` inside a `Drawer` (conditionally when editing)
4. Keep the existing `CustomSelect` dropdown for template *selection* per func_id (this is the "which template to use" control, separate from management)
5. Remove the old inline creation form entirely

**State management:**
- Local state for drawer open/close, current editing template, dirty flag
- API calls for CRUD operations (create/update/delete)
- After any CRUD → refetch templates list + call existing `fetchConfig()` to sync selection dropdowns

---

### Phase 4: Integration and Polish

#### 4.1 Accessibility

- Drawer: `role="dialog"`, `aria-label="Edit template"`, focus trap
- Collapsible groups: `aria-expanded`, `aria-controls` on group header buttons
- Placeholder chips: `role="button"`, `aria-label="Insert {name} placeholder"`
- Template textareas: `aria-label="System template"` / `aria-label="User template"`

#### 4.2 Keyboard Navigation

- `Escape` in drawer → unsaved changes check → close
- `Tab` navigation within drawer fields
- `Enter` on placeholder chip → insert
- Drawer focus trap: Tab cycles within drawer when open

#### 4.3 Error Handling

- API errors during save → toast notification (using existing `sonner` setup)
- 409 on delete (template in use) → show specific message: "This template is currently selected. Switch to a different template first."
- Network errors → toast with retry suggestion

---

## Acceptance Criteria

### Functional Requirements

- [x] User can view all templates grouped by 9 categories with collapsible sections
- [x] User can create a new template with pre-filled default content
- [x] User can edit an existing custom template via the drawer
- [x] User can duplicate any template (including defaults) as a new template
- [x] User can delete a custom template (with confirmation dialog)
- [x] User cannot edit or delete default (built-in) templates
- [x] User cannot delete a template that is currently selected globally (409 error with clear message)
- [x] Placeholder panel shows all available variables with descriptions and required/optional markers
- [x] Clicking a placeholder chip inserts `{placeholder_name}` at the cursor position in the last-focused textarea
- [x] System/User template roles are explained with a visible banner
- [x] Unsaved changes warning when closing drawer with modifications
- [x] Template selection dropdown (existing) continues to work with new/edited/deleted templates

### Non-Functional Requirements

- [x] Placeholder metadata is fetched from the API, not hardcoded in frontend
- [x] `PromptRegistry.get()` gracefully falls back to default for unknown impl_ids (no crashes)
- [x] Registry cache invalidation correctly propagates to all dependent use cases
- [x] Delete operation checks global config for usage before allowing deletion
- [x] All drawer interactions are keyboard-accessible

### Quality Gates

- [x] Existing template creation still works (backward compatible POST endpoint)
- [x] Existing template selection still works (no regression in config API)
- [x] All 18 func_ids appear in the UI with correct placeholder metadata
- [ ] Backend tests for PUT, DELETE endpoints + storage delete method
- [ ] Frontend tests for drawer open/close, placeholder insertion, CRUD flows

## File Change Summary

### New Files

| File | Purpose |
|------|---------|
| `frontend/components/ui/Drawer.tsx` | Reusable slide-from-right drawer |
| `frontend/components/dialogs/settings/prompt/TemplateGroupList.tsx` | Collapsible category groups |
| `frontend/components/dialogs/settings/prompt/TemplateCard.tsx` | Individual template row with actions |
| `frontend/components/dialogs/settings/prompt/TemplateDrawer.tsx` | Full template editor form |
| `frontend/components/dialogs/settings/prompt/constants.ts` | Category grouping, label maps |
| `frontend/components/dialogs/settings/useUnsavedChangesGuard.ts` | Dirty state guard hook |

### Modified Files

| File | Changes |
|------|---------|
| `src/deeplecture/infrastructure/repositories/fs_prompt_template_storage.py` | Add `delete_template()` |
| `src/deeplecture/presentation/api/routes/prompt_templates.py` | Add PUT, DELETE, GET text endpoints; extend GET list with metadata |
| `src/deeplecture/use_cases/prompts/template_definitions.py` | Add `_PLACEHOLDER_DESCRIPTIONS` map; add `get_metadata()` function |
| `src/deeplecture/use_cases/prompts/registry.py` | Fix `get()` fallback; add/extend `get_template_texts()` |
| `src/deeplecture/di/container.py` | Fix `refresh_prompt_registry()` to invalidate dependent use cases |
| `frontend/lib/api/promptTemplates.ts` | Add `update`, `delete`, `getTemplateText` functions |
| `frontend/lib/api/types.ts` | Add `UpdatePromptTemplatePayload`, `PlaceholderMetadata` types |
| `frontend/components/dialogs/settings/PromptTab.tsx` | Major refactor: replace inline form with TemplateGroupList + TemplateDrawer |

### Deleted Code

| Location | What |
|----------|------|
| `PromptTab.tsx:17-34` | Hardcoded `PROMPT_LABELS` (moved to constants or fetched from API) |
| `PromptTab.tsx:36-101` | Hardcoded `FUNC_PLACEHOLDERS` (replaced by API metadata) |
| `PromptTab.tsx` inline create form | Old creation form (replaced by drawer) |

## Implementation Order

```
Phase 1 (Backend)          Phase 2 (API Layer)        Phase 3 (UI)              Phase 4 (Polish)
─────────────────          ───────────────────        ────────────              ─────────────────
1.1 Storage delete    ──►  2.1 API client funcs  ──►  3.1 Drawer component  ──►  4.1 Accessibility
1.2 PUT/DELETE routes ──►  2.2 Type updates       │   3.2 Unsaved guard         4.2 Keyboard nav
1.3 Metadata API      │   2.3 Remove hardcoded   │   3.3 GroupList              4.3 Error handling
1.4 Template text API  │       FUNC_PLACEHOLDERS  │   3.4 TemplateCard
1.5 Registry fallback  │                          │   3.5 TemplateDrawer
1.6 Cache invalidation │                          │   3.6 Cursor insertion
                       │                          │   3.7 Refactor PromptTab
                       └──────────────────────────┘
```

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Drawer too narrow within Settings modal | Poor editing experience for long templates | Make drawer `w-full`, replacing template list view entirely when open |
| Placeholder descriptions incomplete | Users still confused about some variables | Provide sensible defaults; iterate based on feedback |
| Registry cache invalidation too aggressive | Performance impact from re-creating use cases | Only invalidate prompt-dependent use cases, not all cached objects |
| Concurrent template edits (multiple tabs) | Lost writes in filesystem storage | Acceptable risk for single-user app; atomic writes prevent corruption |
| Per-video configs with stale template refs | Silent fallback to default | Registry graceful fallback (1.5) + log warning for observability |

## References

- **Brainstorm**: `docs/brainstorms/2026-03-03-prompt-template-ux-brainstorm.md`
- **Prior plan**: `docs/plans/2026-02-13-feat-global-prompt-template-library-plan.md`
- **Settings architecture**: `docs/plans/2026-02-12-feat-unified-settings-all-pervideo-overrides-plan.md`
- **Policy drift lesson**: `docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md`
- **Backend template defs**: `src/deeplecture/use_cases/prompts/template_definitions.py`
- **Registry**: `src/deeplecture/use_cases/prompts/registry.py`
- **Storage**: `src/deeplecture/infrastructure/repositories/fs_prompt_template_storage.py`
- **API routes**: `src/deeplecture/presentation/api/routes/prompt_templates.py`
- **Frontend PromptTab**: `frontend/components/dialogs/settings/PromptTab.tsx`
- **Settings Dialog**: `frontend/components/dialogs/SettingsDialog.tsx`
- **API client**: `frontend/lib/api/promptTemplates.ts`
