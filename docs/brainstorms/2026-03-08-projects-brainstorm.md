# Projects (Folder-based Course Organization)

**Date:** 2026-03-08
**Status:** Brainstorm

## What We're Building

A "Projects" feature that lets users organize their content (videos and slides) into named groups, similar to folders. This addresses the pain point of a flat, ever-growing content list with no way to categorize items by course or topic.

### Core Behavior

- Each content item can belong to **at most one** project (one-to-many relationship)
- Projects are **optional** — ungrouped content remains visible outside of any project
- Content is sorted by creation time within projects (no custom ordering)

### Project Properties

| Property    | Type     | Required | Notes                          |
|-------------|----------|----------|--------------------------------|
| id          | UUID     | auto     | System-generated               |
| name        | string   | yes      | User-facing display name       |
| description | string   | no       | Optional short summary         |
| color       | string   | no       | Hex color for visual identity  |
| icon        | string   | no       | Icon identifier (emoji or key) |
| created_at  | datetime | auto     | UTC timestamp                  |
| updated_at  | datetime | auto     | UTC timestamp                  |

### Content-Project Association

- `ContentMetadata` gains a nullable `project_id` field
- `project_id = NULL` means "ungrouped"

## Why This Approach

**One-to-many (folder model) over many-to-many (tag model):**
- Simpler mental model — users think in "folders", not "tags"
- Simpler data model — single FK column on `content_metadata` instead of a junction table
- Matches the user's stated goal of "course folders"

**Optional grouping over forced grouping:**
- No migration burden for existing content — all current items start as ungrouped
- Users can gradually organize at their own pace
- A "default project" would add artificial structure

**Sidebar filter over separate pages:**
- One-click project switching without page navigation
- Content grid stays in view — familiar layout preserved
- "All" and "Ungrouped" pseudo-entries let users see everything or just loose items
- Sidebar can collapse for users who don't use projects

## UI Design

### Homepage Layout (Sidebar + Content Grid)

```
+-------------+------------------------------+
| [<] Projects|  Course Subtitle & Notes     |
|             |                              |
|  > All      |  +--------+ +--------+      |
|  * LinAlg   |  | vid 1  | | vid 2  |      |
|  o Acctg    |  +--------+ +--------+      |
|  o Ungroup  |  +--------+                 |
|             |  | vid 3  |                 |
|  [+ New]    |  +--------+                 |
+-------------+------------------------------+
```

- Sidebar is collapsible (persisted in localStorage)
- "All" shows every content item regardless of project
- "Ungrouped" shows items with `project_id = NULL`
- Active project is highlighted; click to filter
- "[+ New]" opens a create-project dialog

### Upload Flow

- Upload dialog gains an optional "Project" dropdown
- Defaults to the currently selected project in the sidebar (or "None")
- Content can be reassigned to a different project later via context menu

### Content Card Actions

- Right-click or hover menu gains "Move to Project..." option
- Opens a picker listing all projects + "Remove from project"

## Key Decisions

1. **Storage:** New `projects` table in the existing `metadata.db` SQLite database; `project_id` FK column added to `content_metadata` via `_ensure_columns()`
2. **API:** New `/api/projects` CRUD endpoints; existing `/api/content/list` gains optional `?project_id=` query parameter
3. **No nesting:** Projects are flat (no sub-projects/sub-folders) — keeps it simple
4. **No project-level config:** Projects are purely organizational; per-content config remains on individual items

## Open Questions

1. **Bulk operations:** Should users be able to multi-select content and move them to a project in one action? (Nice-to-have, can defer)
2. **Project deletion:** When a project is deleted, should its content become ungrouped or also be deleted? (Likely: become ungrouped)
3. **Sidebar on mobile:** Should the sidebar become a dropdown or slide-over on small screens?
4. **Project ordering:** Should users be able to reorder projects in the sidebar, or sort alphabetically?
