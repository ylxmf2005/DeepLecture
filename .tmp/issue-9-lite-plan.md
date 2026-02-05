# Consensus Plan: Add Video Player View Mode Controls

## Summary

**Feature**: Add three view mode control buttons (Widescreen, Web Fullscreen, System Fullscreen) to the video player, with widescreen mode transforming the layout to place the video full-width at the top and NotesPanel/Sidebar side-by-side below.

**Estimated LOC**: ~125 (Small)

**Path**: Lite (single-agent)

## Proposed Solution

### File Changes

| File | Level | Purpose |
|------|-------|---------|
| `frontend/stores/types.ts` | Minor | Add `viewMode` to GlobalSettings |
| `frontend/stores/useGlobalSettingsStore.ts` | Minor | Add view mode state management actions |
| `frontend/app/video/[id]/VideoPageClient.tsx` | Major | Implement widescreen layout transformation logic |
| `frontend/components/video/VideoControls.tsx` | Minor | Add view mode control buttons |

### Implementation Steps

**Step 1: Update type definitions for view mode** (Estimated: ~25 LOC)
- File: `frontend/stores/types.ts`
  - Add `export type ViewMode = "normal" | "widescreen" | "web-fullscreen" | "fullscreen";` after line 119
  - Add `viewMode: ViewMode;` to GlobalSettings interface (around line 63)
  - Add `viewMode: "normal" as ViewMode,` to DEFAULT_GLOBAL_SETTINGS (around line 93)
  - Add view mode action types to GlobalSettingsActions interface (around line 169)

Dependencies: None

**Step 2: Implement view mode state management in Zustand store** (Estimated: ~20 LOC)
- File: `frontend/stores/useGlobalSettingsStore.ts`
  - Add `setViewMode: (mode) => set({ viewMode: mode })` action (around line 103, after toggleHideSidebars)
  - Add `viewMode: state.viewMode,` to partialize function (around line 216, after hideSidebars)
  - Add `viewMode: state.viewMode ?? DEFAULT_GLOBAL_SETTINGS.viewMode,` to migrate function (around line 260)

Dependencies: Step 1 (type definitions must exist first)

**Step 3: Add view mode control buttons to VideoControls** (Estimated: ~40 LOC)
- File: `frontend/components/video/VideoControls.tsx`
  - Import icons at line 12: `ChevronsLeftRight, Maximize2`
  - Add props to VideoControlsProps interface (after line 42):
    - `viewMode: ViewMode;`
    - `onViewModeChange: (mode: ViewMode) => void;`
  - Destructure new props in component (around line 72)
  - Add view mode buttons before fullscreen button (around line 330, before fullscreen):
    - Widescreen button (ChevronsLeftRight icon)
    - Web fullscreen button (Maximize icon, separate from system fullscreen)
    - System fullscreen button (Maximize2 icon)
  - Update click handlers to call `onViewModeChange` with appropriate mode
  - Apply active state styling when `viewMode` matches button mode

Dependencies: Step 2 (store actions must exist)

**Step 4: Implement layout transformation logic in VideoPageClient** (Estimated: ~40 LOC)
- File: `frontend/app/video/[id]/VideoPageClient.tsx`
  - Add viewMode to useVideoPageSettings hook extraction (around line 67): `const { playback, language, hideSidebars, viewMode, live2d } = settings;`
  - Extract `setViewMode` from settingsActions (around line 68)
  - Pass viewMode and onViewModeChange to VideoPlayerSection component props (around line 419-437)
  - Update grid layout className logic (line 394):
    - For widescreen mode: Use `grid-cols-1` (full width)
    - For normal/web-fullscreen: Use existing `grid-cols-1 md:grid-cols-3` pattern
  - Add widescreen-specific layout wrapper around NotesPanel and SidebarTabs (around line 439-502):
    - When `viewMode === "widescreen"`: Wrap NotesPanel and SidebarTabs in a new grid row with `grid-cols-1 md:grid-cols-2`
    - When `viewMode !== "widescreen"`: Use existing structure

Dependencies: Step 3 (view mode controls must exist)

### Layout Transformation

**Normal Mode** (Current):
```
+--------------------+------------+
|   VideoPlayer      |  Sidebar   |
+--------------------+            |
|   NotesPanel       |            |
+--------------------+------------+
Grid: md:grid-cols-3, left col-span-2
```

**Widescreen Mode** (New):
```
+----------------------------------+
|         VideoPlayer              |
|         (full width)             |
+----------------------------------+
|   NotesPanel    |    Sidebar     |
+-----------------+----------------+
Grid: grid-cols-1 for video, then nested grid-cols-2 for bottom row
```

**Web Fullscreen Mode**:
- Video fills browser viewport
- Other elements hidden or minimized
- Similar to YouTube theater mode

**System Fullscreen Mode**:
- Uses existing browser fullscreen API
- Existing implementation in VideoPlayer.tsx

### Test Strategy

**Manual Testing:**
- Click widescreen button: Verify video expands to full width, NotesPanel and Sidebar appear side-by-side below
- Click web fullscreen button: Verify video fills browser viewport
- Click system fullscreen button: Verify native fullscreen API is triggered
- Switch between modes: Verify layout transitions smoothly
- Verify view mode state persists across page refreshes (Zustand persistence)
- Test responsive behavior on different screen sizes
- Verify existing hideSidebars setting still works correctly

**Integration Testing:**
- Verify view mode doesn't conflict with existing fullscreen implementation
- Verify subtitle overlay positioning remains correct in all view modes
- Verify Live2D overlay remains functional in all view modes
- Verify DnD tab functionality works in widescreen mode

## Icons Reference

| Mode | Icon | Lucide Name |
|------|------|-------------|
| Widescreen | `< >` | `ChevronsLeftRight` |
| Web Fullscreen | `⊞` | `Maximize` |
| System Fullscreen | `↗↙` | `Maximize2` |

---

**Total estimated complexity:** 125 LOC (Small feature)

**Recommended approach:** Single development session following Types → Store → Controls → Layout
