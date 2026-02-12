# Research Summary: Cascading Configuration System Implementation

**Date:** 2026-02-10
**Status:** Research Complete — Ready for Implementation
**Sources:** Codebase exploration, existing architecture docs, brainstorm document

---

## Executive Summary

This repository already has a **comprehensive design document** for a cascading 3-level configuration system (`docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md`). The task system architecture is well-documented, and the codebase is ready for implementation.

### Key Findings

1. **Brainstorm Already Exists** — A detailed cascading config design has been drafted
2. **Task System is Mature** — SSE-based async task system with proper state management is in place
3. **Global Settings Store Exists** — Zustand-based global settings (`useGlobalSettingsStore.ts`)
4. **ContentMetadata is Entity-Based** — Already supports rich metadata with status tracking
5. **No Per-Video Config Yet** — The infrastructure is ready; implementation is the next step

---

## 1. The Cascading Configuration Design (Already Drafted)

Located in: `/docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md`

### Three-Level Hierarchy

```
Per-Task Invocation Overrides (highest priority)
        ↓ falls through if not set
Per-Video Configuration Overrides (backend-persisted)
        ↓ falls through if not set
Global User Defaults (lowest priority)
```

### Why This Design

- **Minimal storage**: Only store explicit overrides, not full configs
- **Auto-propagation**: Changing global defaults affects all non-overridden videos
- **Easy reset**: Delete override to inherit from global
- **Natural mental model**: Matches VS Code, Premiere Pro, Descript patterns

### Config Resolution Algorithm

The brainstorm provides a concrete algorithm using the **nullish coalescing operator** pattern:

```python
def resolveConfig(globalConfig, videoConfig, taskOverrides):
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
        # ... etc for ttsModel, prompts, noteContextMode
    }
```

---

## 2. Task Parameter Matrix (What's Configurable)

From the brainstorm, all 13 task types and their configurable parameters:

| Task Type | Language | LLM Model | TTS Model | Prompts | Other Params |
|-----------|----------|-----------|-----------|---------|-------------|
| `subtitle_generation` | source | - | - | - | - |
| `subtitle_translation` | source + target | yes | - | yes | - |
| `timeline_generation` | source + target | yes | - | yes | learner_profile |
| `video_generation` | source + target | yes | yes | yes | tts_language |
| `voiceover_generation` | target | - | yes | - | voiceover_name |
| `slide_explanation` | source + target | yes | - | yes | learner_profile, context_window |
| `fact_verification` | target | yes | - | yes | - |
| `cheatsheet_generation` | target | yes | - | yes | context_mode, min_criticality, subject_type, target_pages, user_instruction |
| `note_generation` | target | yes | - | yes | context_mode, learner_profile, user_instruction, max_parts |
| `quiz_generation` | target | yes | - | yes | context_mode, min_criticality, subject_type, question_count, user_instruction |
| `video_merge` | - | - | - | - | files |
| `video_import_url` | - | - | - | - | url |
| `pdf_merge` | - | - | - | - | files |

**Key observations:**
- **Language** is relevant to 10 of 13 tasks
- **LLM model** is relevant to 8 tasks
- **TTS model** is relevant to 2 tasks
- **Prompts** are relevant to 8 tasks
- **Other params** (question_count, context_mode, etc.) are task-specific

---

## 3. Global Settings Store (Frontend - Existing)

Location: `/frontend/stores/useGlobalSettingsStore.ts` and `/frontend/stores/types.ts`

### Current Global Settings Structure

```typescript
export interface GlobalSettings {
    // Playback behavior (stays global)
    playback: PlaybackSettings;           // autopause, autoresume, etc.

    // Content-related (will gain per-video overrides)
    language: LanguageSettings;           // original, translated
    ai: AISettings;                       // llmModel, ttsModel, prompts
    note: NoteSettings;                   // contextMode

    // Display/UI (stays global)
    subtitleDisplay: SubtitleDisplaySettings;
    hideSidebars: boolean;
    viewMode: ViewMode;

    // Notifications (stays global)
    notifications: NotificationSettings;

    // Appearance (stays global)
    live2d: Live2DSettings;

    // Learner profile (stays global for now)
    learnerProfile: string;

    // Dictionary (stays global)
    dictionary: DictionarySettings;
}
```

### Implementation Pattern (Zustand)

Uses `zustand` with `persist` middleware for localStorage:

```typescript
export const useGlobalSettingsStore = create<GlobalSettingsStore>()(
    persist(
        (set) => ({
            // State
            ...DEFAULT_GLOBAL_SETTINGS,
            _hydrated: false,

            // Actions
            setOriginalLanguage: (lang) =>
                set((state) => ({
                    language: { ...state.language, original: lang },
                })),
            // ... more setters
        }),
        {
            name: "deeplecture-settings", // localStorage key
            storage: createJSONStorage(...),
        }
    )
);
```

**Key insight:** The setter pattern uses immutable updates (`{ ...state.xxx, key: value }`), which is crucial for Zustand's reactivity.

---

## 4. ContentMetadata Entity (Backend - Existing)

Location: `/src/deeplecture/domain/entities/content.py`

### Current Structure

```python
@dataclass(slots=True)
class ContentMetadata:
    """Core entity representing uploaded content."""

    id: str
    type: ContentType              # "video" or "slide"
    original_filename: str

    # File paths (deprecated)
    source_file: str
    video_file: str | None = None
    pdf_page_count: int | None = None
    timeline_path: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Source info
    source_type: SourceType         # "local", "remote", "youtube", "bilibili"
    source_url: str | None = None

    # Feature statuses (already exist for tracking processing)
    video_status: str
    subtitle_status: str
    enhance_translate_status: str
    timeline_status: str
    notes_status: str

    # Job tracking
    video_job_id: str | None
    subtitle_job_id: str | None
    enhance_translate_job_id: str | None
    timeline_job_id: str | None
```

### Extension Point

**Where to add per-video config:**
- Add a new field: `config_overrides: dict[str, Any] | None = None`
- Or: Create a separate `config_overrides: VideoConfigOverrides` dataclass field

The brainstorm recommends storing only the **overridden keys** (not a full config snapshot).

---

## 5. Task System Architecture (Well-Documented)

Locations:
- `/docs/architecture/task-system-overview.md` (detailed 850-line doc)
- `/docs/architecture/task-state-and-sse.md` (architectural decisions)

### State Machine

```
PENDING → PROCESSING → READY (success)
                    ↘ ERROR (failure)
```

Both READY and ERROR are terminal states (immutable once reached).

### Backend Implementation

**Task Manager** (`/src/infrastructure/workers/task_queue.py`):
- ThreadPoolExecutor for execution
- SQLite WAL mode for concurrent access
- Write-Through persistence (every state change → SQLite)
- Snapshot-based persistence (capture state inside lock, persist outside lock)

**Key architectural decision:** Uses Write-Through + Snapshots instead of Event Sourcing:
- Write-Through: Simpler, direct state persistence
- Snapshots: Avoid holding locks during I/O

### Frontend Implementation

**useTaskStatus Hook** (`/frontend/hooks/useTaskStatus.ts`):
- Native EventSource API for SSE
- Automatic reconnection (handled by browser)
- Maps task events to task state

**useVideoPageState Hook** (`/frontend/hooks/useVideoPageState.ts`):
- Main state container for video page
- Triggers content metadata refresh on task completion
- Separate task status from UI state (important!)

### SSE (Server-Sent Events)

**Pattern: Subscribe-Then-Snapshot**

1. Client subscribes first (registers in EventPublisher)
2. Client queries initial state (task snapshot)
3. Client waits for real-time events

This avoids race condition where task completes between query and subscribe.

### Persistence

- **In-memory dict**: Runtime hot cache (`self._tasks[task_id]`)
- **SQLite**: Durable state (`tasks` table)
- **Initial events factory**: On SSE connect, sends current task snapshots
- **TTL cleanup**: Auto-delete terminal tasks after `ttl_seconds`

---

## 6. Recommended Implementation Path

### Phase 1: Backend (Per-Video Config Storage)

**Step 1: Extend ContentMetadata**

```python
@dataclass(slots=True)
class ContentMetadata:
    # ... existing fields ...

    # New: Per-video config overrides (only non-default values)
    config_overrides: dict[str, Any] = field(default_factory=dict)
```

Or create a dedicated dataclass:

```python
@dataclass(slots=True)
class VideoConfigOverrides:
    """Partial config with only overridden values."""
    source_language: str | None = None
    target_language: str | None = None
    llm_model: str | None = None
    tts_model: str | None = None
    prompts: dict[str, str] | None = None
    note_context_mode: str | None = None
```

**Step 2: Update sqlite_metadata.py**

- Extend schema to persist config overrides (JSON column)
- Update save/load methods to handle new field

**Step 3: Add Config Resolution Service**

```python
class ConfigResolution:
    """Resolves config cascade: global → video → task override."""

    def resolve(
        self,
        global_config: GlobalSettings,
        video_config: VideoConfigOverrides | None,
        task_overrides: dict[str, Any] | None,
    ) -> ResolvedConfig:
        """Apply cascade with nullish coalescing."""
```

### Phase 2: Backend API (GET/PUT /content/{id}/config)

Create new endpoints:

```python
@app.get("/api/content/{content_id}/config")
def get_content_config(content_id: str):
    """Get per-video config overrides (not resolved, just stored overrides)."""

@app.put("/api/content/{content_id}/config")
def update_content_config(content_id: str, overrides: dict):
    """Update per-video config overrides."""
```

### Phase 3: Frontend State (Per-Video Config Store)

Create a new Zustand store:

```typescript
export const useVideoConfigStore = create<VideoConfigStore>()(
    persist(
        (set) => ({
            // Per-video config: content_id -> config_overrides
            configsByVideo: {} as Record<string, Partial<ConfigurableSettings>>,

            setVideoConfig: (contentId, overrides) =>
                set((state) => ({
                    configsByVideo: {
                        ...state.configsByVideo,
                        [contentId]: overrides,
                    },
                })),
        }),
        { name: "deeplecture-video-configs" }
    )
);
```

**Or sync from backend:** Make it a server-side only feature (no frontend localStorage).

### Phase 4: UI Components

**1. Video Settings Panel**
- New sidebar tab or modal
- Shows per-video overrides with "inherited" / "overridden" indicators
- Per-setting "Reset to default" button
- Form to add/edit overrides

**2. Pre-Task Config Popover**
- Shows effective resolved config
- Allows one-time task-level overrides
- Optional expansion (not always shown)

**3. Global Settings Dialog Updates**
- Label content-related settings as "Default for new videos"
- Add help text explaining cascade

---

## 7. Decision Points Already Made (From Brainstorm)

### What Moves to Per-Video (with global defaults)

✅ **Language pair** (source language + target language)
✅ **LLM model selection**
✅ **TTS model selection**
✅ **Prompts per function** (prompt implementation overrides)
✅ **Note context mode** (subtitle/slide/both)

### What Stays Global (user preferences)

✅ **Playback behavior** (autopause, autoswitch, summary threshold)
✅ **Subtitle display** (font size, bottom offset, repeat count)
✅ **Notifications** (toast, browser, title flash)
✅ **Layout** (sidebars, view mode)
✅ **Dictionary** (enabled, interaction mode)
✅ **Live2D appearance** (model path, position, scale)
✅ **Learner profile** (global for now, could be per-video later)

### Storage Decision

✅ **Backend-persisted** (not frontend localStorage)
- Ensures durability across browser clears
- Potential multi-device access
- Config lives with content metadata

### UI Surfaces

1. **Global Settings Dialog** (existing, refined)
2. **Video Settings Panel** (new)
3. **Pre-Task Config Popover** (new)

---

## 8. Codebase Ready Points

### Existing Infrastructure That Supports This

1. **Task System**
   - Already has task_id, content_id, task_type
   - Already tracks status, progress, error
   - Already has useTaskStatus hook with SSE

2. **Content Metadata**
   - Already persisted in SQLite
   - Already has immutable update pattern (`.with_status()`)
   - Ready to add config_overrides field

3. **Global Settings Store**
   - Already has language, ai.llmModel, ai.ttsModel, note.contextMode
   - Zustand pattern is clean and extensible
   - localStorage persistence already in place

4. **API Routing**
   - Clear pattern in `presentation/api/routes/`
   - Can add new `/config` endpoints easily

5. **Frontend State Management**
   - Multiple Zustand stores already in place
   - Can add VideoConfigStore easily
   - useVideoPageState already coordinates refresh logic

### No Major Refactoring Needed

- Global settings stay as-is (become defaults)
- ContentMetadata is easily extendable
- Task system doesn't need changes (receives resolved config)
- Use cases don't need changes (they just receive config at invocation)

---

## 9. Open Questions from Brainstorm (Resolved or Deferred)

| Question | Status | Decision |
|----------|--------|----------|
| Migration strategy for existing videos | Resolved | Inherit everything from global (cascade handles) |
| Per-video config storage format | Deferred | JSON column in SQLite or separate table (implementation choice) |
| Pre-task popover design | Deferred | Collapsible/optional to avoid slowing users |
| Config cloning | Deferred | Nice-to-have for later |
| Learner profile scope | Deferred | Keep global for now, revisit later |
| Task-specific params defaults | Open | Store per-video or only at task invocation? |

---

## 10. File Locations Reference

### Documentation

- **Brainstorm:** `/docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md`
- **Task Architecture:** `/docs/architecture/task-system-overview.md`
- **Task Decisions:** `/docs/architecture/task-state-and-sse.md`

### Backend Code

- **ContentMetadata:** `/src/deeplecture/domain/entities/content.py`
- **Metadata Storage:** `/src/deeplecture/infrastructure/repositories/sqlite_metadata.py`
- **Task Queue:** `/src/deeplecture/infrastructure/workers/task_queue.py`
- **DI Container:** `/src/deeplecture/di/container.py`
- **Config Settings:** `/src/deeplecture/config/settings.py`

### Frontend Code

- **Global Settings Store:** `/frontend/stores/useGlobalSettingsStore.ts`
- **Settings Types:** `/frontend/stores/types.ts`
- **Task Status Hook:** `/frontend/hooks/useTaskStatus.ts`
- **Video Page State:** `/frontend/hooks/useVideoPageState.ts`
- **Settings Dialog:** `/frontend/components/dialogs/SettingsDialog.tsx`

### Test Files

- **Task Types Tests:** `/frontend/lib/__tests__/taskTypes.test.ts`
- **Use Case Tests:** `/tests/unit/use_cases/`

---

## 11. Implementation Sequence Recommendation

1. **Backend First** (Decoupled from UI)
   - Extend ContentMetadata + sqlite_metadata
   - Add ConfigResolution service
   - Add API endpoints: GET/PUT /content/{id}/config

2. **Frontend Store** (Consume new API)
   - Create useVideoConfigStore or fetch from backend
   - Wire it into task invocation

3. **UI** (Present the config)
   - Video Settings Panel
   - Pre-task config popover
   - Settings dialog refinements

4. **Test Coverage**
   - Unit tests for ConfigResolution cascade
   - Integration tests for API endpoints
   - E2E tests for UI flows

5. **Migration** (Optional, if needed)
   - Script to copy existing global settings to video configs (if desired)
   - Or simply use defaults (cascade handles it)

---

## Summary

The groundwork is solid:

- ✅ Detailed design document already exists
- ✅ Task system is mature and well-documented
- ✅ Global settings store is clean and extensible
- ✅ ContentMetadata is ready to extend
- ✅ Backend API patterns are clear
- ✅ Frontend Zustand pattern is established

**Next step:** Implementation following the brainstorm design, starting with backend infrastructure (extend ContentMetadata, add ConfigResolution service, create API endpoints), then wiring frontend stores and UI components.
