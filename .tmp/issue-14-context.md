# Context Summary: Hover-to-Lookup Dictionary for Language Learning in Video Subtitles

## Feature Understanding
**Intent**: Add an interactive hover dictionary feature for original language subtitles (both video player overlay and sidebar panel) that provides word definitions, pronunciation, examples, and vocabulary collection functionality. This enables language learning by allowing users to look up unfamiliar words without breaking their video-watching flow.

**Scope signals**: hover interaction, dictionary lookup, popup/tooltip UI, vocabulary storage, language learning, subtitle word-level interaction, frontend-heavy feature with potential backend API for vocabulary persistence

## Relevant Files

### Source Files - Frontend Components
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/content/SubtitleList.tsx` — Sidebar subtitle panel using Virtuoso for virtualized list rendering. Displays subtitles with click-to-seek, hover actions for "Ask AI" and "Add to notes". Each subtitle rendered with timestamp and text. Key insight: Already has hover interaction pattern with buttons appearing on `group-hover:opacity-100`.

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayer.tsx` — Video player component with subtitle overlay rendering (lines 442-466). Renders active subtitles at bottom of video with configurable fontSize and bottomOffset. Subtitles displayed as black semi-transparent boxes with white text. Currently no word-level interaction.

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/components/video/VideoPlayerSection.tsx` — Wrapper for VideoPlayer component, handles player state and slide tab switching. Passes subtitle data to VideoPlayer.

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/app/video/[id]/VideoPageClient.tsx` — Main video page orchestrator (750+ lines). Manages subtitle state via `useSubtitleManagement` hook, handles sidebar and player subtitle modes separately. Coordinates all video page features including notes, timeline, ask context.

### Source Files - Frontend Hooks & State Management
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/hooks/useSubtitleManagement.ts` — Manages subtitle loading and mode switching (source/target/dual/dual_reversed). Fetches subtitles via API, handles race conditions, merges bilingual subtitles. Returns `subtitlesSource`, `subtitlesTarget`, etc.

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/useGlobalSettingsStore.ts` — Zustand store for global settings using persist middleware. Manages language settings (original/translated), playback preferences, UI settings. Pattern to follow for vocabulary storage.

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/stores/types.ts` — Type definitions for stores. Defines `SubtitleDisplayMode` as "source" | "target" | "dual" | "dual_reversed". Good reference for extending with vocabulary-related types.

### Source Files - Data Types
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/srt.ts` — Subtitle type definition:
  ```typescript
  interface Subtitle {
    id: string;
    startTime: number;
    endTime: number;
    text: string; // Full text of subtitle, no word-level data
  }
  ```
  Also includes SRT/VTT parsing and formatting utilities.

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/api/types.ts` — API response types following camelCase convention (axios interceptors handle snake_case conversion). Includes `SubtitleSegment`, `SubtitleResponse`, etc.

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/api/subtitle.ts` — Subtitle API methods: `generateSubtitles`, `enhanceAndTranslate`, `getSubtitles`, `getSubtitlesVtt`. No word-level endpoints currently.

### Documentation
- `/Users/EthanLee/Desktop/CourseSubtitle/README.md` — Project overview. DeepLecture is an AI-native video learning platform. Features include dual subtitles, screenshot explanations, timeline nodes, smart skip, focus mode, AI Q&A, notes, AI voiceover, Live2D. Tech stack: Python backend (FastAPI), Next.js frontend, Zustand state management.

- `/Users/EthanLee/Desktop/CourseSubtitle/CLAUDE.md` — Project instructions. Clean Architecture with 4 layers (domain, use cases, infrastructure, presentation). Backend follows dependency injection pattern. No specific subtitle-related constraints.

- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/README.md` — Standard Next.js README, no additional constraints.

### Configuration
- `/Users/EthanLee/Desktop/CourseSubtitle/frontend/package.json` — Dependencies include: React 19, Next.js 16, Zustand 5.0.9, axios 1.13.2, lucide-react (icons), tailwind-merge, framer-motion (animations), react-virtuoso (virtual scrolling). No existing dictionary/i18n libraries.

### Tests
- No test files found for subtitle components yet.

## Architecture Context

### Existing Patterns

**Subtitle Data Flow**:
- Backend generates subtitles (Whisper) → stores as segments with timing
- Frontend fetches via `/api/subtitle/{contentId}?language={lang}`
- Returns `SubtitleResponse` with `SubtitleSegment[]` (start, end, text)
- Frontend parses into `Subtitle[]` interface
- Subtitle modes: source (original language only), target (translation only), dual (both, source on top), dual_reversed (both, target on top)
- Player and sidebar have independent subtitle mode settings

**State Management Pattern**:
- Global settings: Zustand store with persist middleware (`useGlobalSettingsStore`)
- Per-video state: Separate Zustand store with localStorage (`useVideoStateStore`)
- Custom hooks extract specific state slices to minimize re-renders
- Example: `usePlayerSubtitleMode(videoId)` → `SubtitleDisplayMode`

**Hover/Popup Patterns**:
- SubtitleList uses `group` + `group-hover:opacity-100` for hover buttons
- ConfirmDialog component shows modal overlay pattern (backdrop + centered dialog)
- Live2DCanvas has drag handles that appear on hover
- No existing word-level tooltip/popup implementation
- CSS: Uses Tailwind for styling, dark mode support via `dark:` variants

**Component Composition**:
- Virtuoso for long lists (SubtitleList handles 1000+ subtitles efficiently)
- Error boundaries wrap major components
- Dynamic imports for heavy components (SettingsDialog, ActionsDialog)
- Ref forwarding pattern (VideoPlayer exposes `VideoPlayerRef` for imperative controls)

### Integration Points

**Subtitle Text Rendering**:
- **VideoPlayer overlay** (lines 450-463): Maps `activeSubtitles` array, renders each subtitle's `text` field as single `<div>` with black/70 background. Need to parse text into words and wrap each in clickable/hoverable span.
- **SubtitleList sidebar** (lines 155-162): Renders `subtitle.text` in `<p>` tag with `whitespace-pre-wrap`. Same word-wrapping needed here.

**Vocabulary Storage**:
- Likely needs new Zustand store for vocabulary collection
- Pattern: `useVocabularyStore` with persist middleware like `useGlobalSettingsStore`
- Schema: `{ [videoId]: { [word]: { definition, timestamp, savedAt } } }` or global word list
- Backend API: May need POST `/api/vocabulary` endpoint if server-side storage desired

**Dictionary Data Source**:
- Frontend-only: Use offline dictionary library (e.g., wiktionary-data, dictionary-en, or CC-CEDICT for Chinese)
- Or API-based: Integrate with dictionary API (e.g., Free Dictionary API, Wiktionary API)
- Consider language detection: Original language can be any language (configured in settings)

**UI Popup Component**:
- Need new component: `<DictionaryPopup>` that appears on hover/click
- Position near hovered word using absolute positioning or Popper.js-like logic
- Should support dark mode like existing dialogs
- Include: word, definition, phonetics, examples, "Save to vocabulary" button

## Constraints Discovered

**Language Handling**:
- Original language (`language.original` in settings) is user-configurable, not hardcoded to English
- Feature must work for any language the user sets as original
- Translation language (`language.translated`) is separate—dictionary only applies to original language

**Subtitle Data Structure**:
- Current `Subtitle.text` is plain string, no word-level segmentation
- Need client-side word tokenization (language-specific rules: English spaces, Chinese characters, etc.)
- No existing backend support for word boundaries

**Performance**:
- SubtitleList uses Virtuoso for performance with large subtitle lists
- Dictionary lookup must be low-latency (prefer offline library over API calls)
- Popup rendering should not block video playback

**Out of Scope** (based on constraints):
- Translation text hovering does NOT trigger dictionary (only original language)
- Backend changes should be minimal (vocabulary storage API only, optional)
- No existing popup framework, need to build custom or add library

**UI/UX Requirements from Feature Request**:
- Works in both video player overlay AND sidebar subtitle panel
- Only applies to original language text, not translations
- Low latency (offline dictionary preferred)
- Includes "Save to vocabulary" button
- Should feel like Youdao Dictionary's word-picking feature

## Recommended Focus Areas for Bold-Proposer

**Area 1: Offline Dictionary Library Research**
**Why Bold should focus here for innovation**: Existing gap—no dictionary integration in codebase. Bold should research SOTA offline dictionary libraries (e.g., Wiktionary data dumps, CC-CEDICT for Chinese, multi-language dictionaries) and propose best-fit solution considering latency, bundle size, and language coverage. Consider hybrid approach: offline for common words, fallback to API for rare words.

**Area 2: Word Tokenization Strategy**
**Why Bold should focus here for innovation**: Current subtitle text is unsegmented strings. Need language-aware word splitting that works for English (spaces), Chinese (no spaces, character-based or jieba-like segmentation), and other languages. Bold should explore browser Intl.Segmenter API (modern, handles many languages) vs. language-specific libraries vs. regex-based splitting.

**Area 3: Popup Positioning & Interaction Pattern**
**Why Bold should focus here for innovation**: No existing tooltip/popup pattern in codebase. Bold should design interaction: hover-only, click-to-pin, or hybrid? How to handle popup near video edges (especially in fullscreen)? Consider accessibility (keyboard navigation, screen readers). Explore headless UI libraries (Radix Popover, Floating UI) vs. custom implementation.

**Area 4: Vocabulary Collection & Review UX**
**Why Bold should focus here for innovation**: Existing gap—project has no flashcard/vocabulary review feature (see Roadmap: Flashcard feature is planned but not implemented). Bold should design vocabulary collection flow: where to show saved words, how to review them (separate page? sidebar tab?), export options (Anki format?), spaced repetition integration possibilities.

## Complexity Estimation

**Estimated LOC**: ~600 (Medium-Large)

**Breakdown**:
- **Frontend Components** (~300 LOC):
  - New `DictionaryPopup` component: ~100 LOC (popup UI, position calculation, pronunciation/examples rendering)
  - New `VocabularySidebar` or tab component: ~80 LOC (saved word list, review interface)
  - Modify `SubtitleList.tsx`: +80 LOC (word tokenization, hover handlers, popup trigger)
  - Modify `VideoPlayer.tsx` subtitle overlay: +40 LOC (same word interaction logic for overlay)

- **Frontend State & Hooks** (~120 LOC):
  - New `useVocabularyStore` Zustand store: ~60 LOC (CRUD for vocabulary, persist)
  - New `useDictionaryLookup` hook: ~40 LOC (fetch/cache dictionary data)
  - New `useWordTokenizer` hook: ~20 LOC (word segmentation logic)

- **Frontend Utilities** (~80 LOC):
  - Dictionary data loader/parser: ~50 LOC (if offline, load JSON; if API, fetch wrapper)
  - Word tokenization helpers: ~30 LOC (language-specific splitting, Intl.Segmenter wrapper)

- **Backend API (optional)** (~100 LOC):
  - New `/api/vocabulary` endpoints (POST, GET, DELETE): ~60 LOC (CRUD handlers)
  - Vocabulary storage repository: ~40 LOC (filesystem or SQLite persistence)

- **Documentation** (~20 LOC):
  - README updates, type definitions

**Lite path checklist**:
- [x] All knowledge within repo (no internet research needed): **NO** — Need to research offline dictionary libraries/APIs (Wiktionary data, Free Dictionary API, CC-CEDICT), word tokenization approaches (Intl.Segmenter browser API, jieba for Chinese), and popup positioning libraries (Floating UI, Radix). Also need UX patterns from Youdao Dictionary, Anki, Language Reactor for reference.
- [ ] Files affected < 5: **NO** — Estimated 8-10 files affected
- [ ] LOC < 150: **NO** — ~600 LOC estimated

**Recommended path**: `full`

**Rationale**: This feature requires **SOTA research** on offline dictionary libraries, word tokenization approaches across languages, and UX patterns from existing language learning tools (Youdao, Language Reactor). The vocabulary collection system also ties into future Flashcard/Quiz features mentioned in the Roadmap, suggesting broader architectural decisions.
