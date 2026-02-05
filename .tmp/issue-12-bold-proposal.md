# Bold Proposal: Multi-Track Subtitle Switching with Auto-Toggle

## Innovation Summary

A Netflix-inspired multi-track subtitle system that treats subtitles as first-class "tracks" with metadata, enables quick toggle switching between original/translated pairs, and automatically switches subtitle language based on page visibility - showing translated subtitles when away (for background listening) and original when actively watching (for language learning).

## Original User Request

**Feature Requirements:**
1. A system to manage multiple subtitle tracks (original and translated) with support for named copies
2. The ability to specify an original subtitle track (from video's original audio or Whisper-generated)
3. The ability to specify a translated subtitle track
4. A video player toggle button to quickly switch between original and translated tracks
5. Auto-switch behavior: automatically switch to translated when leaving the video, and back to original when watching
6. Extend the existing "auto pause after your leave" functionality to detect when user leaves

This section preserves the user's exact requirements so that critique and reducer agents can verify alignment with the original intent.

## Research Findings

**Key insights from SOTA research:**

1. **Track Metadata Pattern (Netflix/YouTube)**: Modern video players store subtitle tracks as first-class entities with metadata (language, label, isDefault, source) rather than just file paths. This enables features like "preferred language" auto-selection and track labeling. ([FastPix Documentation](https://docs.fastpix.io/docs/subtitle-switching-and-multi-track-audio))

2. **Page Visibility API Best Practices**: The key pattern is to track `playingOnHide` state before pausing, and only resume/switch if the user was actively engaged. Simply auto-switching without tracking user intent leads to poor UX. ([MDN Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API), [MDN Blog](https://developer.mozilla.org/en-US/blog/using-the-page-visibility-api/))

3. **Dual Subtitle Language Learning**: Extensions like Language Reactor and InterSub demonstrate that learners want quick switching between "immersion mode" (target language only) and "comprehension mode" (native language) - this maps directly to the auto-switch requirement. ([InterSub](https://intersub.cc/), [Language Learning with Netflix](https://extension.appforlanguage.com/cbxchangelog/learning-language-with-netflix-changelog-updates-new-features-enhancements/))

4. **Zustand for Media State**: Zustand's simple hook-based API with persistence middleware is ideal for managing per-video subtitle track selection, as it supports the existing voiceover pattern. ([State Management Trends 2025](https://makersden.io/blog/react-state-management-in-2025))

**Files checked for current implementation:**
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`: Verified `VideoState` structure includes `subtitleModePlayer`, `subtitleModeSidebar`, `selectedVoiceoverId` - establishes pattern for track selection
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useSubtitleManagement.ts`: Current implementation loads source/target subtitles based on semantic mode, no concept of "tracks" with metadata
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx`: Already uses `visibilitychange` event at line 131-136, tracks `wasPlayingRef` for state preservation
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_subtitle_storage.py`: Files stored as `subtitle_{language}.srt`, `list_languages()` method available
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useVoiceoverManagement.ts`: Reference pattern for multi-track management with persisted selection

## Proposed Solution

### Core Architecture

The solution introduces a **Subtitle Track Registry** concept that mirrors the existing voiceover management pattern. Instead of just loading subtitles by language code, we treat each subtitle file as a "track" with rich metadata including user-defined labels, original/translated designation, and preference ordering.

Key innovation: **Auto-Switch Mode** that integrates with the existing `visibilitychange` detection in `FocusModeHandler.tsx` to automatically switch between "watching mode" (original subtitles for active learning) and "background mode" (translated subtitles for passive comprehension).

```
                    +-----------------------+
                    |   SubtitleTrackStore  |
                    |   (Zustand)           |
                    +-----------------------+
                           |
          +----------------+----------------+
          |                                 |
   +------v------+               +----------v---------+
   | Track Registry|             | Auto-Switch Mode   |
   | - tracks[]   |              | - watchingTrackId  |
   | - activeId   |              | - awayTrackId      |
   | - originalId |              | - enabled          |
   +-------------+               +-------------------+
          |                                 |
          +----------------+----------------+
                           |
                   +-------v--------+
                   | VideoPlayer    |
                   | Toggle Button  |
                   +----------------+
```

### Key Components

1. **Subtitle Track Types and Store Extensions**
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`
   - Responsibilities:
     - Define `SubtitleTrack` interface with id, language, label, isOriginal, isTranslated flags
     - Extend `VideoState` with `subtitleTracks`, `activeSubtitleTrackId`, `originalTrackId`, `translatedTrackId`
     - Add `AutoSwitchSettings` to `PlaybackSettings` for enabling/configuring auto-switch behavior
   - LOC estimate: ~45

2. **Subtitle Track Management Hook**
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useSubtitleTrackManagement.ts` (new)
   - Responsibilities:
     - Build track registry from available subtitle files
     - Manage track selection with persistence
     - Provide quick toggle between original/translated tracks
     - Integrate with existing `useSubtitleManagement` for actual subtitle loading
   - LOC estimate: ~120

3. **Auto-Switch Integration in FocusModeHandler**
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx`
   - Responsibilities:
     - Extend `handleVisibilityChange` to switch subtitle tracks based on visibility
     - Track previous track ID before switching for restoration
     - Respect user preference for auto-switch enable/disable
   - LOC estimate: ~50

4. **Video Player Track Toggle UI**
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`
   - Responsibilities:
     - Add quick toggle button (beside existing language menu) for original/translated switch
     - Visual indicator for current track (original vs translated)
     - Keyboard shortcut (e.g., 'T' for toggle)
   - LOC estimate: ~60

5. **Backend Track Listing API Enhancement**
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/subtitle.py`
   - Responsibilities:
     - New endpoint `GET /<content_id>/tracks` returning available tracks with metadata
     - Include language codes, auto-detected labels, and file existence status
   - LOC estimate: ~35

6. **Store Actions and Selectors**
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useVideoStateStore.ts`
   - Responsibilities:
     - Add actions: `setActiveSubtitleTrack`, `setOriginalTrack`, `setTranslatedTrack`
     - Add selectors for track state
   - LOC estimate: ~40

### External Dependencies

No new external dependencies required. The solution leverages:
- Existing Zustand store infrastructure
- Existing Page Visibility API usage in FocusModeHandler
- Existing subtitle storage and loading patterns

## Benefits

1. **Language Learning Optimization**: Auto-switch to original when actively watching supports immersive learning; switch to translated when away ensures comprehension of background content (e.g., during note-taking).

2. **Reduced Cognitive Load**: Quick toggle button eliminates need to open menu, select language - a single click or keyboard shortcut switches between learning modes.

3. **Consistent Architecture**: Follows the established voiceover management pattern (`selectedVoiceoverId`), making the codebase more predictable and maintainable.

4. **Future Extensibility**: Track registry concept enables future features like custom subtitle uploads, subtitle notes/highlights per track, and multi-track comparison view.

## Trade-offs

1. **Complexity**: Adds a new abstraction layer (tracks) on top of existing subtitle management. The current semantic mode system (`source`/`target`/`dual`) must coexist with track-based selection.
   - Mitigation: Keep semantic modes as the display logic; tracks determine which files to load for source/target.

2. **Learning curve**: Users must understand the difference between "subtitle mode" (how to display) and "track selection" (which files to use).
   - Mitigation: Good defaults (auto-detect original/translated from language codes) and clear UI labeling.

3. **Failure modes**:
   - Track designation mismatch (user marks wrong track as "original")
   - Auto-switch during brief tab switches may be annoying
   - Mitigation: Add threshold for auto-switch (e.g., only switch if hidden > 3 seconds), allow easy override.

## Implementation Estimate

**Total LOC**: ~450 LOC (Medium-Large)

**Breakdown**:
- Types and Store Extensions: ~45 LOC
- Track Management Hook: ~120 LOC
- Auto-Switch Integration: ~50 LOC
- Video Player Toggle UI: ~60 LOC
- Backend Track API: ~35 LOC
- Store Actions: ~40 LOC
- Documentation: ~50 LOC
- Tests: ~100 LOC (unit tests for hook, integration tests for auto-switch)

**Recommended approach**: Implement in 2-3 milestone commits:
1. Milestone 1: Track types + store + management hook (foundation)
2. Milestone 2: Toggle UI + backend API
3. Delivery: Auto-switch integration + tests

---

Sources:
- [FastPix - Subtitle Switching and Multi-Track Audio](https://docs.fastpix.io/docs/subtitle-switching-and-multi-track-audio)
- [MDN - Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)
- [MDN Blog - Using the Page Visibility API](https://developer.mozilla.org/en-US/blog/using-the-page-visibility-api/)
- [Makers Den - State Management Trends in React 2025](https://makersden.io/blog/react-state-management-in-2025)
- [InterSub - Interactive Dual Subtitles](https://intersub.cc/)
- [Language Learning with Netflix Changelog](https://extension.appforlanguage.com/cbxchangelog/learning-language-with-netflix-changelog-updates-new-features-enhancements/)
- [GitHub - Zustand State Management](https://github.com/pmndrs/zustand)
- [HLS.js Subtitle Track Controller](https://github.com/video-dev/hls.js/blob/master/docs/API.md)
