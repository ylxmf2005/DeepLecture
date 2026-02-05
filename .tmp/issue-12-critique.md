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
