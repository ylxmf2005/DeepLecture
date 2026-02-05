# Milestone 1: Documentation and Tests

**Branch:** issue-14
**Created:** 2026-02-04
**LOC:** 0 (tests only)
**Test Status:** 0/3 test files (tests will fail - no implementation yet)

## Work Completed
- Updated `docs/demo/dual-subtitle.md` with hover dictionary description
- Created `frontend/lib/__tests__/subtitles/display.test.ts` (80 LOC)
- Created `frontend/lib/__tests__/dictionary/tokenize.test.ts` (90 LOC)
- Created `frontend/lib/__tests__/dictionary/lookup.test.ts` (120 LOC)

## Work Remaining (~520 LOC implementation)

### M1: Dictionary Core (Tokenizer + Display + Lookup)
- `frontend/lib/dictionary/types.ts` - DictionaryEntry, DictionaryProvider interfaces
- `frontend/lib/dictionary/tokenize.ts` - tokenizeText with Intl.Segmenter + fallback
- `frontend/lib/dictionary/lookup.ts` - createDictionaryLookup with cache + API
- `frontend/lib/subtitles/display.ts` - createSubtitleRows view model

### M2: UI Components
- `frontend/hooks/useDictionaryLookup.ts` - React hook for lookup state
- `frontend/stores/useVocabularyStore.ts` - Zustand vocabulary persistence
- `frontend/components/content/HoverableSubtitleText.tsx` - Word spans with hover
- `frontend/components/content/DictionaryPopup.tsx` - Definition popup

### M3: Integration
- `frontend/components/features/FlashcardTab.tsx` - Vocabulary list display
- `frontend/components/content/SubtitleList.tsx` - Integrate HoverableSubtitleText
- `frontend/components/video/VideoPlayer.tsx` - Add source/target props, enable hover
- `frontend/components/video/TabContentRenderer.tsx` - Wire FlashcardTab
- `frontend/app/video/[id]/VideoPageClient.tsx` - Pass language context

## Next File Changes
Start with dictionary types and tokenizer:
1. `frontend/lib/dictionary/types.ts`
2. `frontend/lib/dictionary/tokenize.ts`
3. `frontend/lib/subtitles/display.ts`
