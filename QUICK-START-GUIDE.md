# Cascading Configuration System - Quick Start Guide

## What You Need to Know (30-Second Overview)

The system has a **3-level cascade** that eliminates manual setting changes between videos:

```
[Task Run] Overrides → [Per-Video] Config → [Global] Defaults
```

- **Global:** User's default settings (already exists in `useGlobalSettingsStore`)
- **Per-Video:** Overrides for specific video (NEW, backend-persisted)
- **Task Run:** One-time overrides at task invocation (NEW, ephemeral)

Each level is **optional** — if not set, cascade falls through to the next level.

---

## Why This Matters

**Before:** User has to manually change global settings before each task on different videos
```
Settings → Change Language to Japanese → Generate Subtitles
Settings → Change Language to Spanish → Generate Subtitles (different video)
Settings → Change Language back → Work on other videos
😤 Tedious, error-prone
```

**After:** Each video remembers its own language
```
Video A: "This is Japanese" (auto-saved)
Video B: "This is Spanish" (auto-saved)
Generate subtitles on either video → Uses correct language automatically
😊 Seamless
```

---

## Architecture at a Glance

### Backend

```python
# 1. Content entity holds overrides
@dataclass
class ContentMetadata:
    id: str
    # ... existing fields ...
    config_overrides: dict[str, Any]  # NEW: {"language_target": "ja", ...}

# 2. Resolution service merges all 3 levels
class ConfigResolution:
    def resolve(global, video, task) -> dict:
        # Returns fully resolved config

# 3. API endpoints manage per-video config
GET    /api/content/{id}/config        # Fetch per-video overrides
PUT    /api/content/{id}/config        # Update per-video overrides
DELETE /api/content/{id}/config        # Reset to global defaults
```

### Frontend

```typescript
// 1. Resolution hook (mirrors backend logic)
const config = useConfigResolution(contentId, taskOverrides);

// 2. UI to edit per-video config
<VideoSettingsPanel contentId={contentId} />

// 3. Optional pre-task config popover
<PreTaskConfigPopover taskType="subtitle_generation" overrides={{}} />

// 4. Wire into task handlers
generateSubtitles(contentId, { config_overrides: {...} })
```

---

## What Gets Cascaded

### ✅ Content-Related (Has Per-Video Overrides)
- Source language (video audio language)
- Target language (translation/AI output language)
- LLM model (ChatGPT, Claude, etc.)
- TTS model (voice synthesis)
- Prompts (custom instructions for AI)
- Note context mode (subtitle, slide, or both)

### ❌ Not Cascaded (Global Only)
- Playback behavior (autopause, autoresume)
- Subtitle display (font size, position)
- Notifications (toast, browser, title flash)
- Layout (sidebar visibility, view mode)
- Dictionary settings
- Live2D appearance
- Learner profile (global for now)

---

## Implementation Scope

### Phase 1: Backend Infrastructure (2-3 days)
```python
# 1. Extend ContentMetadata
config_overrides: dict[str, Any] = field(default_factory=dict)

# 2. Create ConfigResolution service
class ConfigResolution:
    def resolve(global_config, video_config, task_overrides):
        # Merge with cascading logic

# 3. Add API endpoints
GET/PUT/DELETE /api/content/{id}/config

# 4. Update SQLite schema
ALTER TABLE content_metadata ADD COLUMN config_overrides TEXT;
```

### Phase 2: Frontend State Management (1-2 days)
```typescript
// 1. Create video config store or hook
useVideoConfig(contentId)          // Fetch from backend

// 2. Create resolution hook
useConfigResolution(contentId, taskOverrides)  // Merge all 3 levels

// 3. Wire into task handlers
generateSubtitles(contentId, { config_overrides: {...} })
```

### Phase 3: UI Components (2-3 days)
```typescript
// 1. Video Settings Panel
<VideoSettingsPanel />  // Edit per-video overrides

// 2. Pre-task Config Popover
<PreTaskConfigPopover />  // One-time overrides

// 3. Settings Dialog Updates
// Add help text: "These are defaults for new videos"
```

---

## Data Flow Example

### Scenario: Generating subtitles for a Japanese video

**Step 1: Initial State**
- Global settings: English → Chinese
- Video A config: (none, inherits global)
- Video B config: Japanese → English (explicitly set)

**Step 2: User on Video B, Clicks "Generate Subtitles"**
```
User clicks → PreTaskConfigPopover shows:
  "Source Language: Japanese (from video config)"
  "Target Language: English (from video config)"
  "LLM Model: gpt-4 (from global default)"
  → User clicks "Generate" with no changes
```

**Step 3: API Call**
```
POST /api/subtitle/generate {
  "content_id": "video_b",
  "config_overrides": {}  // Task level: empty
}
```

**Step 4: Backend Resolution**
```python
global_cfg = {language: {original: "en", translated: "zh"}, ...}
video_cfg = {source_language: "ja", target_language: "en"}
task_cfg = {}

resolved = ConfigResolution.resolve(global_cfg, video_cfg, task_cfg)
# Returns: {
#   source_language: "ja",        # from video
#   target_language: "en",         # from video
#   llm_model: "gpt-4",            # from global
#   ...
# }
```

**Step 5: Task Execution**
```python
subtitles = whisper.transcribe(
    video_b_audio,
    language=resolved["source_language"],  # "ja"
)
# Transcription is in Japanese ✓
```

---

## Testing Strategy

### Unit Tests (Fast, Isolated)
```python
# ConfigResolution logic
def test_cascade_from_global():
    # Task override = None, Video override = None
    # Should use global value

def test_cascade_video_wins():
    # Task override = None, Video override = X
    # Should use X

def test_cascade_task_wins():
    # Task override = Y, Video override = X
    # Should use Y
```

### Integration Tests (With Database)
```python
# API endpoints
def test_get_video_config():
    # Save config, GET it back, verify

def test_put_video_config():
    # PUT new config, verify persisted in DB

# Task submission with config
def test_subtitle_generation_with_config():
    # Verify resolved config is passed to task callable
```

### E2E Tests (Full Flow)
```typescript
// User flow
1. User navigates to Video A
2. User opens VideoSettingsPanel
3. User sets language to Japanese
4. User saves
5. User clicks "Generate Subtitles"
6. PreTaskConfigPopover shows Japanese
7. Task executes with Japanese language
8. Subtitles are in Japanese ✓
```

---

## Frequently Asked Questions

### Q: What if a user clears their browser's localStorage?
**A:** No problem! Per-video config is stored on the backend. Global settings from localStorage will default to original values, but per-video configs stay safe.

### Q: Can users share config between videos?
**A:** Not in Phase 1 (out of scope). Easy to add in Phase 2 as a "copy config from video X" button.

### Q: What about learner profile — should it also be per-video?
**A:** Not in Phase 1. Keep it global for now. A learner might study Chinese at beginner level but English at advanced level, but that's a Phase 2 consideration.

### Q: Do task-specific parameters like `question_count` get per-video defaults?
**A:** Not in Phase 1. These are task-specific and should only exist at task invocation (pre-task popover). Per-video defaults would require many more parameters. Phase 2 can revisit.

### Q: What if backend is temporarily down?
**A:** Frontend falls back to global settings (cascade still works). Per-video config just won't load, but tasks still run with global defaults.

### Q: How do I migrate existing videos that have no per-video config?
**A:** No migration needed! The cascade naturally falls through to global. Users can start setting per-video config on any video anytime.

---

## Key Design Decisions (Why We Chose This Approach)

| Decision | Why |
|----------|-----|
| **3-level cascade** (not snapshots) | Only store what's different. Auto-propagation. Easy reset. Familiar pattern (VS Code, Premiere Pro). |
| **Backend-persisted** (not localStorage) | Survives browser clears. Multi-device ready. Config lives with its content. |
| **Partial overrides** (not full config) | Minimal storage. Clear inheritance. No duplication. |
| **Separate per-video UI** (not in global settings) | Keeps settings dialog uncluttered. Makes it clear which video you're configuring. |
| **Optional pre-task popover** (not always shown) | Lets power users tweak, doesn't slow down casual users. |

---

## Deliverables

### Code
- [ ] Extended `ContentMetadata` with `config_overrides` field
- [ ] `ConfigResolution` service (pure logic, fully testable)
- [ ] Config API endpoints (GET/PUT/DELETE)
- [ ] `useConfigResolution` hook (mirrors backend logic)
- [ ] `VideoSettingsPanel` component
- [ ] `PreTaskConfigPopover` component
- [ ] Updated task handlers with config integration
- [ ] Updated settings dialog with clarifying text

### Database
- [ ] Schema: Add `config_overrides TEXT` column

### Tests
- [ ] Unit: Config resolution logic
- [ ] Integration: Config API endpoints
- [ ] E2E: User can set and use per-video config

### Documentation
- [ ] Architecture decision record (ADR)
- [ ] User guide for per-video settings

---

## Success Criteria

- ✅ User can view current config for a video (global vs video vs task level)
- ✅ User can set per-video overrides (language, model, etc.)
- ✅ User can reset per-video override to use global default
- ✅ Task uses correct resolved config (cascade works)
- ✅ Per-video config survives browser refresh
- ✅ Multiple videos can have different configs simultaneously
- ✅ Old browsers/clients still work (backward compatible)
- ✅ 100+ unit/integration tests covering cascade logic

---

## Related Documentation

- **Full Design:** `/docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md` (11 KB, comprehensive)
- **Architecture:** `/docs/architecture/task-system-overview.md` (34 KB, task system internals)
- **Implementation Checklist:** `/IMPLEMENTATION-CHECKLIST.md` (detailed tasks)
- **Code Structure:** `/CODE-STRUCTURE-REFERENCE.md` (file locations + code examples)

---

## Next Steps

1. **Read** the full design doc (brainstorm)
2. **Review** architecture docs (task system, state management)
3. **Start** with backend Phase 1 (extend ContentMetadata, add ConfigResolution)
4. **Test** config resolution logic thoroughly
5. **Move** to frontend Phase 2 (add API integration)
6. **Polish** with UI Phase 3 (components)
7. **Test** E2E flows

**Estimated Timeline:** 3-4 weeks (1 week backend infrastructure, 1 week frontend integration, 1-2 weeks UI + testing)

---

## Questions?

Refer to the supporting docs:
- **"How do I implement X?"** → See `/CODE-STRUCTURE-REFERENCE.md`
- **"What's the full design?"** → See `/docs/brainstorms/2026-02-10-cascading-task-config-brainstorm.md`
- **"How does the task system work?"** → See `/docs/architecture/task-system-overview.md`
- **"What should I code next?"** → See `/IMPLEMENTATION-CHECKLIST.md`

Good luck! 🚀
