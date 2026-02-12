---
title: "Unified Settings Dialog with Full Per-Video Override Support"
type: feat
date: 2026-02-12
supersedes: docs/plans/2026-02-10-feat-cascading-task-configuration-plan.md
---

# Unified Settings Dialog with Full Per-Video Override Support

## Overview

Merge the global SettingsDialog and per-video VideoConfigPanel into a **single unified settings dialog** with a VS Code-style scope switcher (`🌐 Global` / `🎬 This Video`). Extend per-video overrides from the current 7 task-relevant fields to **all ~30 settings fields** — including player, subtitle display, notifications, Live2D, dictionary, and view mode.

This reverses the original scoping decision (brainstorm 2026-02-10) that limited per-video config to "task-relevant" fields only. The rationale: users benefit from per-video player preferences (e.g., auto-pause for lectures, not for music; larger subtitles for foreign-language content) and a single settings entry point eliminates the "where do I change this?" confusion.

## Problem Statement

1. **Two settings surfaces** — users must know whether to open SettingsDialog (global) or VideoConfigPanel (per-video). Cognitive overhead.
2. **Limited per-video scope** — only 7 fields (language, AI models, prompts, learner profile, note context mode) can be overridden per-video. Player behavior, subtitle display, Live2D, dictionary, notifications are forced global.
3. **Use cases for per-video UI overrides exist** — e.g., subtitle font size varies by language complexity; auto-pause behavior differs for lecture vs. entertainment; dictionary on for language learning content, off for native language content.

## Proposed Solution

### Architecture: DeepPartial Cascading

```
Per-Video Config (sparse, backend-persisted)
        ↓ falls through if not set
Global Defaults (localStorage, Zustand)
        ↓
Resolved Settings (fully populated, read-only)
```

Per-video config mirrors the `GlobalSettings` shape as a `DeepPartial`:

```typescript
// frontend/stores/types.ts
type PerVideoConfig = DeepPartial<GlobalSettings>;

// Resolution: simple recursive merge with ?? at each leaf
type ResolvedSettings = Readonly<GlobalSettings>;
```

### Architecture: Context-based Injection

```
                    ┌─────────────────────────────┐
                    │       Home Page              │
                    │  (no VideoConfigProvider)    │
                    │                              │
                    │  usePlaybackSettings()       │
                    │  → returns global directly   │
                    └─────────────────────────────┘

                    ┌─────────────────────────────┐
                    │       Video Page             │
                    │  <VideoConfigProvider id={x}>│
                    │                              │
                    │  usePlaybackSettings()       │
                    │  → returns merged(global,    │
                    │         perVideo)            │
                    └─────────────────────────────┘
```

**Key insight:** Existing selector hooks (`usePlaybackSettings`, `useLive2dSettings`, etc.) become scope-aware via React Context. Components don't need to change — they automatically get resolved values when inside a `VideoConfigProvider`.

---

## Technical Approach

### Phase 1: Type System & Resolution (Foundation)

#### 1.1 Expand `PerVideoConfig` type

**File:** `frontend/stores/types.ts`

```typescript
// Utility type
type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

// Per-video overrides — same shape as GlobalSettings, all optional
type PerVideoConfig = DeepPartial<GlobalSettings>;

// Backward compat: map old flat TaskConfigShape to new nested shape
// (migration helper, used once during transition)

// Keep TaskConfigShape for backend API request bodies (task execution)
// PerVideoConfig is the storage/UI shape; TaskConfigShape is the API shape
```

**Decision:** `PerVideoConfig` uses the **same nested structure** as `GlobalSettings`. This makes resolution a generic deep merge rather than manual field-by-field mapping. The old flat `TaskConfigShape` is retained for API request bodies (backend tasks only care about language/model/prompts).

#### 1.2 Generic deep merge resolution

**File:** `frontend/lib/configResolution.ts` (new, extracted from hook)

```typescript
/**
 * Recursively merge per-video overrides onto global defaults.
 * Per-video values win; undefined/missing falls through to global.
 * Prompts merge at key level (not replace).
 */
export function resolveSettings(
  global: GlobalSettings,
  perVideo: PerVideoConfig | null,
): GlobalSettings {
  if (!perVideo) return global;
  return deepMergeWithDefaults(global, perVideo);
}

// Also export: isFieldOverridden(perVideo, path) → boolean
// path like "playback.autoPauseOnLeave" or "ai.llmModel"
```

#### 1.3 Update config resolution tests

**File:** `frontend/lib/__tests__/configResolution.test.ts`

Expand from 7 test cases to cover:
- All nested groups (playback, subtitleDisplay, notifications, live2d, dictionary)
- Partial group overrides (only some fields in a group overridden)
- Prompts key-level merge (preserved)
- Standalone fields (hideSidebars, viewMode, learnerProfile)
- Backward compatibility with old flat format
- Empty per-video config returns global unchanged

---

### Phase 2: React Context for Scope-Aware Hooks

#### 2.1 VideoConfigProvider

**File:** `frontend/contexts/VideoConfigContext.tsx` (new)

```typescript
interface VideoConfigContextValue {
  /** Sparse per-video overrides */
  overrides: PerVideoConfig;
  /** Fully resolved settings (global + per-video merged) */
  resolved: GlobalSettings;
  /** Check if a specific field path is overridden */
  isOverridden: (path: string) => boolean;
  /** Set per-video overrides (debounced save) */
  setOverrides: (updates: PerVideoConfig) => void;
  /** Clear a specific field override */
  clearOverride: (path: string) => void;
  /** Clear all overrides */
  clearAllOverrides: () => void;
  /** Count of overridden leaf fields */
  overrideCount: number;
  /** Loading state */
  loading: boolean;
}
```

Wraps the video page. On mount:
- Fetches per-video config from backend
- Subscribes to `useGlobalSettingsStore` changes
- Recomputes `resolved` whenever global or per-video changes
- Debounced PUT on override changes (800ms, existing pattern)

#### 2.2 Make selector hooks scope-aware

**File:** `frontend/stores/useGlobalSettingsStore.ts`

Modify existing selector hooks to check for `VideoConfigContext`:

```typescript
// Before (global only):
export const usePlaybackSettings = () =>
  useGlobalSettingsStore((s) => s.playback);

// After (scope-aware):
export function usePlaybackSettings(): PlaybackSettings {
  const videoCtx = useContext(VideoConfigContext);
  const global = useGlobalSettingsStore((s) => s.playback);
  if (videoCtx) return videoCtx.resolved.playback;
  return global;
}
```

Apply this pattern to ALL selector hooks:
- `usePlaybackSettings` → `resolved.playback`
- `useLanguageSettings` → `resolved.language`
- `useSubtitleDisplaySettings` (if exists) → `resolved.subtitleDisplay`
- `useNotificationSettings` → `resolved.notifications`
- `useLive2dSettings` → `resolved.live2d`
- `useNoteSettings` → `resolved.note`
- `useAISettings` → `resolved.ai`
- `useDictionarySettings` → `resolved.dictionary`
- `useLearnerProfile` → `resolved.learnerProfile`
- `useViewMode` → `resolved.viewMode`

**Zero breaking changes** — all existing consumers transparently get resolved values.

#### 2.3 Update `ai-overrides.ts` chokepoint

**File:** `frontend/lib/api/ai-overrides.ts`

The module-level `currentVideoConfig` pattern remains, but now reads from the full `PerVideoConfig` instead of the old flat `TaskConfigShape`. The `getAIOverrides()`, `getLanguageOverrides()`, etc. functions continue to extract the AI-relevant fields for API request bodies.

```typescript
// setCurrentVideoConfig now accepts PerVideoConfig (nested)
// getAIOverrides() extracts: perVideo.ai?.llmModel, perVideo.ai?.ttsModel, etc.
// getLanguageOverrides() extracts: perVideo.language?.original, perVideo.language?.translated
```

#### 2.4 Wire VideoConfigProvider into video page

**File:** `frontend/app/video/[id]/VideoPageClient.tsx`

```tsx
<VideoConfigProvider contentId={contentId}>
  {/* existing video page content */}
</VideoConfigProvider>
```

Replace the current `useContentConfig` hook usage with the new context provider.

---

### Phase 3: Unified Settings UI

#### 3.1 Add scope switcher to SettingsDialog

**File:** `frontend/components/dialogs/SettingsDialog.tsx`

- Add `scope` state: `'global' | 'video'`
- Add `ScopeSwitcher` component in header (from demo)
- Pass `scope` to all tab components
- "This Video" tab disabled when no video context (opened from home page)
- "Reset All (N)" button visible in video scope when overrides exist
- Video name shown in header subtitle when in video scope

**Props change:**
```typescript
interface SettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  video?: ContentItem;          // existing
  initialScope?: 'global' | 'video';  // new: pre-select scope
}
```

#### 3.2 Make each settings tab scope-aware

Each tab receives a new prop interface:

```typescript
interface ScopeAwareTabProps {
  scope: 'global' | 'video';
  // When scope === 'video', these are available:
  videoConfig?: VideoConfigContextValue;
}
```

**Tab behavior by scope:**

| Scope | Read from | Write to | UI indicators |
|-------|-----------|----------|---------------|
| `global` | `useGlobalSettingsStore` | `store.set*()` actions | None (current behavior) |
| `video` | `videoConfig.resolved` | `videoConfig.setOverrides()` | Override badge + Reset button per field |

Each field wrapper uses the `FieldRow` pattern from the demo:
- Show "Override" badge when field is overridden
- Show "Reset" button to clear individual override
- Placeholder "Use global default" for unset per-video fields

#### 3.3 Scope-aware field controls

**File:** `frontend/components/dialogs/settings/ScopeAwareField.tsx` (new)

Generalized version of `OverridableSelect` / `OverridableTextarea` from VideoConfigPanel:

```typescript
interface ScopeAwareFieldProps {
  label: string;
  description?: string;
  scope: 'global' | 'video';
  /** Dot path like "playback.autoPauseOnLeave" */
  fieldPath: string;
  children: (props: {
    value: any;
    onChange: (value: any) => void;
    isOverridden: boolean;
  }) => React.ReactNode;
}
```

Renders:
- Label with optional Override badge
- Reset button (video scope, overridden only)
- Render-prop children for the actual control (select, toggle, textarea, slider)

#### 3.4 Update individual tab components

Files to modify:
- `frontend/components/dialogs/settings/GeneralTab.tsx` — add scope support to language + learner profile
- `frontend/components/dialogs/settings/ModelTab.tsx` — add scope support to LLM + TTS model selects
- `frontend/components/dialogs/settings/PlayerTab.tsx` — add scope support to subtitle display + focus mode toggles
- `frontend/components/dialogs/settings/FunctionsTab.tsx` — add scope support to note context, dictionary, smart skip
- `frontend/components/dialogs/settings/PromptTab.tsx` — add scope support to prompt templates
- (Notifications tab, Live2D tab — same pattern)

**Each tab is modified, not rewritten.** Add `scope` prop, wrap each field control with `ScopeAwareField`, keep existing UI structure.

#### 3.5 Delete VideoConfigPanel

**File:** `frontend/components/dialogs/VideoConfigPanel.tsx` → DELETE

Remove all references:
- `VideoPageClient.tsx`: replace VideoConfigPanel trigger with unified SettingsDialog trigger (scope='video')
- Remove `OverridableSelect` / `OverridableTextarea` (replaced by `ScopeAwareField`)

#### 3.6 Update settings dialog entry points

- **Header gear icon** (home page): opens SettingsDialog with `initialScope='global'`, "This Video" tab disabled
- **Video page gear icon**: opens SettingsDialog with `initialScope='video'`
- **Keyboard shortcut** (if any): opens with scope based on current page context

---

### Phase 4: Backend Expansion

#### 4.1 Expand ContentConfig entity

**File:** `src/deeplecture/domain/entities/config.py`

Two approaches:

**Option A (Recommended): Nested dict with typed access**

```python
@dataclass(frozen=True)
class ContentConfig:
    """Sparse per-video configuration overrides.

    Mirrors the frontend GlobalSettings shape. All fields optional.
    Only stores explicit overrides; absent = inherit from global.
    """
    # Existing fields (backward compatible)
    source_language: str | None = None
    target_language: str | None = None
    llm_model: str | None = None
    tts_model: str | None = None
    prompts: dict[str, str] | None = None
    learner_profile: str | None = None
    note_context_mode: NoteContextMode | None = None

    # Playback
    auto_pause_on_leave: bool | None = None
    auto_resume_on_return: bool | None = None
    auto_switch_subtitles_on_leave: bool | None = None
    auto_switch_voiceover_on_leave: bool | None = None
    voiceover_auto_switch_threshold_ms: int | None = None
    summary_threshold_seconds: int | None = None
    subtitle_context_window_seconds: int | None = None
    subtitle_repeat_count: int | None = None

    # Subtitle display
    subtitle_font_size: int | None = None
    subtitle_bottom_offset: int | None = None

    # Notifications
    browser_notifications_enabled: bool | None = None
    toast_notifications_enabled: bool | None = None
    title_flash_enabled: bool | None = None

    # Live2D
    live2d_enabled: bool | None = None
    live2d_model_path: str | None = None
    live2d_model_position: str | None = None   # "left" | "right"
    live2d_model_scale: float | None = None
    live2d_sync_with_video_audio: bool | None = None

    # Dictionary
    dictionary_enabled: bool | None = None
    dictionary_interaction_mode: str | None = None  # "hover" | "click"

    # View
    hide_sidebars: bool | None = None
    view_mode: str | None = None  # "normal" | "widescreen" | ...
```

The `to_sparse_dict()` and `from_dict()` methods already handle this pattern — only non-None fields are serialized. `from_dict()` ignores unknown keys (forward compatible).

**Why flat, not nested on the backend:** The backend is a persistence layer. It doesn't need group hierarchy — that's a frontend UI concern. Flat fields are simpler to validate and query. The frontend maps flat ↔ nested in the API client.

#### 4.2 Update API validation

**File:** `src/deeplecture/presentation/api/routes/content_config.py`

Add validation rules for new fields:
- Boolean fields: must be `bool` if present
- Integer fields: must be `int`, with min/max bounds (e.g., font_size 8–72, threshold 0–60000)
- String enum fields: must be in allowed values (view_mode, interaction_mode, model_position)
- Float fields: must be `float`, with bounds (scale 0.1–5.0)

Use a declarative validation schema to avoid repetitive if/else:

```python
FIELD_VALIDATORS = {
    "auto_pause_on_leave": BoolValidator(),
    "subtitle_font_size": IntValidator(min=8, max=72),
    "view_mode": EnumValidator({"normal", "widescreen", "web-fullscreen", "fullscreen"}),
    # ... etc
}
```

#### 4.3 Frontend ↔ Backend mapping

**File:** `frontend/lib/api/contentConfig.ts`

Add mapping functions:

```typescript
// Nested frontend shape → flat backend shape
function toBackendConfig(config: PerVideoConfig): Record<string, unknown>

// Flat backend shape → nested frontend shape
function fromBackendConfig(data: Record<string, unknown>): PerVideoConfig
```

This keeps the backend API contract stable (flat JSON) while the frontend works with nested types.

#### 4.4 Update backend tests

**Files:**
- `tests/unit/domain/test_content_config.py` — add tests for new fields (round-trip, sparse dict)
- `tests/unit/infrastructure/test_fs_content_config_storage.py` — test saving configs with new fields
- `tests/unit/presentation/api/test_error_handlers.py` — test validation for new fields (bad types, out-of-range)

---

### Phase 5: Migration & Cleanup

#### 5.1 Backward-compatible migration

Existing per-video configs (7 flat fields) remain valid. The backend `from_dict()` already ignores unknown keys and defaults missing fields to `None`. No data migration needed — old configs just have fewer fields.

The frontend `fromBackendConfig()` handles both old flat format and new fields transparently.

#### 5.2 Remove `useContentConfig` hook (merge into VideoConfigProvider)

The existing `useContentConfig` hook's logic (fetch, debounce, save) moves into `VideoConfigProvider`. The hook itself is removed. All consumers use `useContext(VideoConfigContext)` or the scope-aware selector hooks.

#### 5.3 Update `useVideoPageSettings` hook

**File:** `frontend/hooks/useVideoPageSettings.ts`

This hook currently aggregates multiple global setting selectors for the video page. With scope-aware hooks, it may become unnecessary (each component reads directly via its own hook). Simplify or remove.

---

## User Flow Analysis & Edge Cases

### Happy Paths

| Flow | Behavior |
|------|----------|
| Open settings from home page | Scope switcher shows `Global` active, `This Video` disabled (greyed out) |
| Open settings from video page | Scope switcher shows both options, defaults to `This Video` |
| Switch to `This Video` scope | Fields show resolved values; overridden fields have badges |
| Override a field | Badge appears, Reset button shows, override count increments |
| Reset single field | Badge disappears, value reverts to global default |
| Reset All | All overrides cleared, confirmation dialog first |
| Change global default | All videos without overrides for that field immediately reflect the change |
| Navigate to different video | VideoConfigProvider unmounts → flushes debounced saves → remounts with new video's config |

### Edge Cases

| Case | Handling |
|------|----------|
| **Config still loading** | Show skeleton/loading in `This Video` scope; disable editing until loaded |
| **Save fails (network error)** | Toast error, keep local state, retry on next change |
| **Multiple browser tabs, same video** | Last-write-wins (PUT semantics). No real-time sync needed. |
| **Delete video** | Existing cascade delete in `content.py` already removes config JSON |
| **Very large config JSON** | Max ~30 fields × avg 20 bytes = ~600 bytes. Negligible. |
| **Old per-video config (7 fields)** | `from_dict()` handles it — new fields default to `None` (inherit global) |
| **Open settings, then navigate away from video** | Dialog should close on navigation, or scope switches to `Global` |

### What NOT to do

- **Don't persist per-video overrides in localStorage** — keep them on the backend for durability
- **Don't create a `useUnifiedSettings()` mega-hook** — use the existing selector hooks made scope-aware via Context
- **Don't change the backend API shape** — keep flat JSON, map in the frontend API client
- **Don't add per-task (L3) overrides** — still YAGNI per original plan

---

## Files to Create (~4 new)

| File | Purpose |
|------|---------|
| `frontend/lib/configResolution.ts` | Generic deep merge + `isFieldOverridden()` utility |
| `frontend/contexts/VideoConfigContext.tsx` | React Context + Provider for per-video resolved settings |
| `frontend/components/dialogs/settings/ScopeAwareField.tsx` | Reusable field wrapper with override badge/reset |
| `frontend/components/dialogs/settings/ScopeSwitcher.tsx` | Global / This Video toggle component |

## Files to Modify (~15)

| File | Change |
|------|--------|
| `frontend/stores/types.ts` | Add `DeepPartial`, expand `PerVideoConfig` type |
| `frontend/stores/useGlobalSettingsStore.ts` | Make selector hooks scope-aware via Context |
| `frontend/components/dialogs/SettingsDialog.tsx` | Add scope state, ScopeSwitcher, pass scope to tabs |
| `frontend/components/dialogs/settings/GeneralTab.tsx` | Accept scope, use ScopeAwareField |
| `frontend/components/dialogs/settings/ModelTab.tsx` | Accept scope, use ScopeAwareField |
| `frontend/components/dialogs/settings/PlayerTab.tsx` | Accept scope, use ScopeAwareField |
| `frontend/components/dialogs/settings/FunctionsTab.tsx` | Accept scope, use ScopeAwareField |
| `frontend/components/dialogs/settings/PromptTab.tsx` | Accept scope, use ScopeAwareField |
| `frontend/lib/api/contentConfig.ts` | Add flat ↔ nested mapping functions |
| `frontend/lib/api/ai-overrides.ts` | Adapt to nested PerVideoConfig shape |
| `frontend/app/video/[id]/VideoPageClient.tsx` | Wrap with VideoConfigProvider, update settings trigger |
| `frontend/lib/__tests__/configResolution.test.ts` | Expand tests for all field groups |
| `src/deeplecture/domain/entities/config.py` | Add ~23 new optional fields |
| `src/deeplecture/presentation/api/routes/content_config.py` | Add validation for new fields |
| `tests/unit/domain/test_content_config.py` | Add tests for new fields |

## Files to Delete (~2)

| File | Reason |
|------|--------|
| `frontend/components/dialogs/VideoConfigPanel.tsx` | Replaced by unified SettingsDialog |
| `frontend/hooks/useContentConfig.ts` | Logic absorbed into VideoConfigContext |

---

## Implementation Order

```
Phase 1 (Foundation)          Phase 2 (Context)           Phase 3 (UI)              Phase 4 (Backend)
─────────────────────         ─────────────────           ─────────────             ────────────────
types.ts (DeepPartial)   →   VideoConfigContext.tsx  →   ScopeSwitcher.tsx     →   config.py (entity)
configResolution.ts      →   selector hooks update   →   ScopeAwareField.tsx  →   content_config.py (validation)
configResolution.test.ts →                           →   SettingsDialog.tsx    →   tests
                                                     →   Each tab component
                                                     →   Delete VideoConfigPanel
```

Phase 1 & 4 can run **in parallel** (frontend types & backend entity are independent).
Phase 2 depends on Phase 1.
Phase 3 depends on Phase 2.

## Acceptance Criteria

### Functional

- [ ] Single settings dialog with scope switcher (`Global` / `This Video`)
- [ ] `This Video` scope disabled when not on a video page
- [ ] ALL ~30 settings fields overridable per-video
- [ ] Override badge + Reset button per field in video scope
- [ ] "Reset All (N)" button in header with override count
- [ ] Changes in video scope persisted to backend (debounced 800ms)
- [ ] Changing global default propagates to non-overridden videos immediately
- [ ] Old 7-field per-video configs load correctly (backward compat)
- [ ] VideoConfigPanel removed, single entry point for all settings

### Non-Functional

- [ ] Selector hooks are zero-breaking-change (existing consumers unchanged)
- [ ] Config resolution < 1ms for 30 fields
- [ ] Backend validation covers all new fields with proper types and bounds
- [ ] Test coverage for deep merge, all field groups, edge cases

## References

- Brainstorm: `docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md`
- Previous plan: `docs/plans/2026-02-10-feat-cascading-task-configuration-plan.md`
- Context-mode solution: `docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md`
- Demo page: `frontend/app/demo/settings/page.tsx`
