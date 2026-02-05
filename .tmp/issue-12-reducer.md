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
