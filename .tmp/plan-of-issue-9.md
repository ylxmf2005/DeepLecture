# Implementation Plan: Issue #9 - Video Player View Mode Controls

## Implementation Steps

**Step 1: Update type definitions** (`frontend/stores/types.ts`)
- Add ViewMode type
- Add viewMode to GlobalSettings interface
- Add viewMode to DEFAULT_GLOBAL_SETTINGS
- Add setViewMode to GlobalSettingsActions

**Step 2: Implement state management** (`frontend/stores/useGlobalSettingsStore.ts`)
- Add setViewMode action
- Add viewMode to partialize function
- Add viewMode to migrate function

**Step 3: Add view mode buttons** (`frontend/components/video/VideoControls.tsx`)
- Import ChevronsLeftRight, Maximize2 icons
- Add viewMode and onViewModeChange props
- Add widescreen, web-fullscreen, system-fullscreen buttons

**Step 4: Layout transformation** (`frontend/app/video/[id]/VideoPageClient.tsx`)
- Extract viewMode from settings
- Pass to VideoPlayerSection
- Implement widescreen layout transformation
