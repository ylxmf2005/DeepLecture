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
