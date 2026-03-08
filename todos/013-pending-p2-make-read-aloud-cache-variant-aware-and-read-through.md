---
status: pending
priority: p2
issue_id: "013"
tags: [code-review, performance, caching, backend]
dependencies: []
---

# Make Read-Aloud Cache Variant-Aware and Read-Through

## Problem Statement

Current read-aloud cache keys only by paragraph/sentence index, ignoring language/model/voice variants, and the generation path always synthesizes instead of reading cache first.

## Findings

- Cache key uses `p{para}_s{idx}` only: [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py:142).
- Cached path is `{content_id}/read_aloud_cache/{sentence_key}.mp3` with no variant suffix: [fs_read_aloud_cache.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_read_aloud_cache.py:65).
- Stream accepts `target_language` and `tts_model`, but they are not part of cache identity: [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/presentation/api/routes/read_aloud.py:29).
- Generation only writes cache and never checks cache before translation/TTS: [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py:182).

## Proposed Solutions

### Option 1: Variant Hash in Sentence Key + Read-Through Cache

**Approach:** Add variant components (`target_language`, `source_language`, `tts_model`, selected voice) into cache key and lookup before synthesize.

**Pros:**
- Correct cache isolation
- Large cost/latency reduction on replay

**Cons:**
- Requires URL/key format migration

**Effort:** Medium

**Risk:** Low

---

### Option 2: Cache Manifest Per Run

**Approach:** Store a manifest mapping sentence index to artifact file per run config.

**Pros:**
- Clear compatibility story
- Easier invalidation by manifest version

**Cons:**
- More metadata management

**Effort:** Medium-Large

**Risk:** Medium

---

### Option 3: Disable Cross-Run Reuse (Run-Scoped Cache)

**Approach:** Keep cache only for active run to avoid collisions.

**Pros:**
- Simpler correctness guarantee

**Cons:**
- Loses replay performance benefit

**Effort:** Small

**Risk:** Low

## Recommended Action


## Technical Details

**Affected files:**
- [read_aloud.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/use_cases/read_aloud.py)
- [fs_read_aloud_cache.py](/Users/EthanLee/Desktop/CourseSubtitle/src/deeplecture/infrastructure/repositories/fs_read_aloud_cache.py)
- [readAloud.ts](/Users/EthanLee/Desktop/CourseSubtitle/frontend/lib/api/readAloud.ts)

## Resources

- **Review target:** `master...feat/notes-read-aloud`

## Acceptance Criteria

- [ ] Cache key uniquely identifies language/model/voice variant
- [ ] Generation path checks cache before translation/TTS
- [ ] Re-run same config reuses cached audio
- [ ] Different config cannot overwrite/replay wrong audio

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Codex

**Actions:**
- Traced key construction and cache path derivation
- Compared stream request params against cache identity
- Verified no read-through lookup in generation loop

**Learnings:**
- Current cache design can mix variants and misses easy performance wins

## Notes

- Closely related to session identity work in `003`.
