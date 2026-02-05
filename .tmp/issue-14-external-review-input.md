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

**Generated**: 2026-02-04 11:08

This document combines three perspectives from our multi-agent debate-based planning system:
1. **Report 1**: issue-14-bold-proposal.md
2. **Report 2**: issue-14-critique.md
3. **Report 3**: issue-14-reducer.md

---

## Part 1: issue-14-bold-proposal.md

# Bold Proposal: Hover-to-Lookup Dictionary for Language Learning in Video Subtitles

## Innovation Summary

A **hybrid offline-first dictionary system** with intelligent word tokenization using `Intl.Segmenter`, pre-loaded IndexedDB dictionary cache from open-source WordNet/Wiktionary data, Floating UI-powered smart popups, and a Zustand-persisted vocabulary collection with spaced repetition review capabilities.

## Original User Request

> Add a hover-to-lookup dictionary feature for video subtitles (both on the video player overlay and right sidebar). When users hover over words in the **original language** subtitle only, a popup dictionary appears with:
> 1. Word definition/meaning
> 2. Pronunciation (phonetic transcription)
> 3. Example sentences
> 4. "Save to vocabulary" button for word collection
>
> Key requirements:
> - Only applies to **original language text**, NOT translations
> - For bilingual subtitles, hovering on translation text does nothing
> - Works both on video player subtitle overlay AND right sidebar subtitle panel
> - Low latency (prefer offline dictionary over API calls)
> - Vocabulary collection system (save words, review later like flashcards)
> - Similar to Youdao Dictionary's word-picking (取词) feature

This section preserves the user's exact requirements so that critique and reducer agents can verify alignment with the original intent.

## Research Findings

**Key insights from SOTA research:**

1. **Youdao Dictionary's 取词功能** uses mouse position monitoring and DOM text inspection in browsers, with API calls for definitions. The Chrome extension displays word meaning, phonetic transcription, and pronunciation audio on hover. Source: [Youdao Dict Chrome Extension](https://chromewebstore.google.com/detail/youdao-dict/llopmojlajjdmeilflefogagfolbndme)

2. **Language Reactor** provides dual subtitles with hover-to-translate popups, recognizes word conjugations/plurals, and allows saving words for later review. It integrates seamlessly with Netflix video playback. Source: [Language Reactor](https://www.languagereactor.com/)

3. **Intl.Segmenter API** (Baseline April 2024) enables locale-sensitive word tokenization that works for CJK languages without spaces. It uses Unicode standards for accurate segmentation across all languages. Source: [MDN Intl.Segmenter](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter)

4. **Floating UI** (~3kB gzipped) provides automatic collision detection, responsive positioning, and accessibility support for tooltips/popovers. Source: [Floating UI](https://floating-ui.com/)

5. **IndexedDB** is suitable for dictionary data with fast read latency using proper indexing. Source: [Speeding up IndexedDB](https://nolanlawson.com/2021/08/22/speeding-up-indexeddb-reads-and-writes/)

6. **Offline Dictionary Data** available from:
   - [Free Dictionary API](https://dictionaryapi.dev/) - Free API with phonetics and audio
   - [ipa-dict](https://github.com/open-dict-data/ipa-dict) - IPA pronunciation data in JSON format
   - [WordNet npm package](https://www.npmjs.com/package/wordnet) - 28.1 MB comprehensive dictionary
   - [Webster's JSON Dictionary](https://github.com/adambom/dictionary) - Public domain dictionary data

7. **Anki-style spaced repetition** uses SM-2/FSRS algorithms for optimal review scheduling. Card review flow: front-reveal-grade cycle. Source: [Anki Algorithm Explained](https://www.growexx.com/blog/anki-algorithm-explained-how-spaced-repetition-works/)

**Files checked for current implementation:**

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/content/SubtitleList.tsx`: Sidebar subtitle panel using Virtuoso, renders `subtitle.text` as plain string (line 161), has hover pattern with `group-hover:opacity-100` for action buttons
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`: Video player with subtitle overlay (lines 442-466), renders `sub.text` directly in a div, no word-level interaction
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useSubtitleManagement.ts`: Manages subtitle modes (source/target/dual/dual_reversed), provides `subtitlesSource`, `subtitlesTarget`, `currentSubtitles`
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`: Defines `SubtitleDisplayMode`, Zustand persist patterns, storage versioning
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useGlobalSettingsStore.ts`: Zustand store with persist middleware pattern, migration support
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/srt.ts`: Subtitle type: `{ id, startTime, endTime, text }` - text is a plain string

## Proposed Solution

### Core Architecture

The solution uses a **three-tier dictionary lookup architecture**:

1. **Tier 1 (Instant - 0ms)**: In-memory LRU cache of recently looked-up words
2. **Tier 2 (Fast - 5-20ms)**: IndexedDB with pre-loaded common vocabulary (10k most frequent words with definitions, IPA, examples)
3. **Tier 3 (Fallback - 100-300ms)**: Free Dictionary API call for rare words, cached back to IndexedDB

Word tokenization uses the native `Intl.Segmenter` API with language-aware segmentation, making it work seamlessly for both space-delimited languages (English) and non-space languages (Chinese, Japanese).

The popup is powered by **Floating UI** for smart positioning that handles video player boundaries, fullscreen mode, and sidebar constraints.

### Key Components

#### 1. **Word Tokenizer Service** (`frontend/lib/dictionary/tokenizer.ts`)
   - Files: `frontend/lib/dictionary/tokenizer.ts`
   - Responsibilities:
     - Use `Intl.Segmenter` for locale-aware word boundary detection
     - Handle CJK languages (Chinese, Japanese, Korean) without space delimiters
     - Provide word span positions for hover detection
     - Filter out punctuation and whitespace segments
   - LOC estimate: ~80

```typescript
// Example interface
interface WordSegment {
  word: string;
  index: number;
  isWord: boolean; // true if Intl.Segmenter identifies as "word" type
}

function tokenizeText(text: string, locale: string): WordSegment[];
```

#### 2. **Dictionary Data Store** (`frontend/lib/dictionary/store.ts`)
   - Files: `frontend/lib/dictionary/store.ts`, `frontend/lib/dictionary/types.ts`
   - Responsibilities:
     - IndexedDB wrapper using Dexie.js for type-safe access
     - Pre-load common vocabulary JSON bundle (~2MB gzipped for 10k words)
     - Store user-saved vocabulary separately
     - Provide fast indexed lookup by word/lemma
   - LOC estimate: ~150

```typescript
interface DictionaryEntry {
  word: string;
  lemma: string; // base form (e.g., "run" for "running")
  phonetic: string; // IPA transcription
  audioUrl?: string;
  definitions: { partOfSpeech: string; meaning: string; example?: string }[];
  cached?: boolean; // true if from API fallback
}
```

#### 3. **Dictionary Lookup Hook** (`frontend/hooks/useDictionaryLookup.ts`)
   - Files: `frontend/hooks/useDictionaryLookup.ts`
   - Responsibilities:
     - Three-tier lookup with LRU cache, IndexedDB, API fallback
     - Debounced lookup (150ms) to avoid excessive queries on fast hovering
     - Handle loading/error states
     - Lemmatization for inflected forms (simple heuristics + dictionary fallback)
   - LOC estimate: ~120

#### 4. **Vocabulary Store** (`frontend/stores/useVocabularyStore.ts`)
   - Files: `frontend/stores/useVocabularyStore.ts`, `frontend/stores/types.ts` (updates)
   - Responsibilities:
     - Zustand store with IndexedDB persistence for vocabulary collection
     - Store words with context (video ID, timestamp, subtitle text)
     - Track review statistics (times reviewed, last review date, difficulty)
     - Simple SM-2 scheduling for spaced repetition
   - LOC estimate: ~180

```typescript
interface VocabularyWord {
  id: string;
  word: string;
  definition: string;
  phonetic: string;
  context: { videoId: string; timestamp: number; sentence: string };
  addedAt: string;
  // SM-2 fields
  easeFactor: number;
  interval: number;
  repetitions: number;
  nextReviewDate: string;
}
```

#### 5. **Hoverable Subtitle Text Component** (`frontend/components/content/HoverableSubtitleText.tsx`)
   - Files: `frontend/components/content/HoverableSubtitleText.tsx`
   - Responsibilities:
     - Render tokenized words as individual `<span>` elements
     - Track hover state with mouse enter/leave
     - Distinguish between original and translation text (only original is interactive)
     - Handle dual subtitle mode (first line = original, second = translation or vice versa)
   - LOC estimate: ~100

#### 6. **Dictionary Popup Component** (`frontend/components/dictionary/DictionaryPopup.tsx`)
   - Files: `frontend/components/dictionary/DictionaryPopup.tsx`, `frontend/components/dictionary/index.ts`
   - Responsibilities:
     - Floating UI-powered popup with smart positioning
     - Display definition, pronunciation (with audio playback), examples
     - "Save to Vocabulary" button with success feedback
     - Keyboard accessibility (Escape to close, focus trap)
     - Responsive sizing for video player vs sidebar
   - LOC estimate: ~200

#### 7. **Dictionary Context Provider** (`frontend/components/dictionary/DictionaryProvider.tsx`)
   - Files: `frontend/components/dictionary/DictionaryProvider.tsx`
   - Responsibilities:
     - React Context for dictionary state management
     - Coordinate popup visibility and position
     - Provide lookup and save functions to children
     - Handle click-outside dismissal
   - LOC estimate: ~80

#### 8. **Vocabulary Review Panel** (`frontend/components/vocabulary/VocabularyReviewPanel.tsx`)
   - Files: `frontend/components/vocabulary/VocabularyReviewPanel.tsx`, `frontend/components/vocabulary/VocabularyCard.tsx`, `frontend/components/vocabulary/index.ts`
   - Responsibilities:
     - Flashcard-style review interface
     - Show word, reveal definition on click
     - Grade buttons (Again, Hard, Good, Easy) update SM-2 scheduling
     - Progress indicator (X cards remaining today)
     - Link back to video timestamp for context
   - LOC estimate: ~250

#### 9. **Integration Updates**
   - Files: `frontend/components/content/SubtitleList.tsx` (modify), `frontend/components/video/VideoPlayer.tsx` (modify)
   - Responsibilities:
     - Replace plain text rendering with `HoverableSubtitleText`
     - Pass language context to determine which text is original
     - Wrap with `DictionaryProvider`
   - LOC estimate: ~60

### External Dependencies

| Package | Purpose | Size |
|---------|---------|------|
| `@floating-ui/react` | Popup positioning | ~3kB gzipped |
| `dexie` | IndexedDB wrapper | ~22kB gzipped |
| (Bundled JSON) | Common vocabulary data | ~2MB gzipped |

**No new backend dependencies required** - dictionary data is frontend-only with API fallback to free public services.

## Benefits

1. **Ultra-Low Latency**: Three-tier caching ensures sub-20ms lookups for common words. LRU cache handles repeated hovers instantly (0ms), IndexedDB serves the 10k most common words in <20ms, and API fallback is only triggered for rare words.

2. **Works Offline**: Once the initial vocabulary bundle is loaded and API responses are cached, the dictionary functions completely offline - perfect for studying on flights or poor network conditions.

3. **Language-Agnostic Tokenization**: Using `Intl.Segmenter` means the same code works for English (space-delimited), Chinese (no spaces), Japanese (mixed), German (compound words), etc. No per-language tokenization code needed.

4. **Spaced Repetition Learning**: The SM-2 algorithm ensures efficient vocabulary retention. Users see difficult words more often and easy words less frequently, optimizing study time.

5. **Contextual Vocabulary**: Saved words include video timestamp and surrounding subtitle, allowing users to jump back to the exact moment they encountered a word for better comprehension.

6. **Non-Intrusive UX**: Dictionary only activates on original language text (not translations), preventing confusion in bilingual subtitle mode. Hover delay prevents accidental popups.

## Trade-offs

1. **Complexity**: Adds ~1,200 LOC of new frontend code and 2MB of bundled dictionary data. The three-tier lookup system has more moving parts than a simple API call.
   - Mitigation: Clear separation of concerns makes each component testable in isolation.

2. **Learning curve**: Developers need to understand `Intl.Segmenter` behavior, Floating UI positioning, and Dexie.js IndexedDB patterns.
   - Mitigation: Well-documented code with JSDoc comments and usage examples.

3. **Failure modes**:
   - `Intl.Segmenter` not supported in older browsers (pre-April 2024): Fallback to simple space-split for Latin scripts, show warning for CJK.
   - IndexedDB blocked (private browsing): Fall back to API-only mode with memory cache.
   - API rate limits: Free Dictionary API has no published rate limits but may throttle; cached responses mitigate this.
   - Large vocabulary data load: Lazy-load dictionary bundle after initial page render; show "Loading dictionary..." state.

4. **Initial Load Impact**: 2MB dictionary bundle needs to be downloaded once. Using dynamic import and service worker caching minimizes repeat impact.

## Implementation Estimate

**Total LOC**: ~1,220 (Medium-Large feature)

**Breakdown**:
| Component | LOC |
|-----------|-----|
| Word Tokenizer | ~80 |
| Dictionary Data Store | ~150 |
| Dictionary Lookup Hook | ~120 |
| Vocabulary Store | ~180 |
| HoverableSubtitleText | ~100 |
| DictionaryPopup | ~200 |
| DictionaryProvider | ~80 |
| VocabularyReviewPanel + Card | ~250 |
| Integration Updates | ~60 |
| **Total Implementation** | **~1,220** |
| Documentation | ~150 |
| Tests | ~300 |
| **Grand Total** | **~1,670** |

**Recommended approach**: Milestone commits over 3-4 development sessions

**Milestone strategy**:
- Milestone 1: Tokenizer + Dictionary Store + IndexedDB setup
- Milestone 2: Lookup hook + HoverableSubtitleText component
- Milestone 3: DictionaryPopup + Provider integration
- Milestone 4: Vocabulary store + Review panel

---

Sources:
- [MDN Intl.Segmenter](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/Segmenter)
- [MDN Blog: Locale-sensitive text segmentation](https://developer.mozilla.org/en-US/blog/javascript-intl-segmenter-i18n/)
- [Floating UI](https://floating-ui.com/)
- [Floating UI React](https://floating-ui.com/docs/react)
- [Dexie.js](https://dexie.org/)
- [Free Dictionary API](https://dictionaryapi.dev/)
- [IPA Dict](https://github.com/open-dict-data/ipa-dict)
- [WordNet npm](https://www.npmjs.com/package/wordnet)
- [Webster's JSON Dictionary](https://github.com/adambom/dictionary)
- [Language Reactor](https://www.languagereactor.com/)
- [Youdao Dict Chrome Extension](https://chromewebstore.google.com/detail/youdao-dict/llopmojlajjdmeilflefogagfolbndme)
- [Anki Algorithm Explained](https://www.growexx.com/blog/anki-algorithm-explained-how-spaced-repetition-works/)
- [RxDB: Solving IndexedDB Slowness](https://rxdb.info/slow-indexeddb.html)
- [Speeding up IndexedDB reads and writes](https://nolanlawson.com/2021/08/22/speeding-up-indexeddb-reads-and-writes/)

---

## Part 2: issue-14-critique.md

# Proposal Critique: Hover-to-Lookup Dictionary for Language Learning

## Executive Summary

The proposal presents a technically sophisticated solution with a sensible three-tier caching architecture. However, it makes several risky assumptions about browser compatibility, dictionary data availability, and integration complexity. The 1,220 LOC estimate appears optimistic given the scope, and key edge cases around multi-language support and word tokenization for non-English languages are inadequately addressed.

## Files Checked

**Documentation and codebase verification:**
- `/Users/EthanLee/Desktop/CourseSubtitle/CLAUDE.md`: Verified project architecture (Clean Architecture with frontend/backend split)
- `/Users/EthanLee/Desktop/CourseSubtitle/README.md`: Confirmed Flashcard is on roadmap (line 105), no existing dictionary feature
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/package.json`: Confirmed zustand v5.0.9 present, no Dexie or floating-ui/react
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/package-lock.json`: floating-ui/dom exists as transitive dependency via @milkdown
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/content/SubtitleList.tsx`: Verified current subtitle rendering (lines 155-163) - plain text, no word-level interactivity
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx`: Verified subtitle overlay (lines 481-496) - same simple rendering
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts`: Confirmed store patterns and SubtitleDisplayMode (source/target/dual/dual_reversed)
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/srt.ts`: Verified Subtitle interface (id, startTime, endTime, text as plain string)
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/tsconfig.json`: Target ES2017, lib includes esnext
- `/Users/EthanLee/Desktop/CourseSubtitle/docs/demo/dual-subtitle.md`: No mention of dictionary/lookup features

## Assumption Validation

### Assumption 1: Intl.Segmenter provides "language-agnostic tokenization"
- **Claim**: `Intl.Segmenter` handles all languages uniformly for word tokenization
- **Reality check**: Intl.Segmenter requires explicit locale specification and behaves differently per language. CJK languages (Chinese, Japanese, Korean) require specific segmentation modes. The "word" granularity for Chinese returns each character as a separate segment unless configured correctly.
- **Status**: [WARNING] Questionable
- **Evidence**: MDN documentation and browser implementation details. Chinese word segmentation is notoriously difficult and requires dictionary-based approaches.

### Assumption 2: Baseline browser support (April 2024)
- **Claim**: Intl.Segmenter baseline is April 2024
- **Reality check**: Safari support for Intl.Segmenter was added in Safari 15.4 (March 2022). Firefox added support in version 125 (April 2024). Current tsconfig targets ES2017, and lib includes esnext which should include Intl.Segmenter types.
- **Status**: [VALID] Valid with caveats
- **Evidence**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/tsconfig.json` line 4

### Assumption 3: floating-ui/react is a new dependency (~3kB)
- **Claim**: Adding @floating-ui/react as new dependency
- **Reality check**: @floating-ui/dom already exists as transitive dependency via @milkdown (package-lock.json lines 1382-1401). However, @floating-ui/react is NOT currently installed and would be a new direct dependency.
- **Status**: [VALID] Valid
- **Evidence**: package-lock.json shows only @floating-ui/core, @floating-ui/dom, @floating-ui/utils

### Assumption 4: 2MB gzipped vocabulary JSON is acceptable
- **Claim**: Bundled 2MB dictionary is reasonable initial load
- **Reality check**: Current node_modules is 576MB, but the actual bundle size matters more. A 2MB gzipped download on first use is significant (8-10MB uncompressed). For users on slow connections or mobile, this could be problematic.
- **Status**: [WARNING] Questionable
- **Evidence**: `du -sh frontend/node_modules` shows 576M

### Assumption 5: WordNet/Wiktionary provides comprehensive definitions
- **Claim**: Open-source WordNet/Wiktionary data covers 10k common words
- **Reality check**: WordNet is English-only. For Chinese source content (the primary use case based on translated: "zh" default), there is no WordNet. Wiktionary data quality varies significantly by language.
- **Status**: [INVALID] Invalid for multi-language support
- **Evidence**: `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts` lines 92-95 show default languages are en/zh

### Assumption 6: IndexedDB is universally available
- **Claim**: IndexedDB with private browsing fallback is handled
- **Reality check**: Safari's IndexedDB in private mode has a 0-byte storage quota (effectively disabled). Firefox and Chrome have their own quirks. The proposal acknowledges this but doesn't provide a concrete fallback strategy.
- **Status**: [WARNING] Questionable
- **Evidence**: Stated trade-off but no mitigation plan

## Technical Feasibility Analysis

### Integration with Existing Code

**Compatibility**: Medium-High complexity

1. **SubtitleList.tsx (lines 155-163)**: Currently renders `{subtitle.text}` as plain text. Modification requires:
   - Wrapping text in a tokenizer component
   - Handling subtitle.text as multiline string (note: cleanSubtitleText in srt.ts strips HTML but preserves newlines)
   - Maintaining existing click-to-seek behavior while adding word hover

2. **VideoPlayer.tsx (lines 481-496)**: Subtitle overlay uses the same simple rendering:
   - Same modifications needed
   - Additional complexity: overlay is inside a `pointer-events-none` container (line 476)
   - Must selectively enable pointer events for hoverable words while keeping overlay non-blocking

3. **Subtitle data structure**: Current `Subtitle` interface in `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/srt.ts` has `text: string`. No modification needed, but tokenization happens at render time.

4. **Dual subtitle mode**: The proposal only addresses "original language" but the codebase has `dual` and `dual_reversed` modes where both languages display. Logic for distinguishing which line is hoverable in dual mode is not addressed.

**Conflicts**: None identified for new files

### Complexity Analysis

**Is this complexity justified?**

The three-tier caching is well-designed for latency. However:

1. **Over-engineered for MVP**: Spaced repetition (SM-2 algorithm) adds ~180 LOC for a feature that could be added later. A simple list of saved words would suffice initially.

2. **LOC estimate concerns**: 1,220 LOC seems low for:
   - Word tokenizer with multi-language support (80 LOC claimed)
   - Full SM-2 spaced repetition with review scheduling (180 LOC claimed)
   - Popup with definition, pronunciation, examples, save button (200 LOC claimed)

   Similar features in production apps typically require 2-3x these estimates.

3. **Missing from estimate**:
   - Dictionary data preprocessing/bundling scripts
   - Tests (vitest config exists but no component tests yet)
   - Migration for existing users
   - Settings UI for enabling/disabling feature

**Simpler alternatives overlooked:**

1. **Phase 1**: Start with API-only dictionary (Free Dictionary API) without IndexedDB caching. Add offline support in Phase 2.

2. **Existing Flashcard roadmap**: README.md line 105 mentions "Flashcard" as a planned feature. Vocabulary collection should integrate with this rather than building a parallel system.

## Risk Assessment

### HIGH Priority Risks

1. **Chinese word segmentation accuracy**
   - Impact: Core feature unusable for Chinese content, which appears to be a primary use case
   - Likelihood: High
   - Mitigation: Implement jieba-style dictionary-based segmentation for Chinese, or use a WebAssembly port of an existing Chinese tokenizer

2. **Dictionary data licensing and availability**
   - Impact: Legal issues or unavailable data for non-English languages
   - Likelihood: Medium-High
   - Mitigation: Document exact data sources with licenses. For Chinese, consider CC-CEDICT. Verify all licenses are compatible with project's MIT license.

3. **Performance impact on subtitle rendering**
   - Impact: Janky scrolling in SubtitleList with virtualized rendering (react-virtuoso)
   - Likelihood: Medium
   - Mitigation: Memoize tokenization results per subtitle. Profile with 1000+ subtitle entries.

### MEDIUM Priority Risks

1. **pointer-events conflict in video overlay**
   - Impact: Either hover doesn't work or video controls become inaccessible
   - Likelihood: Medium
   - Mitigation: Use CSS `pointer-events: auto` only on word spans, not the container

2. **Initial load time with 2MB dictionary**
   - Impact: Poor first-load experience, especially on mobile
   - Likelihood: Medium
   - Mitigation: Lazy-load dictionary on first hover, not on page load. Show loading indicator.

3. **Dexie.js bundle size (22kB gzipped)**
   - Impact: Adds to JS bundle, affecting all users even if they don't use dictionary
   - Likelihood: Low (22kB is acceptable)
   - Mitigation: Dynamic import/code-split the dictionary module

### LOW Priority Risks

1. **Free Dictionary API rate limiting**
   - Impact: Fallback fails for rare words under heavy use
   - Likelihood: Low
   - Mitigation: Cache all API responses. Consider self-hosting dictionary API.

2. **Browser extension conflicts**
   - Impact: Users with Youdao/other dictionary extensions may have double popups
   - Likelihood: Low
   - Mitigation: Document known conflicts

## Critical Questions

These must be answered before implementation:

1. **Which source languages must be supported at launch?** English only, or also Chinese/Japanese/Korean? This fundamentally changes tokenization approach.

2. **What is the relationship to the planned Flashcard feature in README.md?** Should vocabulary collection share storage/UI with flashcards?

3. **How should dual-subtitle mode behave?** When both source and target are displayed, should the target (translation) line also be non-interactive, or completely hidden for hover purposes?

4. **Is 2MB initial download acceptable for the target user base?** What percentage of users are on slow connections?

5. **What happens when dictionary lookup fails?** Silent failure, error message, or graceful degradation to selection-based lookup?

## Recommendations

### Must Address Before Proceeding

1. **Define MVP scope**: Remove SM-2 spaced repetition from Phase 1. Implement simple "saved words" list that exports to existing/planned Flashcard feature.

2. **Resolve Chinese tokenization strategy**: Either:
   - Limit initial release to English-only source content
   - Budget additional 200-300 LOC for dictionary-based Chinese segmentation
   - Use existing npm package like `nodejieba-wasm` (adds ~500KB)

3. **Fix pointer-events architecture**: Design the overlay component to allow selective interactivity without breaking video controls.

4. **Clarify dictionary data pipeline**: Specify exact data sources, preprocessing steps, and output format. Estimate actual compressed size after processing.

### Should Consider

1. **Integrate with existing Flashcard roadmap item**: Coordinate with planned flashcard feature rather than building separate vocabulary storage.

2. **Lazy-load dictionary module**: Use Next.js dynamic imports to avoid bloating the main bundle.

3. **Add dictionary language configuration**: Allow users to select which language's dictionary to download (rather than bundling all).

4. **Consider hybrid approach**: Use browser's native spell-check dictionary for basic tokenization, supplement with custom data for definitions.

### Nice to Have

1. **Offline-first dictionary for top 1,000 words only**: Reduce initial bundle from 2MB to ~200KB for most common lookups.

2. **Right-click context menu alternative**: For users who prefer selection-based lookup over hover.

3. **Pronunciation audio playback**: Extend popup to include TTS pronunciation (could reuse existing TTS infrastructure).

## Overall Assessment

**Feasibility**: Medium - Achievable with significant scope adjustments
**Complexity**: Over-engineered for initial implementation
**Readiness**: Needs revision before proceeding

**Bottom line**: The core concept is sound and the three-tier caching architecture is well-designed. However, the proposal underestimates multi-language complexity (especially for Chinese source content) and front-loads nice-to-have features (SM-2 spaced repetition) that should be deferred. Recommend revising to:
1. Start with English-only source language support
2. Remove spaced repetition from Phase 1
3. Integrate vocabulary storage with planned Flashcard feature
4. Add concrete Chinese tokenization strategy for Phase 2

---

## Part 3: issue-14-reducer.md

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
