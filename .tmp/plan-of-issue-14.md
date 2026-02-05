## Description

Add a hover-to-lookup dictionary feature for video subtitles (both on the video player overlay and right sidebar). When users hover over words in the **original language** subtitle only, a popup dictionary appears with word definitions, pronunciation (phonetic transcription), and example sentences. Users can save words to a vocabulary collection for later review.

**Key requirements:**
- Only applies to original language text, NOT translations
- For bilingual subtitles, hovering on translation text does nothing
- Works both on video player subtitle overlay AND right sidebar subtitle panel
- Low latency (API + in-memory cache, no complex offline bundles)
- Vocabulary collection system (save words, view in Flashcard tab)
- Similar to Youdao Dictionary's word-picking (取词) feature

**Related modules:** frontend/components/content, frontend/components/video, frontend/stores

## Proposed Solution

### Consensus Summary

采取"最小可用 + 可扩展"的折中方案：保留 reducer 的简洁实现（API + 内存缓存 + 简单词汇表），引入 bold 的语言分词（Intl.Segmenter 优先）和可扩展 Provider 接口，但暂不做离线包、SM-2 和多语言字典。双语模式通过明确的 source/target 视图模型来避免误判。

### Goal

在播放器字幕层与侧边字幕列表中，允许仅对原文字幕悬停取词，展示释义/音标/例句并可保存到词汇表，同时在双语模式下译文不响应。

**Success criteria:**
- 悬停原文单词在播放器与侧边列表均能弹出词典，译文行不触发
- 保存词汇持久化可见（Flashcard tab 显示列表），且不影响字幕点击跳转与视频控制

**Out of scope:**
- 离线词典包与 IndexedDB 缓存
- SM-2/FSRS 复习算法
- CJK 分词与多语种词典
- 语音发音播放

### Codebase Analysis

**File changes:**

| File | Level | Purpose |
|------|-------|---------|
| `docs/demo/dual-subtitle.md` | minor | 描述取词与词汇保存 |
| `frontend/lib/dictionary/types.ts` (new) | major | 词典条目与 Provider 类型 |
| `frontend/lib/dictionary/tokenize.ts` (new) | major | 分词（Intl.Segmenter + fallback） |
| `frontend/lib/dictionary/lookup.ts` (new) | major | 查询逻辑 + 内存缓存 |
| `frontend/lib/subtitles/display.ts` (new) | medium | 生成含 source/target 的字幕视图模型 |
| `frontend/hooks/useDictionaryLookup.ts` (new) | medium | UI 侧查询与状态 |
| `frontend/stores/useVocabularyStore.ts` (new) | medium | 词汇表持久化 |
| `frontend/components/content/HoverableSubtitleText.tsx` (new) | major | 逐词渲染与 hover 触发 |
| `frontend/components/content/DictionaryPopup.tsx` (new) | major | 弹窗显示与保存按钮 |
| `frontend/components/features/FlashcardTab.tsx` (new) | medium | 词汇列表最小展示 |
| `frontend/components/content/SubtitleList.tsx` | major | 用视图模型渲染，区分源/译 |
| `frontend/components/video/VideoPlayer.tsx` | major | 播放器字幕支持 hover 与分行 |
| `frontend/components/video/TabContentRenderer.tsx` | medium | flashcard tab 改为词汇列表 |
| `frontend/app/video/[id]/VideoPageClient.tsx` | medium | 传递 source/target 与语言信息 |

### Interface Design

**New interfaces:**

- `DictionaryEntry` (`frontend/lib/dictionary/types.ts`)
  - `word`, `phonetic?`, `definitions[]`, `examples[]`, `source`

- `DictionaryProvider`
  - `supports(locale: string): boolean`
  - `lookup(word: string, locale: string, signal?: AbortSignal): Promise<DictionaryEntry | null>`

- `tokenizeText(text, locale, options?)` (`frontend/lib/dictionary/tokenize.ts`)
  - 返回 `Token[]`：`{ text, isWord, normalized, start, end }`
  - 若 `Intl.Segmenter` 可用则用它，否则正则 fallback

- `SubtitleRow` (`frontend/lib/subtitles/display.ts`)
  - `id`, `startTime`, `endTime`, `sourceText?`, `targetText?`

- `useVocabularyStore` (`frontend/stores/useVocabularyStore.ts`)
  - `items: VocabularyItem[]`
  - `add(item)`, `remove(word, locale)`, `has(word, locale)`

**Modified interfaces:**

```diff
 interface VideoPlayerProps {
     subtitles?: Subtitle[];
+    subtitlesSource?: Subtitle[];
+    subtitlesTarget?: Subtitle[];
+    originalLanguage?: string;
     subtitleMode?: SubtitlePlayerMode;
 }
```

### Test Strategy

**New test files:**
- `frontend/lib/subtitles/display.test.ts` (Estimated: 80 LOC)
- `frontend/lib/dictionary/tokenize.test.ts` (Estimated: 90 LOC)
- `frontend/lib/dictionary/lookup.test.ts` (Estimated: 120 LOC)

**Test cases:**
- dual 模式 source/target 行顺序正确
- dual_reversed 行顺序正确
- 英文标点分割与保留空白
- fallback 分词在无 Intl.Segmenter 环境可用
- 缓存命中不重复 fetch
- 不支持语言返回 null
- fetch 失败返回 null 且不污染缓存

### Implementation Steps

**Step 1: Documentation change** (Estimated: 20 LOC)
- File changes: `docs/demo/dual-subtitle.md`
- Dependencies: None

**Step 2: Test case changes** (Estimated: 290 LOC)
- File changes:
  - `frontend/lib/subtitles/display.test.ts`
  - `frontend/lib/dictionary/tokenize.test.ts`
  - `frontend/lib/dictionary/lookup.test.ts`
- Dependencies: Step 1

**Step 3: Implementation change** (Estimated: 520 LOC)
- File changes:
  - `frontend/lib/dictionary/types.ts`
  - `frontend/lib/dictionary/tokenize.ts`
  - `frontend/lib/dictionary/lookup.ts`
  - `frontend/lib/subtitles/display.ts`
  - `frontend/hooks/useDictionaryLookup.ts`
  - `frontend/stores/useVocabularyStore.ts`
  - `frontend/components/content/HoverableSubtitleText.tsx`
  - `frontend/components/content/DictionaryPopup.tsx`
  - `frontend/components/features/FlashcardTab.tsx`
  - `frontend/components/content/SubtitleList.tsx`
  - `frontend/components/video/VideoPlayer.tsx`
  - `frontend/components/video/TabContentRenderer.tsx`
  - `frontend/app/video/[id]/VideoPageClient.tsx`
- Dependencies: Step 2

**Total estimated complexity:** 830 LOC (Medium)
**Recommended approach:** Milestone commits

**Milestone strategy:**
- **M1**: 字幕视图模型 + 分词 + 查词逻辑
- **M2**: HoverableSubtitleText + DictionaryPopup 集成
- **M3**: FlashcardTab 最小词汇列表

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 双语行语义丢失导致误取词 | H | H | 使用 `SubtitleRow` 明确 source/target |
| 播放器交互被字幕阻挡 | M | H | 仅词级 `pointer-events-auto`，容器保持透明 |
| API 语言覆盖不足 | H | M | 仅对支持语言启用；未支持直接禁用 |
| 虚拟列表性能下降 | M | M | tokenization 结果 memo/cache |

### Dependencies

- 外部服务：Free Dictionary API（仅作为默认 provider）
- 浏览器能力：Intl.Segmenter（无则 fallback）
- 新增 npm 依赖：无

## Related PR

TBD - will be updated when PR is created
