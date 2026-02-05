# Context Summary: Video Player View Mode Controls

## Feature Understanding
**Intent**: Add three view mode control buttons to the video player (widescreen, web fullscreen, system fullscreen) with special widescreen layout behavior where sidebar and bottom panel are relocated below the video instead of beside it.

**Scope signals**: video player controls, layout transformation, fullscreen API, responsive design, state management, Lucide icons (`ChevronsLeftRight`, `Maximize`, `Maximize2`)

## Relevant Files

### Source Files
- `frontend/app/video/[id]/VideoPageClient.tsx` — Main video page container, manages layout grid (`grid-cols-1 md:grid-cols-3`), controls sidebar visibility via `hideSidebars`, renders VideoPlayerSection, NotesPanel (bottom bar), and SidebarTabs
- `frontend/components/video/VideoPlayerSection.tsx` — Wrapper for VideoPlayer, already handles Player/Slide tab toggle and slide fullscreen
- `frontend/components/video/VideoPlayer.tsx` — Core video player component, implements fullscreen toggle, has `containerRef` and fullscreen state management, contains VideoControls
- `frontend/components/video/VideoControls.tsx` — Bottom control bar overlay with play/pause, volume, speed, existing fullscreen button
- `frontend/components/video/NotesPanel.tsx` — Bottom panel component, renders DraggableTabBar with tabs (notes, timeline, subtitles, etc.)
- `frontend/components/video/SidebarTabs.tsx` — Right sidebar component, renders DraggableTabBar with tabs (explanations, verification, ask, quiz, cheatsheet)

### State Management
- `frontend/stores/useGlobalSettingsStore.ts` — Zustand store with `hideSidebars` boolean, persisted to localStorage, has `toggleHideSidebars` action
- `frontend/stores/types.ts` — Type definitions for stores, `hideSidebars` in GlobalSettings

## Architecture Context

### Existing Layout Structure
- `VideoPageClient.tsx`: Grid layout with conditional columns `grid-cols-1 md:grid-cols-3` when `hideSidebars` is false
- Left column spans `md:col-span-2`, contains VideoPlayerSection and NotesPanel (bottom bar)
- Right column contains SidebarTabs, conditionally rendered with `{!hideSidebars && (<SidebarTabs .../>)}`
- Current structure: Video/Notes stacked vertically in left 2/3, Sidebar in right 1/3

### Fullscreen Implementations
- `VideoPlayer.tsx`: System fullscreen on `containerRef` using `requestFullscreen()` API, tracks state with `isFullscreen` useState
- `VideoPlayerSection.tsx`: Same pattern for slide viewer fullscreen
- `NotesPanel.tsx`: Fullscreen for notes editor via DOM query

### State Management Pattern
- Zustand stores with persistence (localStorage)
- `useGlobalSettingsStore` for user-level preferences
- `hideSidebars` is a global boolean toggle
- Components consume via hooks like `useGlobalSettingsStore((state) => state.hideSidebars)`

### UI Patterns
- Tailwind CSS with `cn()` utility for conditional classes
- Lucide React icons already in use throughout (e.g., `Maximize`, `Minimize` in VideoControls)
- Hover-triggered controls with `opacity-0 group-hover:opacity-100 transition-opacity`

## Widescreen Layout Challenge

**Current Layout** (Normal mode):
```
+--------------------+------------+
|   VideoPlayer      |  Sidebar   |
+--------------------+            |
|   NotesPanel       |            |
|   (bottom bar)     |            |
+--------------------+------------+
```

**Required Widescreen Layout**:
```
+----------------------------------+
|         VideoPlayer              |
|         (full width)             |
+----------------------------------+
|   NotesPanel    |    Sidebar     |
|   (bottom bar)  |                |
+-----------------+----------------+
```

## Constraints
- Next.js App Router with app directory
- Tailwind + Lucide icons (lucide-react: ^0.555.0)
- State persistence via Zustand + localStorage
- Frontend-only feature, no backend changes
- Must not conflict with existing system fullscreen

## Complexity Estimation
- **Estimated LOC**: ~180
- **Files affected**: 4-5 files
- **Recommended path**: `lite`
