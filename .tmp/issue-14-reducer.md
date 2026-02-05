# Simplified Proposal: Hover-to-Lookup Dictionary for Language Learning

## Simplification Summary

This simplified proposal eliminates the complex three-tier caching architecture, removes the 2MB bundled dictionary, defers spaced repetition entirely, and replaces Dexie.js/IndexedDB with simple localStorage. The core feature - word lookup on hover - can be achieved with a single API call per lookup (debounced), existing Zustand patterns for vocabulary storage, and native CSS positioning instead of Floating UI.

## Files Checked

**Documentation and codebase verification:**
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/demo/dual-subtitle.md`: Verified subtitle display modes (source/target/dual) - only source language should be hoverable
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/content/SubtitleList.tsx`: Current sidebar subtitle rendering - plain text display with click-to-seek
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`: Video overlay subtitle rendering - simple `<div>` with text
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useGlobalSettingsStore.ts`: Zustand + localStorage persistence pattern already established
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/package.json`: No tooltip library currently installed; framer-motion available for animations
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/srt.ts`: Subtitle data structure - `{ id, startTime, endTime, text }`

## Core Problem Restatement

**What we're actually solving:**
Enable language learners to quickly look up unknown words in source-language subtitles by hovering, and optionally save words for later review.

**What we're NOT solving:**
- Spaced repetition review system (SM-2 algorithm, review scheduling)
- Offline dictionary capability (2MB pre-bundled data)
- Multi-tier caching architecture (LRU + IndexedDB + API fallback)
- Flashcard UI and review workflow
- Complex lemmatization/stemming for word variants
- Cross-browser `Intl.Segmenter` polyfills

## Complexity Analysis

### Removed from Original

1. **Three-Tier Dictionary Cache (LRU + IndexedDB + API)**
   - Why it's unnecessary: For language learning, users typically look up 10-50 words per session. A simple in-memory cache of recent lookups plus a single API call is sufficient. Free Dictionary API response time of 100-300ms is acceptable.
   - Impact of removal: Slightly slower repeated lookups (only within same session; no persistence)
   - Can add later if needed: Yes, IndexedDB tier can be added if users complain about latency

2. **Dexie.js IndexedDB Wrapper (~22kB gzipped)**
   - Why it's unnecessary: Vocabulary collection can use existing Zustand + localStorage pattern (already in codebase). No need for a database library to store a list of saved words.
   - Impact of removal: Saves 22kB bundle size; simplifies dependencies
   - Can add later if needed: Yes, if vocabulary exceeds localStorage limits (~5MB)

3. **Pre-bundled 10k Common Words (~2MB gzipped)**
   - Why it's unnecessary: This is premature optimization. Most users will look up words on-demand. Shipping 2MB of dictionary data for a feature that may be used sparingly is wasteful.
   - Impact of removal: Major bundle size savings; no offline dictionary
   - Can add later if needed: Yes, as opt-in download or service worker cache

4. **Floating UI Library (~3kB gzipped)**
   - Why it's unnecessary: Simple CSS absolute positioning with a few lines of JavaScript to handle edge cases (near viewport edges) is sufficient. The existing codebase uses no tooltip library.
   - Impact of removal: Saves dependency; simpler positioning code
   - Can add later if needed: Yes, if popup positioning becomes problematic

5. **SM-2 Spaced Repetition Algorithm (~180 LOC)**
   - Why it's unnecessary: The vocabulary "save" feature can work as a simple list first. Users can review manually. Spaced repetition is a separate feature that deserves its own implementation cycle.
   - Impact of removal: No automated review scheduling
   - Can add later if needed: Yes, as dedicated "Vocabulary Review" feature

6. **VocabularyReviewPanel + Card (~250 LOC)**
   - Why it's unnecessary: YAGNI - building a flashcard UI before users can even save words. Start with "Save to vocabulary" button that stores to a list; review UI comes later.
   - Impact of removal: No immediate review capability
   - Can add later if needed: Yes, as Phase 2

7. **DictionaryProvider Context (~80 LOC)**
   - Why it's unnecessary: A simple custom hook `useDictionaryLookup` can handle the API call and caching without React Context overhead.
   - Impact of removal: Simpler component tree
   - Can add later if needed: If state needs to be shared across distant components

8. **`Intl.Segmenter` Word Tokenizer (~80 LOC)**
   - Why it's unnecessary: For most Latin-script languages, splitting on whitespace and punctuation is sufficient. CJK languages (Chinese, Japanese) are more complex, but can be handled with regex fallback or server-side.
   - Impact of removal: May have edge cases with CJK languages
   - Can add later if needed: Yes, as language-specific enhancement

### Retained as Essential

1. **HoverableSubtitleText Component**
   - Why it's necessary: Core feature - wraps subtitle text with per-word hover detection
   - Simplified approach: Split text on whitespace/punctuation, wrap each word in `<span>` with `onMouseEnter`

2. **DictionaryPopup Component**
   - Why it's necessary: Displays word definition, pronunciation, examples
   - Simplified approach: CSS absolute positioning relative to hovered word; no external library

3. **useDictionaryLookup Hook**
   - Why it's necessary: Handles API call, debouncing, simple in-memory cache
   - Simplified approach: Single useState + useEffect; 300ms debounce; Map for session cache

4. **Vocabulary Storage (in existing store)**
   - Why it's necessary: Users need to save words for later
   - Simplified approach: Add `savedWords: string[]` to `useGlobalSettingsStore`; persists via existing localStorage

### Deferred for Future

1. **Spaced Repetition Review System**
   - Why we can wait: Core value is lookup, not review. Validate lookup usage before building review.
   - When to reconsider: When users have 50+ saved words and request review features

2. **Offline Dictionary**
   - Why we can wait: API latency is acceptable for low-volume lookups
   - When to reconsider: If users request offline mode or complain about latency

3. **CJK Word Segmentation**
   - Why we can wait: Most language learning videos are English-source; handle Latin scripts first
   - When to reconsider: When supporting Chinese/Japanese/Korean content

4. **Vocabulary Export/Import**
   - Why we can wait: Users can access localStorage data manually if desperate
   - When to reconsider: When users request Anki integration or backup

## Minimal Viable Solution

### Core Components

1. **HoverableSubtitleText Component**
   - Files: `frontend/components/content/HoverableSubtitleText.tsx` (new)
   - Responsibilities: Split subtitle text into hoverable word spans; emit word on hover
   - LOC estimate: ~60 LOC
   - Simplifications applied: Simple whitespace split; inline hover handlers; CSS-only hover state

2. **DictionaryPopup Component**
   - Files: `frontend/components/content/DictionaryPopup.tsx` (new)
   - Responsibilities: Display definition, pronunciation, examples; "Save" button; position near hovered word
   - LOC estimate: ~80 LOC
   - Simplifications applied: CSS absolute positioning; no Floating UI; simple viewport boundary check

3. **useDictionaryLookup Hook**
   - Files: `frontend/hooks/useDictionaryLookup.ts` (new)
   - Responsibilities: Debounced API call to Free Dictionary API; in-memory cache (Map)
   - LOC estimate: ~50 LOC
   - Simplifications applied: No IndexedDB; no LRU eviction; simple Map cache; single API tier

4. **Vocabulary Store Extension**
   - Files: `frontend/stores/useGlobalSettingsStore.ts` (modify existing)
   - Responsibilities: Store saved words; add/remove vocabulary
   - LOC estimate: ~25 LOC additions
   - Simplifications applied: Reuse existing Zustand store; simple string array; existing localStorage persistence

5. **Integration Updates**
   - Files: `frontend/components/content/SubtitleList.tsx`, `frontend/components/video/VideoPlayer.tsx`
   - Responsibilities: Use HoverableSubtitleText for source-language subtitles
   - LOC estimate: ~40 LOC changes
   - Simplifications applied: Only enable for "source" subtitle mode; prop-based toggle

### Implementation Strategy

**Approach**: Feature flag + incremental enhancement

**Key simplifications:**
- Single Free Dictionary API (no fallback chain)
- In-memory cache only (no persistence between sessions)
- CSS positioning (no Floating UI)
- Existing Zustand store (no new state management)
- No review UI (just save/view saved list)

### No External Dependencies

The simplified implementation requires no new npm dependencies:
- **Positioning**: Native CSS absolute/fixed positioning with simple JavaScript boundary checks
- **State**: Existing Zustand store
- **API**: Native fetch (already used throughout codebase)
- **Animations**: Optional framer-motion (already installed) or CSS transitions

## Comparison with Original

| Aspect | Original Proposal | Simplified Proposal |
|--------|------------------|---------------------|
| Total LOC | ~1,220 | ~255 (79% reduction) |
| Files | 9 new files | 3 new files + 2 modifications |
| New Dependencies | `@floating-ui/react`, `dexie` | None |
| Bundle Size Impact | ~27kB + 2MB dictionary | ~0 |
| Complexity | High (3-tier cache, IndexedDB, SM-2) | Low (single API, memory cache) |
| Review System | Full SM-2 spaced repetition | Deferred (just save list) |
| Offline Capability | Yes (10k pre-bundled words) | No (API-only) |

## What We Gain by Simplifying

1. **Faster implementation**: From ~1,220 LOC to ~255 LOC; can be built in a single focused session
2. **Easier maintenance**: No IndexedDB migrations, no cache invalidation logic, no spaced repetition scheduling
3. **Lower risk**: Fewer moving parts; easier to debug; no external library updates to track
4. **Clearer code**: Feature is understandable without understanding caching strategies or SM-2 algorithm
5. **Zero bundle impact**: No new dependencies; no 2MB dictionary download

## What We Sacrifice (and Why It's OK)

1. **Instant lookups for common words**
   - Impact: 100-300ms API latency instead of 0-20ms cache hit
   - Justification: Users look up words infrequently; sub-second latency is acceptable for learning context
   - Recovery plan: Add IndexedDB cache if latency complaints arise

2. **Offline dictionary**
   - Impact: Feature requires internet connection
   - Justification: Video playback already requires server; this is a web app, not offline-first
   - Recovery plan: Service worker caching or optional dictionary download

3. **Spaced repetition review**
   - Impact: Users must self-manage review; no automated scheduling
   - Justification: This is a separate product feature; validate vocabulary saving usage first
   - Recovery plan: Build dedicated "Vocabulary Review" tab if users accumulate words and request it

4. **CJK word segmentation**
   - Impact: Chinese/Japanese/Korean word boundaries may be incorrect
   - Justification: Primary use case is English-source videos; handle Latin scripts first
   - Recovery plan: Add `Intl.Segmenter` or server-side segmentation for CJK languages

## Implementation Estimate

**Total LOC**: ~255 (Low complexity)

**Breakdown**:
- HoverableSubtitleText.tsx: ~60 LOC
- DictionaryPopup.tsx: ~80 LOC
- useDictionaryLookup.ts: ~50 LOC
- Store additions: ~25 LOC
- Integration changes: ~40 LOC

**Files to Create**:
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/content/HoverableSubtitleText.tsx`
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/content/DictionaryPopup.tsx`
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useDictionaryLookup.ts`

**Files to Modify**:
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useGlobalSettingsStore.ts`
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/content/SubtitleList.tsx`
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`

## Red Flags Eliminated

These over-engineering patterns were removed:

1. **Premature optimization (Three-tier cache)**
   - Why it was unnecessary: Building complex caching for 10-50 lookups per session is solving a problem that does not exist yet

2. **Speculative feature (Spaced repetition + flashcard UI)**
   - Why it was unnecessary: Users have not even used vocabulary saving; building review system is premature

3. **Unnecessary dependency (Dexie.js for IndexedDB)**
   - Why it was unnecessary: localStorage with existing Zustand persist middleware handles the use case

4. **Unnecessary dependency (Floating UI)**
   - Why it was unnecessary: A few lines of CSS positioning handles 90% of cases; complex edge cases can be handled with simple JavaScript

5. **Bundled assets (2MB dictionary)**
   - Why it was unnecessary: Shipping megabytes of data for an optional feature violates progressive enhancement principles

6. **Over-abstraction (DictionaryProvider context)**
   - Why it was unnecessary: A simple hook suffices; no need for context when state is component-local
