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
