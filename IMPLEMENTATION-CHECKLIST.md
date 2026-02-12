# Cascading Configuration System - Implementation Checklist

## Overview

A 3-level configuration hierarchy that eliminates manual setting changes between videos:

```
Task Invocation Level (ephemeral)
    ↓ falls through if undefined
Per-Video Level (backend-persisted)
    ↓ falls through if undefined
Global User Defaults Level (localStorage)
```

---

## Backend Implementation Checklist

### Phase 1: Domain Layer

- [ ] **Extend ContentMetadata** (`src/deeplecture/domain/entities/content.py`)
  - [ ] Add `config_overrides: dict[str, Any] = field(default_factory=dict)` field
  - [ ] OR create `VideoConfigOverrides` dataclass for type safety
  - [ ] Add method: `with_config_overrides(overrides: dict) -> ContentMetadata`

- [ ] **Create ConfigResolution Service** (`src/deeplecture/use_cases/config_resolution.py`)
  - [ ] `resolve(global_config, video_config, task_overrides) -> ResolvedConfig`
  - [ ] Implement cascade logic with nullish coalescing pattern
  - [ ] Handle all 13 task types' configurable parameters

### Phase 2: Infrastructure Layer

- [ ] **Update SQLite Schema** (`src/deeplecture/infrastructure/repositories/sqlite_metadata.py`)
  - [ ] Add `config_overrides TEXT` column to `content_metadata` table
  - [ ] Update save method: persist config_overrides as JSON
  - [ ] Update load method: deserialize config_overrides

- [ ] **Create Config Storage Interface** (`src/deeplecture/use_cases/interfaces/config.py`)
  - [ ] Define contract for getting/saving video configs

### Phase 3: API Layer

- [ ] **Add Config Endpoints** (`src/deeplecture/presentation/api/routes/config.py` - NEW)
  - [ ] `GET /api/content/{content_id}/config` - Get video overrides only
  - [ ] `PUT /api/content/{content_id}/config` - Update video overrides
  - [ ] `DELETE /api/content/{content_id}/config` - Reset to global defaults
  - [ ] `GET /api/content/{content_id}/config/resolved` - Get resolved config (optional, for testing)

- [ ] **Update Use Cases** (all task-related: subtitle, timeline, note, etc.)
  - [ ] Accept `config_overrides: dict | None` parameter in API handlers
  - [ ] Pass to ConfigResolution service
  - [ ] Forward resolved config to task callable

---

## Frontend Implementation Checklist

### Phase 1: State Management

- [ ] **Create Video Config Store** (`frontend/stores/useVideoConfigStore.ts` - NEW)
  - [ ] Define `VideoConfigOverrides` interface (mirrors backend)
  - [ ] Create Zustand store: `useVideoConfigStore`
  - [ ] Implement actions:
    - [ ] `setVideoConfig(contentId, overrides)`
    - [ ] `resetVideoConfig(contentId)`
    - [ ] `getVideoConfig(contentId)`
  - [ ] Option A: Persist to localStorage
  - [ ] Option B: Fetch from backend on demand (recommended)

- [ ] **Update Global Settings Store** (`frontend/stores/useGlobalSettingsStore.ts`)
  - [ ] NO CHANGES to structure (it becomes the defaults)
  - [ ] Update documentation: clarify these are "defaults for new videos"
  - [ ] Consider adding note: "Individual videos can override these"

- [ ] **Create Config Resolution Hook** (`frontend/hooks/useConfigResolution.ts` - NEW)
  - [ ] Mirror backend resolution logic
  - [ ] Combine: global settings + video overrides + task overrides
  - [ ] Return resolved config for display/use

### Phase 2: UI Components

- [ ] **Create Video Settings Panel** (`frontend/components/video/VideoSettingsPanel.tsx` - NEW)
  - [ ] Display current video overrides
  - [ ] For each configurable setting:
    - [ ] Show current effective value
    - [ ] Show source: "Inherited from global" or "Overridden"
    - [ ] Edit field with current value
    - [ ] "Reset to default" button
  - [ ] Submit button to save changes
  - [ ] Add to video page (new tab or modal)

- [ ] **Create Pre-Task Config Popover** (`frontend/components/video/PreTaskConfigPopover.tsx` - NEW)
  - [ ] Show resolved config for the specific task
  - [ ] Display which settings are overridden at each level
  - [ ] Allow one-time overrides (ephemeral, not persisted)
  - [ ] Optional: Collapsible/expandable to avoid clutter
  - [ ] "Generate" button to submit with overrides

- [ ] **Update Settings Dialog** (`frontend/components/dialogs/SettingsDialog.tsx`)
  - [ ] Content-related section → label as "Default for new videos"
  - [ ] Add help text: "These defaults apply to all new videos. Individual videos can override these."
  - [ ] Reorganize tabs if needed for clarity

### Phase 3: Integration

- [ ] **Wire Video Config into Task Invocation** (`frontend/hooks/handlers/use*Handlers.ts`)
  - [ ] Example: `useContentHandlers.ts`
  - [ ] Before submitting task: resolve config
  - [ ] Include in API request payload: `config_overrides`

- [ ] **Update Task Submission** (`frontend/lib/api/*.ts`)
  - [ ] All task generation endpoints accept optional `config_overrides` param
  - [ ] Example: `generateSubtitles(videoId, configOverrides?)`

- [ ] **Update useVideoPageState** (`frontend/hooks/useVideoPageState.ts`)
  - [ ] On video change: fetch/load per-video config
  - [ ] Store in local state for quick access
  - [ ] Pass to task invocation

---

## Testing Checklist

### Backend Tests

- [ ] **Unit: ConfigResolution**
  - [ ] Nullish coalescing for each parameter
  - [ ] Missing global fallback to null
  - [ ] Task override beats video override beats global
  - [ ] Merges prompts correctly (not complete replacement)

- [ ] **Integration: Config API**
  - [ ] GET /config returns stored overrides
  - [ ] PUT /config updates overrides
  - [ ] DELETE /config clears overrides
  - [ ] Invalid JSON rejected
  - [ ] Non-existent content_id returns 404

- [ ] **Integration: Task Submission with Config**
  - [ ] Task callable receives resolved config
  - [ ] LLM provider uses correct model
  - [ ] TTS provider uses correct model
  - [ ] Prompts are merged correctly

### Frontend Tests

- [ ] **Unit: useConfigResolution Hook**
  - [ ] Cascade logic matches backend
  - [ ] Handles missing values at each level
  - [ ] Updates reactively when config changes

- [ ] **Integration: Video Settings Panel**
  - [ ] Fetches current video config
  - [ ] Displays with "inherited" indicator
  - [ ] Can edit each field
  - [ ] "Reset to default" removes override
  - [ ] Save persists to backend

- [ ] **E2E: Task with Per-Video Config**
  - [ ] User sets per-video language
  - [ ] User triggers task
  - [ ] Config popover shows correct language
  - [ ] Task uses correct language
  - [ ] Subtitle/output is in correct language

- [ ] **E2E: Multiple Videos with Different Configs**
  - [ ] Video A set to Japanese
  - [ ] Video B set to Spanish
  - [ ] Switch between them
  - [ ] UI shows correct config for each
  - [ ] Tasks use correct config for each

---

## Data Flow Diagrams

### Current Flow (Before Implementation)

```
User clicks "Generate Subtitles"
    ↓
API call: POST /api/subtitle/generate { videoId }
    ↓
Backend receives, uses global settings only
    ↓
Task executes with hardcoded global language/model
```

### New Flow (After Implementation)

```
User clicks "Generate Subtitles"
    ↓
[Optional: Pre-task config popover shows resolved config]
    ↓
API call: POST /api/subtitle/generate { videoId, configOverrides }
    ↓
Backend resolves: video config + task overrides, falls through to global
    ↓
ConfigResolution.resolve() returns merged config
    ↓
Task callable receives resolved config
    ↓
Whisper transcribes with resolved language
    ↓
Subtitle uses resolved language
```

---

## Frontend Component Hierarchy

```
VideoPageClient
├── VideoPlayer
├── TabContentRenderer
│   ├── SubtitlePanel
│   ├── TimelinePanel
│   ├── CheatsheetTab
│   ├── VideoSettingsPanel [NEW]
│   │   ├── ConfigOverrideField (language)
│   │   ├── ConfigOverrideField (llm_model)
│   │   ├── ConfigOverrideField (tts_model)
│   │   └── ConfigOverrideField (note_context_mode)
│   └── ...
├── VideoActions
│   ├── GenerateButton [UPDATED]
│   │   └── PreTaskConfigPopover [NEW]
│   └── ...
└── SettingsDialog [UPDATED]
    └── Tabs → Player / AI / ...
        └── "[These are defaults for new videos]"
```

---

## Implementation Timeline

### Week 1: Backend Infrastructure
- Day 1-2: Extend ContentMetadata, update schema
- Day 3-4: Create ConfigResolution service
- Day 5: Create Config API endpoints

### Week 2: Frontend Store & Integration
- Day 1-2: Create useVideoConfigStore, useConfigResolution hook
- Day 3-4: Wire into task submission handlers
- Day 5: Update useVideoPageState

### Week 3: UI & Polish
- Day 1-2: Video Settings Panel component
- Day 3: Pre-task config popover
- Day 4: Settings Dialog refinements
- Day 5: E2E testing & bug fixes

### Week 4: Testing & Deployment
- Day 1-2: Unit test suite
- Day 3: Integration tests
- Day 4: E2E tests
- Day 5: Documentation & code review

---

## Known Considerations

### Task-Specific Parameters

Parameters like `question_count`, `context_mode`, `min_criticality` are **task-specific**, not shared:
- **Option A:** Only allow at task invocation (pre-task popover)
- **Option B:** Also support per-video defaults

Recommendation: **Option A** (simpler for now, can revisit if needed)

### Learner Profile

Currently **global only**. Could be per-video later if learner studies different subjects at different levels.

### Prompt Merging

When resolving prompts:
- Don't replace entire prompt dict
- Merge: global prompts + video overrides + task overrides
- Task override beats video override beats global

### Migration

For existing videos with no per-video config:
- Simply inherit from global (cascade handles)
- No migration script needed
- Users can set per-video config anytime

### Browser Clears

Since per-video config is **backend-persisted**, users clearing localStorage won't lose it (unlike global settings fallback).

---

## References

- **Design Doc:** `/docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md`
- **Task Architecture:** `/docs/architecture/task-system-overview.md`
- **ContentMetadata:** `/src/deeplecture/domain/entities/content.py`
- **Global Settings:** `/frontend/stores/useGlobalSettingsStore.ts`
- **Task System:** `/src/deeplecture/infrastructure/workers/task_queue.py`
