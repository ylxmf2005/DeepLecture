# Brainstorm: Cascading Task Configuration

**Date:** 2026-02-10
**Status:** Draft
**Author:** User + AI collaborative brainstorm

---

## What We're Building

A **3-level cascading configuration system** that separates global user preferences from per-video content settings and per-task invocation overrides. This eliminates the need for users to manually change global settings before triggering tasks on different videos.

### The Problem Today

All content-related parameters (language pair, LLM model, TTS model, prompts, note context mode) live in the global settings store. When a user works with videos in different languages or wants different AI models for different content, they must:

1. Open Settings dialog
2. Change the relevant settings
3. Trigger the task
4. Repeat for the next video

This is tedious, error-prone, and doesn't scale.

### The Solution

A 3-level configuration hierarchy with cascading overrides:

```
Per-Task Invocation Overrides (highest priority)
        ↓ falls through if not set
Per-Video Configuration Overrides (backend-persisted)
        ↓ falls through if not set
Global User Defaults (lowest priority)
```

Each level stores only its **explicit overrides** — not full configs. Resolution merges all three levels, with higher priority winning. If a video doesn't override `llm_model`, it inherits from global. If a task invocation doesn't specify it, it inherits from the video config.

---

## Why This Approach

**Cascading Overrides** was chosen over Full Snapshots and Template-Based configs because:

1. **Minimal storage** — Only store what's explicitly different from defaults
2. **Auto-propagation** — Changing a global default immediately affects all videos that haven't overridden that setting
3. **Easy "reset to default"** — Just delete the override; the global value takes over
4. **Natural mental model** — Same pattern as CSS cascading, VS Code settings (User → Workspace → Folder), or git config (system → global → local)

---

## Key Decisions

### Decision 1: Configuration Scoping

**What stays global (user preferences):**
- Playback behavior (autopause, autoswitch, summary threshold)
- Subtitle display (font size, bottom offset, repeat count)
- Notifications (toast, browser, title flash)
- Layout (sidebars, view mode)
- Dictionary (enabled, interaction mode)
- Live2D appearance (model path, position, scale)
- Learner profile

**What moves to per-video (with global defaults):**
- Language pair (source language + target language)
- LLM model selection
- TTS model selection
- Prompts per function (prompt implementation overrides)
- Note context mode (subtitle/slide/both)
- Live2D sync-with-video (content behavior, not appearance)

### Decision 2: 3-Level Hierarchy

```
Level 1: Global Defaults (useGlobalSettingsStore, persisted in localStorage)
  → User's preferred defaults for all videos

Level 2: Per-Video Config (backend-persisted alongside content metadata)
  → Overrides for a specific video (e.g., "this video is in Japanese")
  → Stored as partial object: only keys that differ from global
  → Accessed via new API: GET/PUT /content/{id}/config

Level 3: Per-Task Invocation (ephemeral, passed at trigger time)
  → One-time overrides for a specific task run
  → Not persisted — lives only in the API request
  → UI: "Configure & Run" popover before triggering a task
```

### Decision 3: Backend Persistence for Per-Video Config

Per-video configuration is persisted on the **backend** (alongside content metadata), not in frontend localStorage. This ensures:
- Durability across browser clears
- Potential multi-device access
- Config lives with the content it belongs to

### Decision 4: Two UI Surfaces

1. **Global Settings Dialog** (existing, refined)
   - Keeps all user preference settings
   - Content-related settings become "Default for new videos"
   - Clear labeling: "These are your defaults. Individual videos can override."

2. **Video Settings Panel** (new)
   - Accessible from the video page (gear icon or settings tab)
   - Shows per-video overrides with clear "inherited" vs "overridden" indicators
   - Each setting shows: current effective value + source (global / video override)
   - "Reset to default" button per setting

3. **Pre-Task Config Popover** (new)
   - Appears when user clicks a "Generate" button (optional expansion)
   - Shows effective config for this task (resolved from all 3 levels)
   - Allows one-time tweaks before execution
   - Does NOT persist — only affects this invocation

---

## Task Type Parameter Matrix

All 13 task types and their configurable parameters:

| Task Type | Language | LLM Model | TTS Model | Prompts | Other Params |
|-----------|----------|-----------|-----------|---------|-------------|
| `subtitle_generation` | source | - | - | - | - |
| `subtitle_translation` | source + target | yes | - | yes | - |
| `timeline_generation` | source + target | yes | - | yes | learner_profile |
| `video_generation` (slides) | source + target | yes | yes | yes | tts_language |
| `voiceover_generation` | target | - | yes | - | voiceover_name |
| `slide_explanation` | source + target | yes | - | yes | learner_profile, context_window |
| `fact_verification` | target | yes | - | yes | - |
| `cheatsheet_generation` | target | yes | - | yes | context_mode, min_criticality, subject_type, target_pages, user_instruction |
| `note_generation` | target | yes | - | yes | context_mode, learner_profile, user_instruction, max_parts |
| `quiz_generation` | target | yes | - | yes | context_mode, min_criticality, subject_type, question_count, user_instruction |
| `video_merge` | - | - | - | - | files |
| `video_import_url` | - | - | - | - | url |
| `pdf_merge` | - | - | - | - | files |

**Observations:**
- **Language** is relevant to 10 of 13 tasks (all except merge/import)
- **LLM model** is relevant to 8 tasks (all AI-generation tasks)
- **TTS model** is relevant to 2 tasks (voiceover + slide video)
- **Prompts** are relevant to 8 tasks (same as LLM model)
- **Other params** (context_mode, question_count, etc.) are task-specific — these belong in the pre-task config popover

---

## Config Resolution Algorithm

```
function resolveConfig(globalConfig, videoConfig, taskOverrides) {
  // Per-video config: only overridden keys
  // taskOverrides: only explicitly set keys

  return {
    sourceLanguage: taskOverrides.sourceLanguage
      ?? videoConfig.sourceLanguage
      ?? globalConfig.language.original,

    targetLanguage: taskOverrides.targetLanguage
      ?? videoConfig.targetLanguage
      ?? globalConfig.language.translated,

    llmModel: taskOverrides.llmModel
      ?? videoConfig.llmModel
      ?? globalConfig.ai.llmModel,

    ttsModel: taskOverrides.ttsModel
      ?? videoConfig.ttsModel
      ?? globalConfig.ai.ttsModel,

    prompts: mergePrompts(
      globalConfig.ai.prompts,
      videoConfig.prompts,
      taskOverrides.prompts
    ),

    noteContextMode: taskOverrides.noteContextMode
      ?? videoConfig.noteContextMode
      ?? globalConfig.note.contextMode,
  }
}
```

---

## Open Questions

1. **Migration strategy** — How do we handle existing videos that have no per-video config? Answer: They inherit everything from global (the cascade handles this naturally).

2. **Per-video config storage format** — JSON file next to content metadata? New SQLite table? New field in existing metadata?

3. **Pre-task popover design** — Should every "Generate" button show the popover, or should it be an optional expansion (click to expand advanced options)? Recommendation: collapsible/optional to avoid slowing down users who just want defaults.

4. **Config cloning** — Should users be able to "copy config from another video"? Nice-to-have for later.

5. **Learner profile scope** — Currently global. Should it also be per-video? It could vary (e.g., studying Chinese as a beginner but English at advanced level). But keeping it global is simpler for now.

6. **Task-specific params** — Parameters like `question_count`, `context_mode`, `min_criticality` are task-specific, not shared across tasks. Should these have per-video defaults too, or only exist at task invocation time?

---

## Industry Reference

| Product | Config Model |
|---------|-------------|
| VS Code | User → Workspace → Folder settings (3-level cascade) |
| DaVinci Resolve | System Preferences → Project Settings → Timeline/Clip Settings |
| Premiere Pro | Application Preferences → Sequence Settings → Clip Properties |
| Descript | Account Settings → Project Settings |
| Notion | Workspace → Page/Database properties |

Our 3-level model (Global → Video → Task) aligns with **VS Code's approach** — the most developer-friendly pattern.

---

## Scope Boundaries

**In scope:**
- Config hierarchy definition and resolution logic
- Per-video config backend storage and API
- Video Settings Panel UI
- Pre-task config popover UI
- Migration of content-related settings from global-only to cascading
- Global Settings dialog updates (labeling as "defaults")

**Out of scope (future):**
- Config templates / presets
- Bulk config operations (apply to multiple videos)
- Config import/export
- Per-section/per-slide config (sub-video granularity)
