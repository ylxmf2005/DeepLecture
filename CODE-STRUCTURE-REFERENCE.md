# Cascading Config - Code Structure Reference

## Quick Reference: Where Everything Lives

### Backend (Python)

#### Domain Layer
- **Content Entity:** `/src/deeplecture/domain/entities/content.py`
  - `ContentMetadata` dataclass (currently ~170 lines)
  - Extend with `config_overrides` field

#### Application Layer (Use Cases)
- **Upload Use Case:** `/src/deeplecture/use_cases/upload.py`
  - Creates ContentMetadata instances

- **Content Use Case:** `/src/deeplecture/use_cases/content.py`
  - CRUD operations for ContentMetadata

- **Subtitle Use Case:** `/src/deeplecture/use_cases/subtitle.py`
  - Example task use case that needs config

- **Timeline Use Case:** `/src/deeplecture/use_cases/timeline.py`
  - Another example

- **All task use cases:** `/src/deeplecture/use_cases/*.py`
  - Note, Cheatsheet, Quiz, Voiceover, etc.

**NEW FILE TO CREATE:**
- **Config Resolution Service:** `/src/deeplecture/use_cases/config_resolution.py`
  - Pure logic for cascading config
  - No I/O, fully testable

#### Infrastructure Layer (Persistence & External Services)
- **Metadata Storage:** `/src/deeplecture/infrastructure/repositories/sqlite_metadata.py`
  - Extends `MetadataStorageInterface`
  - Persists to SQLite
  - UPDATE THIS: Add JSON column for config_overrides

- **Task Queue:** `/src/deeplecture/infrastructure/workers/task_queue.py`
  - Already well-designed
  - No changes needed (receives config at invocation)

- **LLM Provider:** `/src/deeplecture/infrastructure/providers/llm_provider.py`
  - Selects model
  - Will receive resolved config with selected model

- **DI Container:** `/src/deeplecture/di/container.py`
  - Wires up dependencies
  - ADD: Wire up ConfigResolution service

#### Presentation Layer (REST API)
- **App Setup:** `/src/deeplecture/presentation/api/app.py`
  - FastAPI initialization
  - Mount new routes here

- **Existing Routes:** `/src/deeplecture/presentation/api/routes/`
  - `subtitle.py` - POST /api/subtitle/generate
  - `timeline.py` - POST /api/timeline/generate
  - `note.py` - POST /api/note/generate
  - `cheatsheet.py` - POST /api/cheatsheet/generate
  - `quiz.py` - POST /api/quiz/generate
  - `conversation.py` - POST /api/ask
  - etc.

  **PATTERN TO FOLLOW:**
  ```python
  @router.post("/content/{content_id}/config")
  def set_content_config(content_id: str, overrides: dict):
      # Validate overrides
      # Call update use case
      # Return success
  ```

**NEW FILE TO CREATE:**
- **Config Routes:** `/src/deeplecture/presentation/api/routes/config.py`
  - GET /api/content/{content_id}/config
  - PUT /api/content/{content_id}/config
  - DELETE /api/content/{content_id}/config

---

### Frontend (TypeScript/React)

#### State Management (Zustand)
- **Global Settings Store:** `/frontend/stores/useGlobalSettingsStore.ts`
  - Manages user's global defaults
  - Persisted to localStorage
  - REVIEW, don't change structure

- **Types:** `/frontend/stores/types.ts`
  - `GlobalSettings` interface
  - `DEFAULT_GLOBAL_SETTINGS`
  - Other store types
  - ADD: Cascading config types here

**NEW FILE TO CREATE:**
- **Video Config Store:** `/frontend/stores/useVideoConfigStore.ts`
  - Manages per-video config overrides
  - Can be frontend localStorage OR backend-fetched (recommended: backend)

#### Hooks
- **useGlobalSettingsStore:** `/frontend/hooks/useGlobalSettingsStore.ts`
  - Already exists (named function, not hook)
  - Uses the Zustand store

- **useTaskStatus:** `/frontend/hooks/useTaskStatus.ts`
  - Connects to SSE stream for task events
  - Returns `tasks` state object

- **useVideoPageState:** `/frontend/hooks/useVideoPageState.ts`
  - Main container hook
  - Coordinates content, tasks, subtitles, voiceovers
  - UPDATE THIS: Add video config fetch/sync

- **useTaskNotification:** `/frontend/hooks/useTaskNotification.ts`
  - Toast/notification on task complete
  - No changes needed

- **useSubtitleManagement:** `/frontend/hooks/useSubtitleManagement.ts`
  - Handles subtitle state
  - Example of specialized hook

**NEW FILE TO CREATE:**
- **useConfigResolution:** `/frontend/hooks/useConfigResolution.ts`
  - Takes global + video + task overrides
  - Returns resolved config
  - Mirrors backend logic

#### Components
- **Video Page Client:** `/frontend/app/video/[id]/VideoPageClient.tsx`
  - Main page component
  - Uses useVideoPageState
  - ADD: Render VideoSettingsPanel somewhere

- **Tab Content Renderer:** `/frontend/components/video/TabContentRenderer.tsx`
  - Renders different tabs based on `activeTab`
  - ADD: Add "Settings" or "Video Config" tab

- **Settings Dialog:** `/frontend/components/dialogs/SettingsDialog.tsx`
  - Global settings editor
  - UPDATE: Add clarifying text about defaults

- **Settings Tabs:** `/frontend/components/dialogs/settings/`
  - `PlayerTab.tsx` - Playback settings
  - More specific tabs
  - ADD: If needed, update tab descriptions

**NEW FILES TO CREATE:**
- **VideoSettingsPanel:** `/frontend/components/video/VideoSettingsPanel.tsx`
  - Display + edit per-video config
  - Shows "inherited vs overridden" status
  - Reset to default buttons

- **PreTaskConfigPopover:** `/frontend/components/video/PreTaskConfigPopover.tsx`
  - Shows resolved config before task
  - Allows one-time overrides
  - Optional/collapsible

#### API Client
- **API Index:** `/frontend/lib/api/index.ts`
  - Exports all API functions
  - ADD: Export getVideoConfig, setVideoConfig

- **Existing Endpoints:** `/frontend/lib/api/`
  - `content.ts` - Content operations
  - `subtitle.ts` - Subtitle generation
  - `timeline.ts` - Timeline generation
  - `note.ts` - Note generation
  - `cheatsheet.ts` - Cheatsheet generation
  - `quiz.ts` - Quiz generation
  - etc.

**NEW FILE TO CREATE:**
- **Config API:** `/frontend/lib/api/config.ts`
  ```typescript
  export async function getVideoConfig(contentId: string) { ... }
  export async function setVideoConfig(contentId: string, overrides) { ... }
  export async function deleteVideoConfig(contentId: string) { ... }
  ```

#### Handlers
- **useContentHandlers:** `/frontend/hooks/handlers/useContentHandlers.ts`
  - Functions like `generateSubtitles()`
  - UPDATE: Accept optional configOverrides param

- **useSlideHandlers:** `/frontend/hooks/handlers/useSlideHandlers.ts`
  - Slide-related handlers

- **useSubtitleHandlers:** `/frontend/hooks/handlers/useSubtitleHandlers.ts`
  - Subtitle-specific handlers

- **useTimelineHandlers:** `/frontend/hooks/handlers/useTimelineHandlers.ts`
  - Timeline handlers

- **useVoiceoverHandlers:** `/frontend/hooks/handlers/useVoiceoverHandlers.ts`
  - Voiceover handlers

**UPDATE ALL:** Wire in config resolution before calling API

---

## Schema Changes

### SQLite `content_metadata` Table

**Current schema** (`sqlite_metadata.py:55`):
```python
CREATE TABLE content_metadata (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    original_filename TEXT,
    source_file TEXT,
    video_file TEXT,
    pdf_page_count INTEGER,
    timeline_path TEXT,
    created_at TEXT,
    updated_at TEXT,
    source_type TEXT,
    source_url TEXT,
    video_status TEXT,
    subtitle_status TEXT,
    enhance_translate_status TEXT,
    timeline_status TEXT,
    notes_status TEXT,
    video_job_id TEXT,
    subtitle_job_id TEXT,
    enhance_translate_job_id TEXT,
    timeline_job_id TEXT
)
```

**Add:**
```sql
ALTER TABLE content_metadata ADD COLUMN config_overrides TEXT;
-- config_overrides stores JSON: {"language_source": "ja", "llm_model": "gpt-4-turbo", ...}
```

**Optional: Migration Script**
```python
# No migration needed - new column defaults to NULL
# Old videos get NULL, cascade uses global settings
```

---

## Type Definitions to Create

### Backend Python

```python
# src/deeplecture/use_cases/dto/config.py (NEW)

from dataclasses import dataclass
from typing import Optional

@dataclass
class VideoConfigOverrides:
    """Overridden settings for a specific video (only non-null values)."""
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    llm_model: Optional[str] = None
    tts_model: Optional[str] = None
    prompts: Optional[dict[str, str]] = None
    note_context_mode: Optional[str] = None

@dataclass
class ResolvedConfig:
    """Fully resolved config after cascade."""
    source_language: str
    target_language: str
    llm_model: str | None
    tts_model: str | None
    prompts: dict[str, str]
    note_context_mode: str
    # ... etc
```

### Frontend TypeScript

```typescript
// frontend/types/config.ts (NEW)

export interface VideoConfigOverrides {
    sourceLanguage?: string;
    targetLanguage?: string;
    llmModel?: string;
    ttsModel?: string;
    prompts?: Record<string, string>;
    noteContextMode?: string;
}

export interface ResolvedConfig {
    sourceLanguage: string;
    targetLanguage: string;
    llmModel: string | null;
    ttsModel: string | null;
    prompts: Record<string, string>;
    noteContextMode: string;
}

export type ConfigSource = 'global' | 'video' | 'task';

export interface ResolvedConfigWithSource {
    config: ResolvedConfig;
    sources: Record<string, ConfigSource>;
}
```

---

## Code Examples

### Backend: Config Resolution Service

**File: `/src/deeplecture/use_cases/config_resolution.py`** (NEW)

```python
"""Configuration resolution: cascade from global -> video -> task."""

from dataclasses import dataclass, field
from typing import Any, Optional

class ConfigResolution:
    """Resolves config hierarchy with cascading overrides."""

    def resolve(
        self,
        global_config: dict[str, Any],
        video_config: Optional[dict[str, Any]] = None,
        task_overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Apply 3-level cascade with nullish coalescing.

        Args:
            global_config: User's global defaults (from GlobalSettings)
            video_config: Per-video overrides (from ContentMetadata.config_overrides)
            task_overrides: One-time overrides (from API request)

        Returns:
            Fully resolved config with all values defined
        """
        video_config = video_config or {}
        task_overrides = task_overrides or {}

        return {
            "source_language": (
                task_overrides.get("source_language")
                or video_config.get("source_language")
                or global_config.get("language", {}).get("original")
            ),
            "target_language": (
                task_overrides.get("target_language")
                or video_config.get("target_language")
                or global_config.get("language", {}).get("translated")
            ),
            "llm_model": (
                task_overrides.get("llm_model")
                or video_config.get("llm_model")
                or global_config.get("ai", {}).get("llmModel")
            ),
            "tts_model": (
                task_overrides.get("tts_model")
                or video_config.get("tts_model")
                or global_config.get("ai", {}).get("ttsModel")
            ),
            "prompts": self._merge_prompts(
                global_config.get("ai", {}).get("prompts", {}),
                video_config.get("prompts", {}),
                task_overrides.get("prompts", {}),
            ),
            "note_context_mode": (
                task_overrides.get("note_context_mode")
                or video_config.get("note_context_mode")
                or global_config.get("note", {}).get("contextMode")
            ),
        }

    @staticmethod
    def _merge_prompts(
        global_prompts: dict,
        video_prompts: dict,
        task_prompts: dict,
    ) -> dict:
        """Merge prompts (task > video > global)."""
        result = dict(global_prompts)
        result.update(video_prompts)
        result.update(task_prompts)
        return result
```

### Frontend: Config Resolution Hook

**File: `/frontend/hooks/useConfigResolution.ts`** (NEW)

```typescript
"use client";

import { useMemo } from "react";
import { GlobalSettings } from "@/stores/types";
import { useGlobalSettingsStore } from "@/stores/useGlobalSettingsStore";
import { useVideoConfig } from "@/hooks/useVideoConfig"; // fetch from API or store

export interface ResolvedConfig {
    sourceLanguage: string;
    targetLanguage: string;
    llmModel: string | null;
    ttsModel: string | null;
    noteContextMode: string;
    prompts: Record<string, string>;
}

export function useConfigResolution(
    contentId: string,
    taskOverrides?: Record<string, any>
): ResolvedConfig {
    const globalSettings = useGlobalSettingsStore();
    const videoConfig = useVideoConfig(contentId); // fetch from backend

    return useMemo(() => {
        return resolveConfig(globalSettings, videoConfig, taskOverrides);
    }, [globalSettings, videoConfig, taskOverrides]);
}

function resolveConfig(
    global: GlobalSettings,
    video: Record<string, any> | null,
    task: Record<string, any> | undefined
): ResolvedConfig {
    video = video ?? {};
    task = task ?? {};

    return {
        sourceLanguage:
            task.sourceLanguage ??
            video.sourceLanguage ??
            global.language.original,

        targetLanguage:
            task.targetLanguage ??
            video.targetLanguage ??
            global.language.translated,

        llmModel:
            task.llmModel ?? video.llmModel ?? global.ai.llmModel,

        ttsModel:
            task.ttsModel ?? video.ttsModel ?? global.ai.ttsModel,

        noteContextMode:
            task.noteContextMode ??
            video.noteContextMode ??
            global.note.contextMode,

        prompts: mergePrompts(
            global.ai.prompts,
            video.prompts ?? {},
            task.prompts ?? {}
        ),
    };
}

function mergePrompts(
    globalPrompts: Record<string, string>,
    videoPrompts: Record<string, string>,
    taskPrompts: Record<string, string>
): Record<string, string> {
    return {
        ...globalPrompts,
        ...videoPrompts,
        ...taskPrompts,
    };
}
```

### Integration: Task Handler with Config

**File: `/frontend/hooks/handlers/useContentHandlers.ts`** (UPDATE)

```typescript
// Existing code...

export function useContentHandlers(contentId: string) {
    const globalSettings = useGlobalSettingsStore();
    const videoConfig = useVideoConfig(contentId);
    const resolvedConfig = useConfigResolution(contentId);

    async function generateSubtitles(
        taskOverrides?: Record<string, any>
    ) {
        try {
            // Resolve config with task-level overrides
            const config = useConfigResolution(contentId, taskOverrides);

            // Call API with resolved config
            const response = await api.generateSubtitles(contentId, {
                config_overrides: {
                    source_language: config.sourceLanguage,
                    target_language: config.targetLanguage,
                    // ... etc
                },
            });

            return response;
        } catch (error) {
            // Handle error
        }
    }

    // ... other handlers
}
```

---

## Deployment Considerations

### Database Migration

```bash
# Apply in src/deeplecture/infrastructure/repositories/sqlite_metadata.py

ALTER TABLE content_metadata ADD COLUMN config_overrides TEXT DEFAULT NULL;

# No data migration needed - existing videos use NULL -> fall through to global
```

### Backward Compatibility

- ✅ Existing API calls without `config_overrides` work fine (cascade uses global)
- ✅ Old frontend versions don't break (they just use global settings)
- ✅ New frontend with old backend works (video config is null)

### Feature Flags (Optional)

Add feature flag if rolling out gradually:
```python
# src/deeplecture/config/settings.py
ENABLE_PER_VIDEO_CONFIG = os.getenv("ENABLE_PER_VIDEO_CONFIG", "true").lower() == "true"
```

Then in routes:
```python
if not ENABLE_PER_VIDEO_CONFIG:
    raise HTTPException(status_code=404, detail="Feature not enabled")
```

---

## Testing Structure

### Unit Tests: Config Resolution

**File: `/tests/unit/use_cases/test_config_resolution.py`** (NEW)

```python
import pytest
from deeplecture.use_cases.config_resolution import ConfigResolution

def test_cascade_all_global():
    """All values from global."""
    service = ConfigResolution()
    global_cfg = {"language": {"original": "en", "translated": "fr"}, ...}
    result = service.resolve(global_cfg)
    assert result["source_language"] == "en"
    assert result["target_language"] == "fr"

def test_cascade_video_overrides():
    """Video overrides fall through to global."""
    service = ConfigResolution()
    global_cfg = {"language": {"original": "en", "translated": "fr"}, ...}
    video_cfg = {"target_language": "ja"}
    result = service.resolve(global_cfg, video_cfg)
    assert result["source_language"] == "en"  # from global
    assert result["target_language"] == "ja"  # from video

def test_cascade_task_wins():
    """Task overrides beat video and global."""
    service = ConfigResolution()
    task_cfg = {"source_language": "zh"}
    result = service.resolve(global_cfg, video_cfg, task_cfg)
    assert result["source_language"] == "zh"  # from task
```

### Integration Tests: Config API

**File: `/tests/integration/test_config_api.py`** (NEW)

```python
@pytest.mark.asyncio
async def test_get_video_config():
    """GET /api/content/{id}/config returns stored overrides."""
    # Create content
    # Set config
    # GET /api/content/{id}/config
    # Assert response

@pytest.mark.asyncio
async def test_put_video_config():
    """PUT /api/content/{id}/config updates and persists."""
    # Create content
    # PUT /api/content/{id}/config with {"llm_model": "gpt-4"}
    # Assert updated in DB
    # Verify next GET returns it
```

---

## Summary

**Key files to create:**
1. `/src/deeplecture/use_cases/config_resolution.py` - Resolution logic
2. `/src/deeplecture/presentation/api/routes/config.py` - API endpoints
3. `/frontend/hooks/useConfigResolution.ts` - Resolution hook
4. `/frontend/hooks/useVideoConfig.ts` - Fetch/store video config
5. `/frontend/components/video/VideoSettingsPanel.tsx` - UI for per-video config
6. `/frontend/components/video/PreTaskConfigPopover.tsx` - UI for task overrides
7. `/frontend/lib/api/config.ts` - API client for config operations
8. `/frontend/stores/useVideoConfigStore.ts` - Optional: localStorage persistence

**Key files to update:**
- `/src/deeplecture/domain/entities/content.py` - Add config_overrides field
- `/src/deeplecture/infrastructure/repositories/sqlite_metadata.py` - Persist config
- `/src/deeplecture/di/container.py` - Wire ConfigResolution service
- `/frontend/hooks/useVideoPageState.ts` - Fetch and sync video config
- `/frontend/hooks/handlers/use*Handlers.ts` - Include config in task API calls
- All task API functions in `/frontend/lib/api/*.ts` - Accept config_overrides param

**Database:**
- Add `config_overrides TEXT` column to `content_metadata` table
