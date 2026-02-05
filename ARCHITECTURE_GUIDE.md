# CourseSubtitle Architecture Guide

## Overview

This document provides a complete architectural overview of three interconnected features:
1. **Auto-leave functionality** - Automatic pause/resume and subtitle switching when user leaves tab
2. **Voiceover management** - Selection, sync timeline loading, and state persistence
3. **Subtitle auto-switch** - Automatic subtitle mode switching for background listening

All three features work together to enhance the learning experience by providing intelligent automation around focus, audio sync, and subtitle display.

---

## 1. Auto-Leave (Focus Mode) Functionality

### Purpose
Detects when the user leaves or returns to the page (via `visibilitychange` event) and automatically:
- Pauses video if `autoPauseOnLeave` is enabled
- Resumes video if `autoResumeOnReturn` is enabled
- Switches subtitles to target (translation) mode for background listening if `autoSwitchSubtitlesOnLeave` is enabled
- Detects missed content and offers intelligent catch-up

### Key Component: `FocusModeHandler`

**File**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx`

**Props**:
```typescript
interface FocusModeHandlerProps {
    playerRef: React.RefObject<VideoPlayerRef | null>;
    subtitles: Subtitle[];
    currentTime: number;
    learnerProfile?: string;

    // Settings from GlobalSettingsStore
    autoPauseOnLeave: boolean;
    autoResumeOnReturn: boolean;
    autoSwitchSubtitlesOnLeave: boolean;
    subtitleMode: SubtitleDisplayMode;
    hasTranslation: boolean;

    // Callbacks
    onSubtitleModeChange: (mode: SubtitleDisplayMode) => void;

    // Other parameters for missed content detection
    summaryThresholdSeconds: number;
    skipRamblingEnabled: boolean;
    timelineEntries: TimelineEntry[];
    onAddToAsk: (item: AskContextItem) => void;
    onAddToNotes: (markdown: string) => void;
}
```

**Internal State**:
```typescript
const [isDialogOpen, setIsDialogOpen] = useState(false);
const [summary, setSummary] = useState("");
const [missedDurationStr, setMissedDurationStr] = useState("");
const [jumpBackTime, setJumpBackTime] = useState<number | null>(null);

const leaveTimeRef = useRef<number | null>(null);
const wasPlayingRef = useRef(false);
const autoSwitchStateRef = useRef<AutoSwitchState>(createAutoSwitchState());
const hideDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
```

**Key Flow - `handleVisibilityChange()`**:

#### When Page Becomes Hidden (`document.hidden === true`):
1. Record current playback state in `wasPlayingRef`
2. Record current video time in `leaveTimeRef`
3. **Clear any existing debounce timer** (if returning very quickly)
4. **With 1.5s debounce** (via `AUTO_SWITCH_DEBOUNCE_MS = 1500`):
   - Call `getAutoSwitchModeOnHide()` to check if subtitle switch needed
   - If yes: Call `updateStateOnAutoSwitch()` and trigger `onSubtitleModeChange(newMode)`
5. If `autoPauseOnLeave`: Call `playerRef.current?.pause()`

#### When Page Becomes Visible (`document.hidden === false`):
1. **Clear the debounce timer** (cancels pending subtitle switch if returning quickly)
2. **Restore subtitles** if they were auto-switched:
   - Call `getAutoSwitchModeOnShow()` with saved state
   - If should restore: Call `onSubtitleModeChange(restoreMode)`
   - Reset auto-switch state via `resetAutoSwitchState()`
3. **Resume video** if `autoResumeOnReturn && wasPlayingRef.current`
4. **Detect missed content**:
   - Calculate time elapsed: `currentVideoTime - leaveTimestamp`
   - If missed time > threshold: Open dialog with options to:
     - Jump back to where they left
     - Generate summary of missed content
     - Add to Ask or Notes

### Integration Point

**File**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/app/video/[id]/VideoPageClient.tsx`

```typescript
// Line 73: Read settings from GlobalSettingsStore
const autoSwitchSubtitlesOnLeave = playback.autoSwitchSubtitlesOnLeave;

// Line 682-692: Mount FocusModeHandler in the video page
<FocusModeHandler
    playerRef={playerRef}
    subtitles={playerSubtitles}
    currentTime={currentTime}
    learnerProfile={learnerProfile}
    autoPauseOnLeave={autoPauseOnLeave}
    autoResumeOnReturn={autoResumeOnReturn}
    autoSwitchSubtitlesOnLeave={autoSwitchSubtitlesOnLeave}
    subtitleMode={playerSubtitleMode}           // From state
    hasTranslation={content.translationStatus === "ready"}
    onSubtitleModeChange={setPlayerSubtitleMode} // Updates state
    summaryThresholdSeconds={summaryThresholdSeconds}
    skipRamblingEnabled={skipRamblingEnabled}
    timelineEntries={timelineEntries}
    onAddToAsk={handleAddToAsk}
    onAddToNotes={handleAddToNotes}
/>
```

---

## 2. Voiceover Management

### Purpose
Manages the complete voiceover lifecycle:
- Load and list available voiceovers for a video
- Track selected voiceover (persisted in Zustand store)
- Auto-load sync timeline when voiceover is selected
- Enable/disable voiceover mode in the video player

### Architecture

#### State Management - Three-Tier Structure

**Tier 1: Persistence (Zustand Store)**
```
File: /Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useVideoStateStore.ts

Per-video state stored in localStorage:
- selectedVoiceoverId: string | null

Function: setSelectedVoiceoverId(videoId, voiceoverId)
```

**Tier 2: Hook - Voiceover Management**
```
File: /Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useVoiceoverManagement.ts
```

**Tier 3: Hook - Video Page State**
```
File: /Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useVideoPageState.ts
```

### Hook: `useVoiceoverManagement`

**Location**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useVoiceoverManagement.ts`

**Responsibility**: Isolated voiceover state management following Single Responsibility Principle

**Interface**:
```typescript
export interface UseVoiceoverManagementReturn {
    // Processing state - while generating new voiceover
    voiceoverProcessing: SubtitleSource | null;
    setVoiceoverProcessing: (source: SubtitleSource | null) => void;

    // Form state - for generation UI
    voiceoverName: string;
    setVoiceoverName: (name: string) => void;

    // List state - cached voiceovers
    voiceovers: VoiceoverEntry[];
    setVoiceovers: (voiceovers: VoiceoverEntry[]) => void;
    voiceoversLoading: boolean;
    setVoiceoversLoading: (loading: boolean) => void;

    // Selection state - persisted via Zustand
    selectedVoiceoverId: string | null;
    setSelectedVoiceoverId: (id: string | null) => void;

    // Sync timeline - auto-loaded when selection changes
    selectedVoiceoverSyncTimeline: SyncTimeline | null;

    // Actions
    refreshVoiceovers: () => Promise<void>;
}
```

**Key Effects**:

1. **Load voiceovers on mount/video change** (lines 105-121):
   ```typescript
   useEffect(() => {
       if (!videoId) return;

       // Skip initial fetch if server provided data (eliminates waterfall)
       if (isInitialLoadRef.current && hasInitialVoiceovers) {
           // Validate selection against initial voiceovers
           // If selected ID not in list, clear selection
       } else {
           // Fetch from API
           refreshVoiceovers();
       }
   }, [videoId, voiceoverProcessing, hasInitialVoiceovers, ...]);
   ```

2. **Load sync timeline when voiceover selected** (lines 123-151):
   ```typescript
   useEffect(() => {
       if (!selectedVoiceoverId || !videoId) {
           setSelectedVoiceoverSyncTimeline(null);
           return;
       }

       // Async fetch with cancellation support
       const fetchSyncTimeline = async () => {
           try {
               const timeline = await getVoiceoverSyncTimeline(videoId, selectedVoiceoverId);
               if (!cancelled) {
                   setSelectedVoiceoverSyncTimeline(timeline);
               }
           } catch (error) {
               if (!cancelled) {
                   setSelectedVoiceoverSyncTimeline(null);
               }
           }
       };

       fetchSyncTimeline();

       return () => {
           cancelled = true;
       };
   }, [videoId, selectedVoiceoverId]);
   ```

**State Persistence**:
- `selectedVoiceoverId` is stored in `useVideoStateStore` (per-video localStorage)
- Using Zustand's `persist` middleware with localStorage
- Automatically restored on page reload
- Set via `setSelectedVoiceoverIdStore(videoId, id)`

### Hook: `useVoiceoverSync`

**Location**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useVoiceoverSync.ts`

**Purpose**: Audio/Video synchronization for voiceover playback

**Architecture**:
```
Audio is the master clock
    ↓
Video adjusts playback rate to follow audio timeline
    ↓
Uses sync_timeline.json to map audio_time → video_time
```

**Sync Timeline Structure**:
```typescript
interface SyncTimeline {
    segments: SyncTimelineSegment[];
}

interface SyncTimelineSegment {
    srcStart: number;      // Video time (seconds)
    srcEnd: number;
    dstStart: number;      // Audio time (seconds)
    dstEnd: number;
    speed: number;         // Playback speed multiplier
}
```

**Key Formula**:
```
video_time = src_start + (audio_time - dst_start) * speed
audio_time = dst_start + (video_time - src_start) / speed
```

**Core Features**:

1. **Binary search for segment lookup** (lines 57-94):
   - `findSegmentByAudioTime()`: Find segment by audio playback position
   - `findSegmentByVideoTime()`: Find segment by video position
   - Used for fast timeline navigation

2. **Time mapping functions** (lines 96-131):
   - `mapAudioToVideo()`: Convert audio time → video time
   - `mapVideoToAudio()`: Convert video time → audio time
   - Both clamp results to segment boundaries

3. **Sync tick loop** (lines 165-210):
   - Runs every `tickIntervalMs` (default 200ms) when syncing
   - Compares actual video position vs expected position
   - Adjusts video playback rate smoothly to stay in sync
   - Handles drift tolerance (default 0.2s) with three strategies:
     - Small drift: Smooth rate adjustment via `lerp()`
     - Large drift: Direct seek
     - Extreme drift: Direct seek + clamp rate to 0.25-4.0x

4. **Mode transitions** (lines 241-428):
   - `startSync(timeline)`: Enter sync mode
     - Mutes video (audio will play voiceover)
     - Preserves current video position by converting to audio time
     - Waits for audio metadata before setting sync
     - Stores pre-sync video state (mute/volume) for restore
   - `stopSync()`: Exit sync mode
     - Restores pre-sync video state
     - Stops sync tick loop
     - Pauses audio

5. **Playback control** (lines 493-539):
   - `play()`: Plays audio (in sync mode) or video (normal mode)
   - `pause()`: Pauses both
   - `seekToVideoTime()`: Converts to audio time internally
   - `setUserRate()`: Updates playback speed for both audio+video

6. **Browser integration** (lines 583-666):
   - Intercepts native video controls
   - Handles visibility changes (Chrome auto-pauses muted videos in background)
   - Restores video playback when tab becomes visible again
   - Mirrors user seeks from video to audio timeline

### Integration - VideoPlayer Component

**File**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`

**Usage** (lines 78-127):
```typescript
// Hook initialization
const {
    videoRef,
    audioRef,
    isActive: isSyncActive,
    startSync,
    stopSync,
    seekToVideoTime,
    setUserRate,
    play: syncPlay,
    pause: syncPause,
    getCurrentVideoTime,
} = useVoiceoverSync();

// Effect: Start/stop sync when voiceover changes
useEffect(() => {
    if (voiceoverId && syncTimeline) {
        startSync(syncTimeline);
    } else {
        stopSync();
    }
}, [voiceoverId, syncTimeline, startSync, stopSync]);
```

### Integration - VideoPlayerSection Component

**File**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayerSection.tsx`

**Props** (lines 17-18):
```typescript
selectedVoiceoverId: string | null;
selectedVoiceoverSyncTimeline: SyncTimeline | null;
```

**Usage** (lines 249-250):
```typescript
<VideoPlayer
    voiceoverId={selectedVoiceoverId}
    syncTimeline={selectedVoiceoverSyncTimeline}
    {...}
/>
```

### Integration - VideoPageClient

**File**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/app/video/[id]/VideoPageClient.tsx`

**State flow**:
```typescript
// Line 100-106: From useVideoPageState
const {
    voiceovers,
    setVoiceovers,
    voiceoversLoading,
    selectedVoiceoverId,
    setSelectedVoiceoverId,
    selectedVoiceoverSyncTimeline,
    ...
} = useVideoPageState({ videoId, ... });

// Line 302: Reset repeat state when voiceover changes
useEffect(() => {
    resetRepeatState();
}, [videoId, selectedVoiceoverId, playerSubtitles, resetRepeatState]);

// Line 425-426: Pass to VideoPlayerSection
<VideoPlayerSection
    selectedVoiceoverId={selectedVoiceoverId}
    selectedVoiceoverSyncTimeline={selectedVoiceoverSyncTimeline}
    {...}
/>

// Line 667-670: Voiceover selection dialog
<VoiceoverDialog
    selectedVoiceoverId={selectedVoiceoverId}
    setSelectedVoiceoverId={setSelectedVoiceoverId}
    voiceovers={voiceovers}
    voiceoversLoading={voiceoversLoading}
    {...}
/>
```

---

## 3. Subtitle Auto-Switch

### Purpose
Pure logic module for managing automatic subtitle mode switching when page visibility changes.

**Scenario**: User is learning and has both source and target subtitles visible. When they switch to another tab, the system automatically switches to target (translated) mode for background listening. When they return, it restores the previous mode.

### Module: `subtitleAutoSwitch.ts`

**Location**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/subtitleAutoSwitch.ts`

**Design Philosophy**: Pure functions for comprehensive unit testing without React dependencies

**Types**:
```typescript
interface AutoSwitchState {
    /** The subtitle mode before auto-switch occurred */
    previousMode: SubtitleDisplayMode | null;
    /** Whether the last mode change was due to auto-switch (vs manual user action) */
    wasAutoSwitched: boolean;
}

interface AutoSwitchContext {
    enabled: boolean;
    hasTranslation: boolean;
    currentMode: SubtitleDisplayMode;
    state: AutoSwitchState;
}

type SubtitleDisplayMode = "source" | "target" | "dual" | "dual_reversed";
```

**Public API**:

1. **`getAutoSwitchModeOnHide(ctx)`** - Determine mode when page becomes hidden
   ```typescript
   // Input: { enabled, hasTranslation, currentMode }
   // Returns: "target" | null

   Logic:
   - If disabled or no translation: return null
   - If already on target: return null (no need to switch)
   - Otherwise: return "target" (switch for background listening)
   ```

2. **`getAutoSwitchModeOnShow(ctx)`** - Determine mode when page becomes visible
   ```typescript
   // Input: { enabled, hasTranslation, currentMode, state }
   // Returns: SubtitleDisplayMode | null

   Logic:
   - If disabled or wasn't auto-switched: return null
   - If user manually changed mode while away (currentMode !== "target"): return null
   - Otherwise: return state.previousMode (restore previous)
   ```

3. **`createAutoSwitchState()`** - Initial state
   ```typescript
   // Returns: { previousMode: null, wasAutoSwitched: false }
   ```

4. **`updateStateOnAutoSwitch(previousMode)`** - Record that auto-switch occurred
   ```typescript
   // Input: SubtitleDisplayMode
   // Returns: { previousMode, wasAutoSwitched: true }
   ```

5. **`resetAutoSwitchState()`** - Reset after restore or manual override
   ```typescript
   // Returns: { previousMode: null, wasAutoSwitched: false }
   ```

### Usage Pattern in FocusModeHandler

**Initialization** (line 76):
```typescript
const autoSwitchStateRef = useRef<AutoSwitchState>(createAutoSwitchState());
```

**On page hide** (lines 118-131):
```typescript
if (autoSwitchSubtitlesOnLeave) {
    hideDebounceRef.current = setTimeout(() => {
        const newMode = getAutoSwitchModeOnHide({
            enabled: autoSwitchSubtitlesOnLeave,
            hasTranslation,
            currentMode: subtitleMode,
        });

        if (newMode !== null) {
            autoSwitchStateRef.current = updateStateOnAutoSwitch(subtitleMode);
            onSubtitleModeChange(newMode);
        }
    }, AUTO_SWITCH_DEBOUNCE_MS);  // 1500ms debounce
}
```

**On page show** (lines 144-156):
```typescript
if (autoSwitchSubtitlesOnLeave) {
    const restoreMode = getAutoSwitchModeOnShow({
        enabled: autoSwitchSubtitlesOnLeave,
        hasTranslation,
        currentMode: subtitleMode,
        state: autoSwitchStateRef.current,
    });

    if (restoreMode !== null) {
        onSubtitleModeChange(restoreMode);
    }
    autoSwitchStateRef.current = resetAutoSwitchState();
}
```

### Test Coverage

**File**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/__tests__/subtitleAutoSwitch.test.ts`

Comprehensive tests covering:
- Mode switching (source → target, dual → target, dual_reversed → target)
- Guard conditions (disabled, no translation, already on target)
- State transitions (create, update, reset)
- Manual override detection (user changes mode while away)
- Mode restoration

---

## 4. Type System - SubtitleDisplayMode

**File**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`

```typescript
export type SubtitleDisplayMode = "source" | "target" | "dual" | "dual_reversed";

export interface PlaybackSettings {
    autoPauseOnLeave: boolean;
    autoResumeOnReturn: boolean;
    autoSwitchSubtitlesOnLeave: boolean;
    summaryThresholdSeconds: number;
    subtitleContextWindowSeconds: number;
    subtitleRepeatCount: number;
}
```

**Meanings**:
- `source`: Original language subtitles only
- `target`: Translated language subtitles only
- `dual`: Both source and target (source top, target bottom)
- `dual_reversed`: Both (target top, source bottom)

---

## 5. Data Flow Diagram

```
VideoPageClient
    ↓
useVideoPageState (aggregates all video-related state)
    ├─ useVoiceoverManagement
    │   ├─ selectedVoiceoverId (persisted in Zustand)
    │   ├─ selectedVoiceoverSyncTimeline (loaded from API)
    │   └─ voiceovers[] (cached from API)
    │
    └─ [other state: content, timeline, etc.]

                    ↓

VideoPlayerSection (passes voiceover state down)
    ↓
VideoPlayer
    ├─ useVoiceoverSync (manages audio/video sync)
    │   ├─ videoRef, audioRef
    │   ├─ isActive (sync mode status)
    │   └─ [sync control methods]
    │
    └─ VideoControls (UI for playback)

                    ↓

FocusModeHandler (independent component)
    ├─ Listens to visibilitychange
    ├─ Calls getAutoSwitchModeOnHide/Show
    ├─ Calls onSubtitleModeChange to update state
    ├─ Detects missed content
    └─ Opens MissedContentDialog
```

---

## 6. Settings Integration

All three features are driven by `GlobalSettingsStore`:

**File**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useGlobalSettingsStore.ts`

```typescript
interface PlaybackSettings {
    autoPauseOnLeave: boolean;          // Used by FocusModeHandler
    autoResumeOnReturn: boolean;         // Used by FocusModeHandler
    autoSwitchSubtitlesOnLeave: boolean; // Used by FocusModeHandler & subtitleAutoSwitch
    summaryThresholdSeconds: number;     // Used by FocusModeHandler
    subtitleContextWindowSeconds: number;
    subtitleRepeatCount: number;
}
```

Settings are accessed in VideoPageClient:
```typescript
const { playback, language, hideSidebars, viewMode, live2d } = settings;
const autoPauseOnLeave = playback.autoPauseOnLeave;
const autoResumeOnReturn = playback.autoResumeOnReturn;
const autoSwitchSubtitlesOnLeave = playback.autoSwitchSubtitlesOnLeave;
```

---

## 7. Key Design Patterns

### Single Responsibility Principle
- `useVoiceoverManagement`: Only manages voiceover list & selection
- `useVoiceoverSync`: Only handles A/V sync logic
- `FocusModeHandler`: Only handles visibility changes & missed content
- `subtitleAutoSwitch`: Pure logic module with no side effects

### Separation of Concerns
- **State layer** (Zustand): Persistence
- **Hook layer**: Business logic & API integration
- **Component layer**: UI & event handling
- **Utility layer**: Pure functions

### Cancellation Support
All async operations support cancellation:
```typescript
let cancelled = false;

const fetchData = async () => {
    try {
        const data = await apiCall();
        if (!cancelled) {
            setState(data);
        }
    } catch (error) {
        if (!cancelled) {
            setError(error);
        }
    }
};

return () => {
    cancelled = true;
};
```

### Ref-Based State for Non-UI Data
```typescript
const wasPlayingRef = useRef(false);        // Don't need re-render
const autoSwitchStateRef = useRef(state);    // Only FocusModeHandler uses it
const hideDebounceRef = useRef<...>(null);   // Debounce timer
```

### Debouncing
Subtitle auto-switch uses manual debounce (1.5s) to avoid false triggers:
```typescript
// Cancel on return (clear timeout if returning quickly)
if (hideDebounceRef.current) {
    clearTimeout(hideDebounceRef.current);
    hideDebounceRef.current = null;
}
```

---

## 8. Common Development Tasks

### Adding a New Subtitle Mode

1. Update `SubtitleDisplayMode` type in `types.ts`
2. Update subtitle display logic in subtitle renderer
3. Update `subtitleAutoSwitch.ts` if mode should auto-switch to target
4. Add test cases in `subtitleAutoSwitch.test.ts`
5. Update settings UI to show new option

### Modifying Voiceover Sync Algorithm

1. Edit `useVoiceoverSync.ts` (the `tick` function is the core loop)
2. Key parameters:
   - `driftTolerance` (default 0.2s): threshold before seeking
   - `tickIntervalMs` (default 200ms): sync check frequency
   - Video rate limits: clamped to 0.25-4.0x
3. Update sync timeline generation logic on backend if needed

### Changing Auto-Leave Behavior

1. Modify thresholds in `FocusModeHandler` (e.g., `AUTO_SWITCH_DEBOUNCE_MS`)
2. Update settings in `PlaybackSettings` in `types.ts`
3. Add/remove handlers in `handleVisibilityChange()`
4. Update settings UI in PlayerTab

### Testing Auto-Switch Logic

```typescript
// Pure functions are easy to test
import { getAutoSwitchModeOnHide, getAutoSwitchModeOnShow } from '@/lib/subtitleAutoSwitch';

test('switches to target when hiding', () => {
    const result = getAutoSwitchModeOnHide({
        enabled: true,
        hasTranslation: true,
        currentMode: 'source'
    });
    expect(result).toBe('target');
});
```

---

## 9. Performance Considerations

### Voiceover Sync
- **Tick loop**: 200ms intervals (50% less frequent than 120fps video)
- **Binary search**: O(log n) segment lookup
- **Rate smoothing**: Lerp-based smooth adjustment instead of discrete jumps
- **Cancellation**: Prevents memory leaks from stale fetches

### Subtitle Auto-Switch
- **Debounce**: 1.5s delay prevents excessive switching on brief tab switches
- **Pure functions**: No side effects, easy to optimize
- **Ref-based state**: No re-renders for internal state

### Voiceover Loading
- **Server-side initial data**: Eliminates client waterfall on page load
- **Selective validation**: Only checks if selected ID still exists
- **One-time initial load**: Skips redundant fetch if server provided data

---

## 10. File Structure Summary

```
frontend/
├── hooks/
│   ├── useVoiceoverManagement.ts      # Main voiceover state hook
│   ├── useVoiceoverSync.ts            # A/V sync for voiceover playback
│   ├── useVideoPageState.ts           # Aggregates all video-page state
│   └── useVideoPageHandlers.ts        # Event handlers
│
├── components/
│   ├── features/
│   │   └── FocusModeHandler.tsx       # Visibility change handler
│   ├── video/
│   │   ├── VideoPlayer.tsx            # Main player with sync support
│   │   ├── VideoPlayerSection.tsx     # Player + slide tabs
│   │   └── VideoControls.tsx          # Playback controls
│   └── dialogs/
│       └── MissedContentDialog.tsx    # Catch-up prompt on return
│
├── lib/
│   ├── subtitleAutoSwitch.ts          # Pure functions for mode switching
│   ├── subtitleAutoSwitch.md          # Documentation
│   ├── __tests__/
│   │   └── subtitleAutoSwitch.test.ts # Comprehensive tests
│   ├── api/
│   │   ├── voiceover.ts               # API calls for voiceoverAPI
│   │   └── subtitle.ts                # API calls for subtitles
│   └── [other utilities]
│
├── stores/
│   ├── useVideoStateStore.ts          # Per-video state (selectedVoiceoverId)
│   ├── useGlobalSettingsStore.ts      # Global settings (autoPause, autoSwitch)
│   └── types.ts                       # Type definitions
│
└── app/video/[id]/
    └── VideoPageClient.tsx            # Main page component
```

---

## 11. Key Takeaways

1. **Auto-leave** is driven by `visibilitychange` event with 1.5s debounce for subtitle switching
2. **Voiceover selection** is persisted in Zustand store and triggers sync timeline load
3. **Voiceover sync** uses binary search + smooth rate adjustment to keep audio & video in sync
4. **Subtitle auto-switch** is pure logic that can be tested independently
5. All features work together: auto-leave switches subtitles to target → background listening with voiceover sync
6. Settings integrate via `GlobalSettingsStore` for centralized configuration
7. Three-tier architecture: Persistence (Zustand) → Logic (Hooks) → UI (Components)
