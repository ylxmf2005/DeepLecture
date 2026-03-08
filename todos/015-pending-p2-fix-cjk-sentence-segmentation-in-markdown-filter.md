---
status: pending
priority: p2
issue_id: "015"
tags: [code-review, quality, i18n, backend]
dependencies: []
---

# Fix CJK Sentence Segmentation in Markdown Filter

## Problem Statement

Sentence splitting currently requires whitespace after sentence punctuation, which under-segments Chinese/Japanese/Korean text where punctuation is commonly followed directly by the next character.

## Findings

- Split regex is `(?<=[.!?。！？…])\s+`, requiring one or more spaces: [markdown_text_filter.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/shared/markdown_text_filter.py:46).
- CJK prose commonly has no spaces after `。！？`, causing entire paragraphs to remain as single long sentences.
- Long unsplit sentences reduce playback granularity and worsen jump/progress behavior.

## Proposed Solutions

### Option 1: Use Optional-Whitespace Boundary Split

**Approach:** Change to split on punctuation boundaries with optional whitespace (e.g. `\s*`) and filter empties.

**Pros:**
- Simple fix
- Keeps current architecture

**Cons:**
- Needs careful handling of abbreviations/ellipses in Latin text

**Effort:** Small

**Risk:** Low

---

### Option 2: Language-Aware Sentence Tokenization

**Approach:** Branch splitting strategy by detected source language.

**Pros:**
- Better precision across language families

**Cons:**
- Higher complexity and dependency surface

**Effort:** Medium

**Risk:** Medium

---

### Option 3: Hybrid Heuristic + Max-Length Guard

**Approach:** Keep regex split and additionally chunk very long residual sentences by punctuation/length.

**Pros:**
- Safer fallback for worst cases

**Cons:**
- More heuristic behavior

**Effort:** Small-Medium

**Risk:** Medium

## Recommended Action


## Technical Details

**Affected files:**
- [markdown_text_filter.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/shared/markdown_text_filter.py)

## Resources

- **Review target:** `master...feat/notes-read-aloud`

## Acceptance Criteria

- [ ] Chinese text `句一。句二。` is split into separate sentences
- [ ] English sentence splitting behavior remains correct
- [ ] Unit tests cover CJK and Latin samples
- [ ] No regressions in existing markdown cleaning behavior

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Reviewed markdown filter regex and sentence splitter
- Checked language characteristics against current pattern requirements

**Learnings:**
- Current splitter is whitespace-dependent and not robust for CJK punctuation style

## Notes

- Important for multilingual usability and TTS cadence quality.
