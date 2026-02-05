在开始分析前的三问（Linus 风格）
1. 这是个真问题还是臆想出来的？——真问题，用户明确要“取词 + 保存”。
2. 有更简单的方法吗？——有，先做 API + 内存缓存 + 简单词汇表。
3. 会破坏什么吗？——可能破坏字幕点击、双语分行、播放器交互。

基于现有信息，我理解您的需求是：在播放器字幕层和右侧字幕列表中，对“原文字幕”进行悬停取词，弹出释义/音标/例句并可保存到词汇表；双语模式下译文不响应；低延迟优先但不引入不必要复杂度。

Linus式问题分解思考
第一层：数据结构分析
- 核心数据：Subtitle（id/start/end/text）、字幕模式（source/target/dual/dual_reversed）、词典条目、已保存词汇。
- 数据流：useSubtitleManagement → VideoPageClient → VideoPlayer/SubtitleList → HoverableSubtitleText → DictionaryPopup → VocabularyStore。
- 风险：dual 模式用换行合并文本，丢失“哪一行是原文”的语义。

第二层：特殊情况识别
- dual/dual_reversed 两行顺序不同。
- 多行字幕 + 双语合并导致分割歧义。
- 视频字幕层 `pointer-events-none` 与 hover 冲突。
- 不支持词典的语言必须明确禁用。

第三层：复杂度审查
- 本质：对原文词汇 hover 时查词并保存。
- 当前方案不需要三层缓存、离线包、SM-2。
- 简化：API + 内存缓存 + 轻量词汇表即可。

第四层：破坏性分析
- 可能破坏：字幕点击跳转、播放器点击/拖拽、虚拟列表性能。
- 依赖：字幕模式切换逻辑、`mergeSubtitles` 的换行格式。
- 解决：引入“显示用视图模型”，保留源/译语义，不改 Subtitle 结构。

第五层：实用性验证
- 真实存在：外语学习确实需要快速取词。
- 用户规模未知，但实现成本可控。
- 方案复杂度与收益匹配。

决策输出模式
【核心判断】
✅ 值得做：需求明确且用户价值高，用最小实现即可。

【关键洞察】
- 数据结构：必须保留 source/target 的语义边界，不能只靠换行文本。
- 复杂度：去掉离线包、SM-2、DB，先做 API + 内存缓存。
- 风险点：dual 模式错误取词与播放器交互冲突。

【Linus式方案】
1. 先简化数据结构（字幕显示视图模型保留 source/target）。
2. 消除特殊情况（统一用 source/target 行渲染，禁用译文 hover）。
3. 用最笨但清晰的方法（API + Map 缓存）。
4. 保证零破坏性（pointer-events、点击跳转、虚拟列表性能）。

代码审查输出
【品味评分】
🟡 凑合

【致命问题】
- dual 模式把 source/target 合并为纯字符串，导致“原文/译文边界”丢失。
- 播放器字幕层 `pointer-events-none` 与 hover 交互冲突风险高。

# Implementation Plan: Unknown Feature

## Consensus Summary
采取“最小可用 + 可扩展”的折中方案：保留 reducer 的简洁实现（API + 内存缓存 + 简单词汇表），引入 bold 的语言分词（Intl.Segmenter 优先）和可扩展 Provider 接口，但暂不做离线包、SM-2 和多语言字典。双语模式通过明确的 source/target 视图模型来避免误判。

## Goal
在播放器字幕层与侧边字幕列表中，允许仅对原文字幕悬停取词，展示释义/音标/例句并可保存到词汇表，同时在双语模式下译文不响应。

**Success criteria:**
- 悬停原文单词在播放器与侧边列表均能弹出词典，译文行不触发。
- 保存词汇持久化可见（Flashcard tab 显示列表），且不影响字幕点击跳转与视频控制。

**Out of scope:**
- 离线词典包与 IndexedDB 缓存
- SM-2/FSRS 复习算法
- CJK 分词与多语种词典
- 语音发音播放
- However, it it a good idea for future work?
  - ✅ Good to have in the future: 可选离线包（按语言下载）+ CJK 分词与专用词典 + 闪卡复习节奏。
  - ❌ Not needed: 现在引入复杂缓存与复习算法是过度设计。

## Bug Reproduction
**Skip reason**: 这是新功能实现，不是缺陷修复。

## Codebase Analysis

**Files verified (docs/code checked by agents):**
- `docs/demo/dual-subtitle.md`: 当前双语字幕展示流程，无取词描述。
- `README.md`: Roadmap 含 Flashcard。
- `frontend/components/content/SubtitleList.tsx`: 侧边字幕纯文本渲染。
- `frontend/components/video/VideoPlayer.tsx`: 字幕覆盖层为纯文本，外层 `pointer-events-none`。
- `frontend/hooks/useSubtitleManagement.ts`: dual/dual_reversed 通过换行合并文本。
- `frontend/lib/srt.ts`: Subtitle 结构与 mergeSubtitles。
- `frontend/lib/subtitleSearch.ts`: 获取当前播放字幕。
- `frontend/app/video/[id]/VideoPageClient.tsx`: 侧边字幕选择逻辑。
- `frontend/components/video/TabContentRenderer.tsx`: flashcard 为占位。
- `frontend/stores/tabLayoutStore.ts`: flashcard tab 已存在。

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

**Modification level definitions:**
- **minor**: Cosmetic or trivial changes (comments, formatting, <10 LOC changed)
- **medium**: Moderate changes to existing logic (10-50 LOC, no interface changes)
- **major**: Significant structural changes (>50 LOC, interface changes, or new files)
- **remove**: File deletion

**Current architecture notes:**
- 双语字幕以换行合并为 `Subtitle.text`，语义边界丢失。
- 播放器字幕层外层 `pointer-events-none`，需显式允许词级 hover。
- flashcard tab 目前是占位组件，可最小替换为词汇列表。

## Interface Design

**New interfaces:**
- `DictionaryEntry` (`frontend/lib/dictionary/types.ts`)
  - `word`, `phonetic?`, `definitions[]`, `examples[]`, `source`
  - 保存最小展示信息，无复习字段。

- `DictionaryProvider`
  - `supports(locale: string): boolean`
  - `lookup(word: string, locale: string, signal?: AbortSignal): Promise<DictionaryEntry | null>`

- `tokenizeText(text, locale, options?)` (`frontend/lib/dictionary/tokenize.ts`)
  - 返回 `Token[]`：`{ text, isWord, normalized, start, end }`
  - 若 `Intl.Segmenter` 可用则用它，否则正则 fallback。

- `createDictionaryLookup(provider)` (`frontend/lib/dictionary/lookup.ts`)
  - Step 1: 规范化词（小写/去标点）。
  - Step 2: 检查 provider 支持与内存缓存。
  - Step 3: fetch 查词，成功则缓存。
  - Step 4: 返回 entry 或 null。

- `SubtitleRow` (`frontend/lib/subtitles/display.ts`)
  - `id`, `startTime`, `endTime`, `sourceText?`, `targetText?`
  - Step 1: 根据 mode 生成 rows
  - Step 2: dual/dual_reversed 明确行顺序
  - Step 3: 返回可用于渲染的行数据

- `useVocabularyStore` (`frontend/stores/useVocabularyStore.ts`)
  - `items: VocabularyItem[]`
  - `add(item)`, `remove(word, locale)`, `has(word, locale)`

- `HoverableSubtitleText`
  - Props: `text`, `locale`, `interactive`, `context`, `onSave`
  - 仅当 `interactive` 且语言支持时启用 hover。

- `DictionaryPopup`
  - Props: `anchorRect`, `entry`, `loading`, `error`, `onSave`, `onClose`.

**Modified interfaces:**
`VideoPlayerProps`（新增源/译字幕与语言）
```diff
 interface VideoPlayerProps {
     subtitles?: Subtitle[];
+    subtitlesSource?: Subtitle[];
+    subtitlesTarget?: Subtitle[];
+    originalLanguage?: string;
     subtitleMode?: SubtitlePlayerMode;
 }
```

`SubtitleList` props（新增 mode + source/target 以区分原文/译文）
```diff
- subtitles: Subtitle[];
+ subtitleMode: SubtitleDisplayMode;
+ subtitlesSource: Subtitle[];
+ subtitlesTarget: Subtitle[];
+ originalLanguage: string;
```

`TabContentProps`（传递 source/target 与语言信息到 SubtitleList）
```diff
- sidebarSubtitles: Subtitle[];
+ subtitlesSource: Subtitle[];
+ subtitlesTarget: Subtitle[];
+ sidebarSubtitleMode: SubtitleDisplayMode;
+ originalLanguage: string;
```

**Documentation changes:**
- `docs/demo/dual-subtitle.md`：加入“悬停取词 + 词汇保存”说明。

## Documentation Planning

### High-level design docs (docs/)
- `docs/demo/dual-subtitle.md` — update demo flow with hover dictionary behavior

```diff
-  - 字幕区域自动同步追踪视频进度，并支持点击任意字幕片段实时跳转到对应时间点
+  - 字幕区域自动同步追踪视频进度，并支持点击任意字幕片段实时跳转到对应时间点
+  - 悬停原文单词可弹出释义并保存词汇，译文不响应
```

### Folder READMEs
- 无（当前无相关模块 README 需要更新）

### Interface docs
- 无（目前不存在组件/接口 companion .md）

## Test Strategy

**Test modifications:**
- `frontend/lib/subtitles/display.test.ts`
  - Test case: dual 模式 source/target 行顺序正确
  - Test case: dual_reversed 行顺序正确
  - Test case: target-only 不生成 source 行

- `frontend/lib/dictionary/tokenize.test.ts`
  - Test case: 英文标点分割与保留空白
  - Test case: fallback 分词在无 Intl.Segmenter 环境可用

- `frontend/lib/dictionary/lookup.test.ts`
  - Test case: 缓存命中不 повтор fetch
  - Test case: 不支持语言返回 null
  - Test case: fetch 失败返回 null 且不污染缓存

**New test files:**
- `frontend/lib/subtitles/display.test.ts` (Estimated: 80 LOC)
- `frontend/lib/dictionary/tokenize.test.ts` (Estimated: 90 LOC)
- `frontend/lib/dictionary/lookup.test.ts` (Estimated: 120 LOC)

**Test data required:**
- 简短字幕样例（source/target 两行）
- 伪造 fetch 响应 JSON

## Implementation Steps

**Step 1: Documentation change** (Estimated: 20 LOC)
- File changes: `docs/demo/dual-subtitle.md`
Dependencies: None
Correspondence:
- Docs: 明确 hover 仅原文有效、可保存词汇
- Tests: N/A

**Step 2: Test case changes** (Estimated: 290 LOC)
- File changes:
  - `frontend/lib/subtitles/display.test.ts`
  - `frontend/lib/dictionary/tokenize.test.ts`
  - `frontend/lib/dictionary/lookup.test.ts`
Dependencies: Step 1
Correspondence:
- Docs: 约束 dual 行顺序与 hover 行为
- Tests: 覆盖分词、行语义与缓存

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
Dependencies: Step 2
Correspondence:
- Docs: 实现“原文 hover 取词 + 词汇保存”
- Tests: 满足 display/tokenize/lookup 的行为断言

Implementation sketch (key idea, <20 LOC):
```diff
- {subtitle.text}
+ <HoverableSubtitleText
+   text={row.sourceText}
+   locale={originalLanguage}
+   interactive
+ />
+ {row.targetText && <div className="text-muted">{row.targetText}</div>}
```

**Total estimated complexity:** 830 LOC (Medium)
**Recommended approach:** Milestone commits
**Milestone strategy** *(only if large)*:
- **M1**: 字幕视图模型 + 分词 + 查词逻辑
- **M2**: HoverableSubtitleText + DictionaryPopup 集成
- **M3**: FlashcardTab 最小词汇列表

## Success Criteria

- [ ] 原文 hover 在播放器与侧边字幕都能弹出词典
- [ ] 译文行不触发 hover
- [ ] 保存词汇在 Flashcard tab 可见且持久化
- [ ] 不影响字幕点击跳转与播放控制

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 双语行语义丢失导致误取词 | H | H | 使用 `SubtitleRow` 明确 source/target |
| 播放器交互被字幕阻挡 | M | H | 仅词级 `pointer-events-auto`，容器保持透明 |
| API 语言覆盖不足 | H | M | 仅对支持语言启用；未支持直接禁用 |
| 虚拟列表性能下降 | M | M | tokenization 结果 memo/cache |

## Dependencies

- 外部服务：Free Dictionary API（仅作为默认 provider）
- 浏览器能力：Intl.Segmenter（无则 fallback）
- 新增 npm 依赖：无
