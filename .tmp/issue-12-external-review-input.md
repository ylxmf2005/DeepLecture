# External Consensus Review Task

You are an expert software architect tasked with synthesizing a consensus implementation plan from three different perspectives on the same feature.

## Context

Three specialized agents have analyzed the following requirement:

**Feature Request**: Unknown Feature

Each agent provided a different perspective:
1. **Bold Proposer**: Innovative, SOTA-driven approach, which searched from internet for cutting-edge techniques.
   - The bold proposal includes the "Original User Request" section with the verbatim feature description.
2. **Critique Agent**: Feasibility analysis and risk assessment for the aggressive solution from the **Bold Proposer**.
3. **Reducer Agent**: Simplified, "less is more" approach focusing on the core functionality from a minimalistic standpoint, by simplifying the **Bold Proposer**'s design.

## Your Task

Review all three perspectives and synthesize a **balanced, consensus implementation plan** that:

1. **Incorporates the best ideas** from each perspective
2. **Resolves conflicts** between the proposals
3. **Balances innovation with pragmatism**
4. **Maintains simplicity** while not sacrificing essential features
5. **Addresses critical risks** identified in the critique
6. **Verifies documentation accuracy** - ensure proposals cite `docs/` for current command interfaces

## Input: Combined Report

Below is the combined report containing all three perspectives:

---

# Multi-Agent Debate Report: Unknown Feature

**Generated**: 2026-02-04 10:40

This document combines three perspectives from our multi-agent debate-based planning system:
1. **Report 1**: issue-12-bold-proposal.md
2. **Report 2**: issue-12-critique.md
3. **Report 3**: issue-12-reducer.md

---

## Part 1: issue-12-bold-proposal.md

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

---

## Part 2: issue-12-critique.md

# Proposal Critique: Multi-track Subtitle Switching with Auto-Toggle

## Executive Summary

The proposal introduces a reasonable concept for multi-track subtitle management but **significantly over-engineers the solution** for the stated requirements. The existing codebase already has a semantic subtitle display mode system (`source`/`target`/`dual`/`dual_reversed`) that handles original vs. translated subtitles - the proposal duplicates this with a new "track" abstraction without clearly justifying the additional complexity. The auto-switch feature is feasible but the proposal lacks clarity on several key UX edge cases.

## Files Checked

**Documentation and codebase verification:**
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/demo/dual-subtitle.md`: Verified current dual subtitle documentation; no mention of multi-track concept
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/demo/focus-mode.md`: Minimal documentation; does not detail auto-pause behavior
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`: Verified existing `SubtitleDisplayMode` type and `VideoState` structure
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useVideoStateStore.ts`: Verified store already persists subtitle mode per video
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useSubtitleManagement.ts`: Verified current subtitle loading logic with `source`/`target` paradigm
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx`: Verified visibility change handling exists
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`: Verified subtitle mode selector UI already exists
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/subtitle.py`: Verified backend subtitle routes
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_subtitle_storage.py`: Verified `list_languages()` method exists
- `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/subtitle.py`: Verified storage protocol includes `list_languages`

## Assumption Validation

### Assumption 1: A new "Subtitle Track" abstraction is needed

- **Claim**: The proposal introduces `SubtitleTrack` interface with id, language, label, isOriginal, isTranslated flags to manage multiple subtitle files as "tracks"
- **Reality check**: The codebase already has `SubtitleDisplayMode` (`"source" | "target" | "dual" | "dual_reversed"`) which semantically represents original vs. translated. The `useSubtitleManagement` hook loads `subtitlesSource` and `subtitlesTarget` based on `originalLanguage` and `targetLanguage` from global settings.
- **Status**: QUESTIONABLE
- **Evidence**:
  - `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts:121` defines `SubtitleDisplayMode`
  - `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useSubtitleManagement.ts:47-51` already loads source and target subtitles
  - The current system implicitly defines "original" as the source language subtitle and "translated" as the target language subtitle

### Assumption 2: Named copies of subtitle tracks are required

- **Claim**: Users need "named copies" of subtitle tracks
- **Reality check**: The user request mentions "named copies" but the proposal does not explain the use case. The backend storage (`fs_subtitle_storage.py:67`) stores subtitles as `subtitle_{language}.srt`. There is no mechanism for user-defined labels on subtitle files.
- **Status**: QUESTIONABLE
- **Evidence**:
  - `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_subtitle_storage.py:67` shows glob pattern for discovering subtitles
  - No existing metadata storage for user-defined labels per subtitle file

### Assumption 3: FocusModeHandler can be extended for auto-switch

- **Claim**: The proposal extends `handleVisibilityChange` in `FocusModeHandler` to switch subtitle tracks
- **Reality check**: `FocusModeHandler` (lines 83-129) handles visibility changes with logic for auto-pause and missed content detection. It does NOT currently manage subtitle state. The component receives `autoPauseOnLeave` and `autoResumeOnReturn` as props but has no awareness of subtitle selection.
- **Status**: VALID (technically feasible but scope creep)
- **Evidence**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx:83-129`

### Assumption 4: Voiceover management pattern can be mirrored for subtitles

- **Claim**: Solution mirrors "existing voiceover management pattern"
- **Reality check**: Voiceover management (`useVoiceoverManagement.ts`) manages a list of user-created voiceovers with selection persistence via Zustand store. Subtitles are fundamentally different - they are automatically generated artifacts (Whisper + translation), not user-created entities. The pattern does not directly apply.
- **Status**: QUESTIONABLE
- **Evidence**:
  - `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useVoiceoverManagement.ts:62` shows voiceovers as `VoiceoverEntry[]`
  - Voiceovers have user-defined names and are explicitly created; subtitles are system-generated

### Assumption 5: Backend needs a new `/tracks` endpoint

- **Claim**: New endpoint `GET /<content_id>/tracks` returning available tracks with metadata
- **Reality check**: The backend already has `list_languages()` in `SubtitleStorageProtocol` but no route exposes it. Adding a tracks listing endpoint is reasonable, but the metadata schema (isOriginal, isTranslated, labels) does not exist in the current storage model.
- **Status**: PARTIALLY VALID
- **Evidence**:
  - `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/interfaces/subtitle.py:68-78` shows `list_languages` exists
  - `/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/subtitle.py` has no listing endpoint

## Technical Feasibility Analysis

### Integration with Existing Code

**Compatibility**: POOR - The proposal introduces concepts that conflict with existing patterns

- **SubtitleDisplayMode vs SubtitleTrack**: The codebase uses semantic modes (`source`/`target`/`dual`/`dual_reversed`) that are language-agnostic. The proposal introduces track-based selection that operates at a different abstraction level. These must coexist, creating confusion.

- **useSubtitleManagement already handles source/target**: Lines 92-127 in `useSubtitleManagement.ts` already fetch source and target subtitles based on global language settings. Adding a track registry duplicates this responsibility.

- **VideoState already persists subtitle mode**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts:143-167` shows `VideoState` includes `subtitleModePlayer` and `subtitleModeSidebar`. Adding `activeSubtitleTrackId`, `originalTrackId`, `translatedTrackId` creates parallel state that may conflict.

**Conflicts**:
- Dual state management (semantic mode vs track ID)
- Unclear precedence when both are set
- Migration path for existing stored preferences unclear

### Complexity Analysis

**Is this complexity justified?**

The proposal introduces approximately 450 LOC across 6 components for what could be achieved with much simpler changes:

1. **Quick toggle already exists**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx:488-545` shows a language selector menu that toggles between source/target/dual modes. Adding a quick-toggle button requires ~20 LOC, not a new track abstraction.

2. **Auto-switch is the only novel feature**: The visibility-based subtitle switching is new functionality. This could be implemented by adding ~30 LOC to `FocusModeHandler` plus ~10 LOC to store settings.

3. **Simpler alternatives overlooked**:
   - Add `autoSwitchSubtitleOnLeave: boolean` and `backgroundSubtitleMode: SubtitleDisplayMode` to `PlaybackSettings`
   - Extend `FocusModeHandler` to call `setSubtitleModePlayer` on visibility change
   - No new hooks, interfaces, or backend changes needed

## Risk Assessment

### HIGH Priority Risks

1. **State Synchronization Complexity**
   - Impact: Two parallel systems for subtitle selection (semantic mode vs track ID) will cause bugs where user intent is unclear
   - Likelihood: High
   - Mitigation: Choose one approach - either extend semantic modes or replace with tracks, not both

2. **User Experience Regression**
   - Impact: Adding "track designation" step before users can toggle between original/translated increases friction
   - Likelihood: High - The proposal requires users to "designate" original and translated tracks
   - Mitigation: Auto-detect based on language settings; source language = original, target language = translated

3. **Breaking Change to Persistence**
   - Impact: Changing `VideoState` schema requires migration; version bump to `STORAGE_VERSIONS.VIDEO_STATE`
   - Likelihood: Certain if implemented as proposed
   - Mitigation: Use existing `subtitleModePlayer` field; add only `autoSwitchEnabled: boolean`

### MEDIUM Priority Risks

1. **Auto-Switch Annoyance**
   - Impact: Brief tab switches trigger subtitle changes, disrupting experience
   - Likelihood: Medium
   - Mitigation: Add debounce (e.g., 2 seconds) before switching; only switch if visibility change persists

2. **FocusModeHandler Scope Creep**
   - Impact: Component already handles auto-pause, missed content summary, Smart Skip integration. Adding subtitle switching further bloats it.
   - Likelihood: Certain
   - Mitigation: Extract subtitle auto-switch into separate hook `useAutoSubtitleSwitch` that FocusModeHandler calls

3. **Backend Endpoint Not Needed**
   - Impact: New endpoint adds maintenance burden without clear benefit
   - Likelihood: High - Frontend already knows original/target languages from global settings
   - Mitigation: Defer backend changes; use existing language settings to infer tracks

### LOW Priority Risks

1. **Keyboard Shortcut Conflict**
   - Impact: Proposed 'T' shortcut may conflict with existing shortcuts
   - Likelihood: Low - Need to verify no conflicts
   - Mitigation: Check existing keyboard handlers in VideoPlayer

## Critical Questions

These must be answered before implementation:

1. **What problem does the "track" abstraction solve that semantic modes do not?** The current source/target paradigm already distinguishes original from translated. Why add track IDs?

2. **What are "named copies" of subtitle tracks?** The user request mentions this but it is undefined. Are these user-edited versions? Different translation variants? Different enhancement levels?

3. **How should auto-switch interact with dual mode?** If user is in "dual" mode (showing both), what happens on visibility change? Switch to target-only? Stay in dual?

4. **Should auto-switch respect manual overrides?** If user manually selects "source" mode, should visibility changes still trigger switching?

5. **What is the debounce strategy?** Brief tab switches (Cmd+Tab to check a notification) should not trigger subtitle switching.

6. **Why does the backend need a tracks endpoint?** The frontend already has global language settings that define source and target. What additional metadata justifies a new API?

## Recommendations

### Must Address Before Proceeding

1. **Remove the track abstraction entirely**: The proposal conflates two concerns:
   - (A) Quick toggle between original/translated - already solved by semantic modes
   - (B) Auto-switch on visibility - can be added with ~40 LOC to existing system

   Implement only (B) using existing `SubtitleDisplayMode` and `setSubtitleModePlayer`.

2. **Define auto-switch behavior for dual mode**: Must specify what "translated when away" means when user prefers dual view.

3. **Add debounce to auto-switch**: Visibility changes should persist for 1-2 seconds before triggering subtitle switch to avoid annoyance from brief tab switches.

### Should Consider

1. **Separate auto-switch into dedicated hook**: Create `useAutoSubtitleSwitch` rather than extending FocusModeHandler directly, following single responsibility principle.

2. **Use existing settings storage**: Add `autoSwitchEnabled` and `backgroundSubtitleMode` to `PlaybackSettings` in `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts:29-35` rather than new state structures.

3. **Add quick-toggle button to VideoControls**: A single button that cycles through source -> target -> dual (if available) would satisfy the toggle requirement with minimal complexity.

### Nice to Have

1. **Persist background mode preference**: Store which mode user prefers when away (target vs dual) so auto-switch feels personalized.

2. **Visual feedback on auto-switch**: Toast notification or subtle indicator when subtitle mode changes due to visibility.

## Overall Assessment

**Feasibility**: Medium - The core auto-switch feature is feasible, but the track abstraction adds unjustified complexity.

**Complexity**: Over-engineered - The proposal introduces 450 LOC for what could be achieved with approximately 60 LOC by extending existing patterns.

**Readiness**: Needs significant revision

**Bottom line**: Reject the current proposal and request a simplified version that:
1. Uses existing `SubtitleDisplayMode` instead of introducing `SubtitleTrack`
2. Adds `autoSwitchSubtitleOnLeave` setting to `PlaybackSettings`
3. Extends `FocusModeHandler` with ~30 LOC to switch between modes on visibility change
4. Adds a quick-toggle button to VideoPlayer controls (~30 LOC)
5. Defers the `/tracks` backend endpoint unless a concrete use case for track metadata emerges

The "named copies" feature from the user request is completely unaddressed and needs clarification before any implementation begins.

---

## Part 3: issue-12-reducer.md

# Simplified Proposal: Multi-track Subtitle Toggle with Auto-Switch

## Simplification Summary

This proposal eliminates the "Subtitle Track Registry" abstraction entirely by recognizing that the existing `SubtitleDisplayMode` type (`source` | `target` | `dual` | `dual_reversed`) already provides multi-track semantics. The auto-switch feature integrates directly into the existing `FocusModeHandler.tsx` visibility logic with ~30 LOC rather than creating new hooks. The toggle button reuses the existing language dropdown pattern with a single keyboard shortcut addition.

## Files Checked

**Documentation and codebase verification:**
- `/Users/EthanLee/Desktop/CourseSubtitle/CLAUDE.md`: Verified project architecture (clean architecture layers)
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/README.md`: Project documentation location
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`: Found existing `SubtitleDisplayMode` with `source`/`target`/`dual`/`dual_reversed` - this IS the "track" abstraction
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useSubtitleManagement.ts`: Already loads source and target subtitles, manages mode switching
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx`: Already has `visibilitychange` handler with pause/resume logic
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`: Already has language menu with all modes, just needs toggle shortcut
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useVideoStateStore.ts`: Already has `setSubtitleModePlayer` action and persistence

## Core Problem Restatement

**What we're actually solving:**
Users want to quickly toggle between source (original) and target (translated) subtitles while watching, and have subtitles auto-switch to translated when they leave the page (for background listening) and back to source when they return (for active learning).

**What we're NOT solving:**
- Named subtitle copies or user-defined labels (the system only has source/target, not arbitrary tracks)
- Backend track metadata API (subtitles are already identified by language code, no new abstraction needed)
- Track registry pattern (existing `SubtitleDisplayMode` already represents "tracks")
- Preference ordering or complex track selection (just source/target toggle)

## Complexity Analysis

### Removed from Original

1. **Subtitle Track Types and Store Extensions (~45 LOC)**
   - Why it's unnecessary: `SubtitleDisplayMode` already defines tracks semantically. Adding `SubtitleTrack` interface with `id`, `isOriginal`, `isTranslated` flags duplicates what `"source"` and `"target"` values already mean.
   - Impact of removal: None - existing types suffice
   - Can add later if needed: Yes, if we ever support arbitrary named tracks

2. **Subtitle Track Management Hook (~120 LOC)**
   - Why it's unnecessary: `useSubtitleManagement.ts` already manages loading and mode switching. The "track registry" concept is artificial - we only have two tracks (source/target).
   - Impact of removal: None - existing hook already does this
   - Can add later if needed: Yes, if we need more complex track management

3. **Backend Track Listing API (~35 LOC)**
   - Why it's unnecessary: Frontend already knows available tracks from `content.translationStatus === "ready"`. No API needed to discover that "source" and "target" exist.
   - Impact of removal: None - no new API calls required
   - Can add later if needed: Yes, trivially

4. **New Store Actions (~40 LOC)**
   - Why it's unnecessary: `setSubtitleModePlayer` already exists and works. The proposal's `setActiveSubtitleTrack`, `setOriginalTrack`, `setTranslatedTrack` are redundant wrappers.
   - Impact of removal: None - existing actions suffice
   - Can add later if needed: Yes

### Retained as Essential

1. **Auto-Switch in FocusModeHandler**
   - Why it's necessary: Core user requirement - auto-switch on visibility change
   - Simplified approach: Add ~30 LOC to existing `handleVisibilityChange` function, no new hook needed

2. **Quick Toggle Button + Keyboard Shortcut**
   - Why it's necessary: Core user requirement - fast switching between source/target
   - Simplified approach: Add a single toggle button next to existing language menu, add `T` key handler (~25 LOC total in VideoPlayer.tsx)

3. **Settings for Auto-Switch Enable/Disable**
   - Why it's necessary: User may not want auto-switch behavior
   - Simplified approach: Add one boolean to existing `PlaybackSettings` type (~5 LOC in types.ts, ~10 LOC in settings store)

### Deferred for Future

1. **Track Metadata and Labels**
   - Why we can wait: Current use case is just source/target switching
   - When to reconsider: If users request multiple subtitle files per language

2. **Keyboard Shortcut Customization**
   - Why we can wait: `T` is reasonable default
   - When to reconsider: If users request custom key bindings

## Minimal Viable Solution

### Core Components

1. **Settings Extension**: Add `autoSwitchSubtitles: boolean` to `PlaybackSettings`
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`
   - Responsibilities: Store user preference for auto-switch
   - LOC estimate: ~8 LOC
   - Simplifications applied: Single boolean instead of complex settings object

2. **Auto-Switch Logic**: Extend existing visibility handler
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/features/FocusModeHandler.tsx`
   - Responsibilities: Switch to target on leave, restore previous mode on return
   - LOC estimate: ~35 LOC
   - Simplifications applied: Inline in existing handler, no new hook

3. **Toggle Button + Shortcut**: Add to existing VideoPlayer
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`
   - Responsibilities: Quick source/target toggle, keyboard shortcut `T`
   - LOC estimate: ~30 LOC
   - Simplifications applied: Reuse existing button styling, minimal UI addition

4. **Settings Store Actions**: Add setter for auto-switch setting
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useGlobalSettingsStore.ts`
   - Responsibilities: Persist auto-switch preference
   - LOC estimate: ~12 LOC
   - Simplifications applied: Follow existing pattern for other settings

5. **Settings UI**: Add toggle in Player settings tab
   - Files: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/dialogs/settings/PlayerTab.tsx`
   - Responsibilities: UI for enabling/disabling auto-switch
   - LOC estimate: ~15 LOC
   - Simplifications applied: Reuse existing toggle component pattern

### Implementation Strategy

**Approach**: Extend existing components inline rather than creating new abstractions

**Key simplifications:**
- No new hook - add logic directly to `FocusModeHandler`
- No new API - leverage existing content status checks
- No new store - extend existing `PlaybackSettings` type
- No track abstraction - `"source"` and `"target"` strings ARE the track identifiers
- Reuse existing subtitle mode switching - `setSubtitleModePlayer` already works

### No External Dependencies

No new dependencies required. All functionality builds on:
- Existing Zustand stores
- Existing `visibilitychange` event handling
- Existing subtitle mode infrastructure

## Comparison with Original

| Aspect | Original Proposal | Simplified Proposal |
|--------|------------------|---------------------|
| Total LOC | ~450 | ~100 (78% reduction) |
| Files | 6 files (2 new) | 5 files (0 new) |
| New Hooks | 1 (useSubtitleTrackManagement) | 0 |
| New Types | 3 (SubtitleTrack, etc.) | 0 (1 boolean field) |
| New APIs | 1 endpoint | 0 |
| Dependencies | None | None |
| Complexity | Medium-High | Low |

## What We Gain by Simplifying

1. **Faster implementation**: From ~450 LOC to ~100 LOC means less code to write, review, and test
2. **Easier maintenance**: No new abstractions to understand - just small extensions to existing code
3. **Lower risk**: Modifying existing battle-tested code paths rather than adding new systems
4. **Clearer code**: The "track" concept maps directly to existing `SubtitleDisplayMode` - no translation layer needed

## What We Sacrifice (and Why It's OK)

1. **Track Registry Abstraction**
   - Impact: None for current use case
   - Justification: We only have two tracks (source/target), not arbitrary named tracks
   - Recovery plan: If we ever support multiple subtitle files per language, add abstraction then

2. **Backend Track Metadata API**
   - Impact: None - frontend already knows track availability
   - Justification: Content status fields already indicate which tracks exist
   - Recovery plan: Add API endpoint if we need server-side track enumeration

3. **Rich Track Metadata (labels, ordering)**
   - Impact: Minimal - users don't need to name tracks, just switch them
   - Justification: YAGNI - no user request for custom track names
   - Recovery plan: Extend types if/when needed

## Implementation Estimate

**Total LOC**: ~100 (Low complexity)

**Breakdown**:
- Types extension (`types.ts`): ~8 LOC
- Settings store (`useGlobalSettingsStore.ts`): ~12 LOC
- FocusModeHandler auto-switch: ~35 LOC
- VideoPlayer toggle button + shortcut: ~30 LOC
- Settings UI (`PlayerTab.tsx`): ~15 LOC

## Red Flags Eliminated

These over-engineering patterns were removed:

1. **Premature Abstraction (SubtitleTrack type)**: The existing `SubtitleDisplayMode` enum already serves as the track identifier. Creating `SubtitleTrack` with `id`, `isOriginal`, `isTranslated` flags adds a layer that maps 1:1 to existing values.

2. **Unnecessary Indirection (useSubtitleTrackManagement hook)**: Would wrap `useSubtitleManagement` and `useVideoStateStore` without adding new functionality. The proposed "track registry" logic is just `mode === "source" ? "target" : "source"`.

3. **Speculative API (GET /<content_id>/tracks)**: Frontend already determines track availability from `content.subtitleStatus` and `content.translationStatus`. No server round-trip needed to discover that source and target tracks exist.

4. **Duplicate Store Actions**: Proposed `setActiveSubtitleTrack`, `setOriginalTrack`, `setTranslatedTrack` would just call existing `setSubtitleModePlayer` with different arguments.

---

## Next Steps

This combined report will be reviewed by an external consensus agent (Codex or Claude Opus) to synthesize a final, balanced implementation plan.

---

## Output Requirements

Generate a final implementation plan that follows the plan-guideline structure and rules:
- **Design-first TDD ordering**: Documentation → Tests → Implementation (never invert).
- **Use LOC estimates only** (no time-based estimates).
- **Be concrete**: cite exact repo-relative files/sections; avoid vague audit steps.
- **Include dependencies** for each step so ordering is enforced.
- **For every step, list correspondence** to documentation and test cases (what it updates, depends on, or satisfies).
- **If this is a bug fix**, include Bug Reproduction (or explicit skip reason).

```markdown
# Implementation Plan: Unknown Feature

## Consensus Summary

[2-3 sentences explaining the balanced approach chosen]

## Goal
[1-2 sentence problem statement]

**Success criteria:**
- [Criterion 1]
- [Criterion 2]

**Out of scope:**
- [What we're not doing]
- However, it it a good idea for future work?
  - If so, briefly describe it here. ✅ Good to have in the future: Briefly describe it in 1-2 sentences.
  - If not, explain why it's excluded. ❌ Not needed: Explain why it is a bad idea.

## Bug Reproduction
*(Optional - include only for bug fixes where reproduction was attempted)*

**Steps tried:**
- [Command or action performed]
- [Files examined]

**Observed symptoms:**
- [Error messages, test failures, unexpected behavior]

**Environment snapshot:**
- [Relevant file state, dependencies, configuration]

**Root cause hypothesis:**
- [Diagnosis based on observations]

**Skip reason** *(if reproduction not attempted)*:
- [Why reproduction was skipped]

**Unreproducible constraints** *(if reproduction failed)*:
- [What was tried and why it didn't reproduce]
- [Hypothesis for proceeding without reproduction]

## Codebase Analysis

**Files verified (docs/code checked by agents):**
- [File path 1]: [What was verified]
- [File path 2]: [What was verified]

**File changes:**

| File | Level | Purpose |
|------|-------|---------|
| `path/to/file1` | major | Significant changes description |
| `path/to/file2` | medium | Moderate changes description |
| `path/to/file3` | minor | Small changes description |
| `path/to/new/file` (new) | major | New file purpose (Est: X LOC) |
| `path/to/deprecated/file` | remove | Reason for removal |

**Modification level definitions:**
- **minor**: Cosmetic or trivial changes (comments, formatting, <10 LOC changed)
- **medium**: Moderate changes to existing logic (10-50 LOC, no interface changes)
- **major**: Significant structural changes (>50 LOC, interface changes, or new files)
- **remove**: File deletion

**Current architecture notes:**
[Key observations about existing code]

## Interface Design

**New interfaces:**
- Interface signatures and descriptions. Especially talk about:
  - Exposed functionalities to internal use or user usage
  - Internal implmentation based on the complexity
    - If it is less than 20 LoC, you can just talk about the semantics of the interface omit this
    - If it is with for loop and complicated conditional logics, put the steps here:
      - Step 1: Get ready for input
      - Step 2: Iterate over the input
        - Step 2.1: Check condition A
        - Step 2.2: Check condition B
        - Step 2.3: If condition A and B met, do X, if not go back to Step 2
        - Step 2.3: Return output based on conditionals
      - Step 3: Return final output
  - If any data structures or bookkeepings are needed, describe them here
    - What attributes are needed?
    - What are they recording?
    - Do they have any member methods associated?

**Modified interfaces:**
- [Before/after comparisons]
- It is preferred to have `diff` format if the change is less than 20 LoC:
```diff
- old line 1
- old line 2
+ new line 1
+ new line 2
```

**Documentation changes:**
- [Doc files to update with sections]

## Documentation Planning

**REQUIRED**: Explicitly identify all documentation impacts using these categories:

**High-level design docs (docs/):**
- `docs/workflows/*.md` — workflow and process documentation
- `docs/tutorial/*.md` — tutorial and getting-started guides
- `docs/architecture/*.md` — architectural design docs

**Folder READMEs:**
- `path/to/module/README.md` — module purpose and organization

**Interface docs:**
- Source file companion `.md` files documenting interfaces

Each document modifications should be as details as using `diff` format:
```diff
- Old document on interface(a, b, c)
+ New document on new_interface(a, b, c, d)
+ d handles the new feature by...
```

**Format:**
```markdown
## Documentation Planning

### High-level design docs (docs/)
- `docs/path/to/doc.md` — create/update [brief rationale]

### Folder READMEs
- `path/to/README.md` — update [what aspect]

### Interface docs
- `src/module/component.md` — update [which interfaces]
```

**Citation requirement:** When referencing existing command interfaces (e.g., `/ultra-planner`, `/issue-to-impl`), cite the actual `docs/` files (e.g., `docs/workflows/ultra-planner.md`, `docs/tutorial/02-issue-to-impl.md`) to ensure accuracy.

## Test Strategy

**Test modifications:**
- `test/file1` - What to test
  - Test case: Description
  - Test case: Description

**New test files:**
- `test/new_file` - Purpose (Estimated: X LOC)
  - Test case: Description
  - Test case: Description

**Test data required:**
- [Fixtures, sample data, etc.]

## Implementation Steps

**Step 1: [Documentation change]** (Estimated: X LOC)
- File changes
Dependencies: None
Correspondence:
- Docs: [What this step adds/updates]
- Tests: [N/A or what this enables]

**Step 2: [Test case changes]** (Estimated: X LOC)
- File changes
Dependencies: Step 1
Correspondence:
- Docs: [Which doc changes define these tests]
- Tests: [New/updated cases introduced here]

**Step 3: [Implementation change]** (Estimated: X LOC)
- File changes
Dependencies: Step 2
Correspondence:
- Docs: [Which doc behaviors are implemented here]
- Tests: [Which test cases this step satisfies]

If is preffered to put some implementation snippets here, if it is less than 20 LoC, use this format:
\`\`\`diff
- the code to be modified
+ the modified code
\`\`\`
where gives plan reviewer a quick idea of the implementation.

...

**Total estimated complexity:** X LOC ([Complexity level])
**Recommended approach:** [Single session / Milestone commits]
**Milestone strategy** *(only if large)*:
- **M1**: [What to complete in milestone 1]
- **M2**: [What to complete in milestone 2]
- **Delivery**: [Final deliverable]

## Success Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk 1] | [H/M/L] | [H/M/L] | [How to mitigate] |
| [Risk 2] | [H/M/L] | [H/M/L] | [How to mitigate] |

## Dependencies

[Any external dependencies or requirements]
```

## Evaluation Criteria

Your consensus plan should:

✅ **Be balanced**: Not too bold, not too conservative
✅ **Be practical**: Implementable with available tools/time
✅ **Be complete**: Include all essential components
✅ **Be clear**: Unambiguous implementation steps
✅ **Address risks**: Mitigate critical concerns from critique
✅ **Stay simple**: Remove unnecessary complexity per reducer
✅ **Correct measurement**: Use LOC estimates only; no time-based estimates
✅ **Accurate modification levels**: Every file must have correct level (minor/medium/major/remove)

❌ **Avoid**: Over-engineering, ignoring risks, excessive scope creep, vague specifications, or "audit the codebase" steps

## Final Privacy Note

As this plan will be published in a Github Issue, ensure no sensitive or proprietary information is included.

- No absolute paths from `/` or `~` or some other user-specific directories included
  - Use relative path from the root of the repo instead
- No API keys, tokens, or credentials
- No internal project names or codenames
- No personal data of any kind of users or developers
- No confidential business information
