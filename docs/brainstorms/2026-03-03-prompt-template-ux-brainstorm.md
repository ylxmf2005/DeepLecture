# Prompt Template Management UX Overhaul

**Date:** 2026-03-03
**Status:** Brainstorm Complete
**Author:** EthanLee + Claude

## What We're Building

Overhaul the prompt template management experience to solve two core problems:

1. **Creation UX is hostile**: Users don't know what placeholders are available, there's no default template to start from, and System/User Template roles are unexplained.
2. **No edit/delete after creation**: Once a template is created, users are stuck — no way to modify, duplicate, or remove it.

### Target Experience

A template management panel in the Settings → Prompts tab, featuring:

- **Template list grouped by func_id** with collapsible sections (Q&A, Subtitles, Notes, etc.)
- **Side drawer editor** that slides in from the right for create/edit/duplicate
- **Click-to-insert placeholder panel** in the drawer showing all available variables with descriptions
- **Pre-filled default content** when creating a new template (based on the default template for that func_id)
- **Full CRUD** — create, view, edit, duplicate, delete

## Why This Approach

### Drawer over Modal/Separate Page
- Keeps users on the Settings page (familiar context)
- Drawer provides enough vertical space for template editing
- Can show the template list and editor simultaneously

### Click-to-insert over Autocomplete
- Lower implementation complexity (no need for custom textarea with autocomplete)
- Placeholder panel doubles as documentation (descriptions, required/optional markers)
- More discoverable — users see all options at once rather than needing to type `{`
- Naturally separates "editing space" from "reference space"

### Pre-fill over Reference/Copy Button
- Users start with working content immediately
- Reduces blank-page anxiety
- Users modify rather than create from scratch
- Default template serves as both example and documentation

### Grouped List over Flat/Search
- 18 func_ids is too many for a flat list
- Groups map to user mental models (subtitles, notes, Q&A are distinct features)
- Collapsible sections let users focus on what they care about
- No need for search with good grouping (searchable later if needed)

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Editor form | Side drawer (right) | Stay on settings page, enough space |
| Placeholder guidance | Click-to-insert sidebar panel | Discoverable, serves as docs |
| Default template display | Pre-fill into editor inputs | Start from working example |
| List organization | Grouped by func_id (collapsible) | 18 func_ids too many for flat |
| Extra operations | Duplicate template | Quick iteration on variants |
| Architecture | Refactor Prompts Tab in-place | Minimal change, consistent UX |

## Scope Details

### Frontend Changes (Settings → Prompts Tab)

**Template List Panel:**
- Collapsible groups by category: Q&A, Subtitles, Notes, Timeline, Slides, Knowledge, Quiz/Flashcard/Test, Podcast, Explanation
- Each group shows func_id's templates (default is always shown, marked as read-only)
- Each custom template row: name, impl_id, actions (edit / duplicate / delete)
- "New Template" button per group (pre-selects the func_id)

**Drawer Editor:**
- Header: func_id display name + template name/impl_id inputs
- Optional description field
- System Template textarea (pre-filled with default content)
- User Template textarea (pre-filled with default content)
- Explanation text: "System Template sets the AI's role and behavior. User Template defines the per-request prompt structure."
- Save / Cancel buttons

**Placeholder Panel (inside drawer):**
- Shows allowed placeholders for the selected func_id
- Each placeholder: name, description, required/optional badge
- Click inserts `{placeholder}` at the last focused textarea's cursor position
- Required placeholders visually distinguished (e.g., `*` marker or bold)
- Source: `template_definitions.py` TEMPLATE_DEFINITIONS already has all this metadata

### Backend Changes

**New API Endpoints needed:**
- `PUT /api/prompt-templates/{func_id}/{impl_id}` — Update existing template
- `DELETE /api/prompt-templates/{func_id}/{impl_id}` — Delete template (prevent deleting "default")
- `GET /api/prompt-templates/metadata/{func_id}` — Return placeholder metadata (allowed, required, descriptions) + default template content for pre-filling

**Existing endpoints to enhance:**
- `GET /api/prompt-templates` — Already returns custom templates; may need to include default template content per func_id
- `POST /api/prompt-templates` — Already works for creation; consider adding duplicate support (accept a `source_impl_id` param?)

**Storage layer:**
- `FsPromptTemplateStorage` already has `upsert_template()` — edit is covered
- Need `delete_template(func_id, impl_id)` method

### Placeholder Metadata Per func_id (already defined in backend)

The system already has complete placeholder definitions in `template_definitions.py`:
- 18 func_ids, each with allowed_placeholders and required_placeholders
- This data just needs to be exposed to the frontend via the new metadata endpoint

### Category Grouping (for collapsible UI)

| Category | func_ids |
|----------|----------|
| Q&A | ask_video, ask_summarize_context |
| Subtitles | subtitle_background, subtitle_enhance_translate |
| Timeline | timeline_segmentation, timeline_explanation |
| Slides | slide_lecture |
| Explanation | explanation_system, explanation_user |
| Notes | note_outline, note_part |
| Knowledge | cheatsheet_extraction, cheatsheet_rendering |
| Assessment | quiz_generation, flashcard_generation, test_paper_generation |
| Podcast | podcast_dialogue, podcast_dramatize |

## Open Questions

1. **Placeholder descriptions**: `template_definitions.py` stores allowed/required lists, but not human-readable descriptions per placeholder. Need to add a descriptions map (e.g., `language → "Output language for the generated content"`, `question → "The user's question"`)
2. **Default template read-only view**: Should clicking the "default" template in the list open the drawer in read-only mode to show the default content? Or is pre-filling into a new template enough?
3. **Validation UX**: When a required placeholder is missing, show inline error on save, or real-time highlighting?

## Out of Scope

- Per-video template overrides (already partially exists in settings, separate concern)
- Template versioning/history
- Template import/export
- A/B testing between templates
- Autocomplete-style `{` trigger in textareas (possible future enhancement)
