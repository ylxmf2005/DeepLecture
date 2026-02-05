【思考前提】
```text
1. "这是个真问题还是臆想出来的？" - 拒绝过度设计
2. "有更简单的方法吗？" - 永远寻找最简方案
3. "会破坏什么吗？" - 向后兼容是铁律
```

基于现有信息，我理解您的需求是：在现有字幕语义模式（source/target/dual）基础上，实现原文/译文快速切换，并在用户离开页面时自动切换到译文、返回时切回（或恢复）原模式，同时避免引入“字幕轨道”这种多余抽象，确保文档与设置界面同步更新。

【Linus式问题分解思考】

第一层：数据结构分析
"Bad programmers worry about the code. Good programmers worry about data structures."
- 核心数据：`SubtitleDisplayMode`、是否有翻译字幕、播放状态、离开/返回状态、全局播放设置
- 数据流向：`useSubtitleManagement` 提供字幕与模式，`VideoPageClient` 持有与分发设置，`FocusModeHandler` 响应可见性事件
- 不必要复制：不要引入“轨道注册表”，用现有模式即可表达“原/译”

第二层：特殊情况识别
"好代码没有特殊情况"
- 分支来源：无翻译字幕、当前模式为 `off/dual/dual_reversed`、自动暂停开启、短暂切换标签页
- 真业务：离开时切换译文、返回时恢复；其余是防抖/避免误触
- 消除分支：用“是否有译文 + 是否自动切换 + 是否已自动切换过”的最小状态来消解特殊情况

第三层：复杂度审查
"如果实现需要超过3层缩进，重新设计它"
- 本质：在可见性变化时调整字幕显示模式
- 概念最小化：只加一个布尔设置 + 一个短延迟；不新增轨道/接口/后端
- 复杂度减半：不引入新 store 和新 API

第四层：破坏性分析
"Never break userspace"
- 受影响功能：字幕模式持久化、专注模式自动暂停、播放器快捷键
- 依赖风险：新增设置字段需默认值，避免破坏旧存储
- 迁移策略：保持默认值合并，不强制 bump 版本；避免改变现有字段语义

第五层：实用性验证
"Theory and practice sometimes clash. Theory loses. Every single time."
- 真实存在：语言学习场景对“离开=译文、回来=原文”很常见
- 用户覆盖：双语字幕用户
- 复杂度匹配：只加少量逻辑即可满足需求

【核心判断】
✅ 值得做：需求真实且能用现有语义模式低成本实现
❌ 不值得做：新增“字幕轨道”与后端 tracks API，收益低且风险高

【关键洞察】
- 数据结构：`SubtitleDisplayMode` 已经是“原/译/双语”的最小表达
- 复杂度：轨道抽象会制造双重状态与迁移风险
- 风险点：可见性事件与自动暂停逻辑互相短路导致字幕恢复失效

【Linus式方案】
1. 第一步永远是简化数据结构：只加一个布尔设置
2. 消除所有特殊情况：只有“有译文+自动切换+短延迟”才切
3. 用最笨但最清晰的方式实现：FocusModeHandler 里加少量逻辑
4. 确保零破坏性：默认关闭、旧设置自动兼容

【品味评分】
🟡 凑合
【致命问题】
- 继续叠加“轨道”概念会引入双重状态与持久化冲突，这是自找麻烦

**Implementation Plan: Unknown Feature**

**Consensus Summary**
保持现有 `SubtitleDisplayMode` 语义模式不变，新增“离开自动切译文”的最小设置与逻辑，补上快捷切换按钮与快捷键。避免引入字幕轨道与后端 tracks API，同时加入离开防抖与“仅在有译文时切换”的保护，降低 UX 风险。

**Goal**
在播放器中实现原文/译文一键切换，并在用户离开页面时自动切换到译文、返回时恢复之前模式，且不破坏现有字幕/专注模式逻辑。

**Success criteria:**
- 用户可通过按钮或快捷键在 `source` 和 `target` 间快速切换
- 离开页面超过阈值时自动切换到译文（仅在翻译存在时）
- 返回页面后恢复离开前模式，不覆盖用户手动切换

**Out of scope:**
- 轨道注册表、命名字幕副本、后端 `/tracks` API
- ✅ Good to have in the future: 如果确有“命名副本”诉求，可新增字幕元数据与存储命名规则
- ❌ Not needed: 当前仅有原/译双轨，额外抽象是过度设计

**Bug Reproduction**
Skip reason: 这是新功能，不是 bug 修复。

**Codebase Analysis**
**Files verified (docs/code checked by agents):**
- `docs/demo/dual-subtitle.md`: 现有双语字幕说明
- `docs/demo/focus-mode.md`: 专注模式文档目前仅有图片
- `frontend/stores/types.ts`: `SubtitleDisplayMode` 与 `PlaybackSettings`
- `frontend/stores/useGlobalSettingsStore.ts`: 全局设置持久化与 action
- `frontend/hooks/useSubtitleManagement.ts`: 字幕加载与语义模式
- `frontend/components/features/FocusModeHandler.tsx`: 可见性事件与自动暂停
- `frontend/components/video/VideoPlayer.tsx`: 字幕菜单与快捷键
- `frontend/components/dialogs/settings/PlayerTab.tsx`: 播放器设置 UI
- `frontend/app/video/[id]/VideoPageClient.tsx`: 设置与字幕状态装配

**File changes:**

| File | Level | Purpose |
|------|-------|---------|
| `frontend/stores/types.ts` | minor | 新增自动切换设置字段 |
| `frontend/stores/useGlobalSettingsStore.ts` | medium | 增加设置 action 与持久化 |
| `frontend/hooks/useVideoPageSettings.ts` | minor | 透出新设置与 action |
| `frontend/components/dialogs/settings/PlayerTab.tsx` | medium | UI 开关 |
| `frontend/app/video/[id]/VideoPageClient.tsx` | medium | 传递字幕模式与自动切换设置 |
| `frontend/components/features/FocusModeHandler.tsx` | medium | 自动切换与恢复逻辑（含防抖） |
| `frontend/components/video/VideoPlayer.tsx` | medium | 快捷切换按钮 + 快捷键 |
| `frontend/lib/subtitleAutoSwitch.ts` (new) | major | 纯函数决策，便于测试 |
| `frontend/lib/__tests__/subtitleAutoSwitch.test.ts` (new) | major | 自动切换逻辑单测 |
| `frontend/vitest.config.ts` (new) | major | 测试配置 |
| `frontend/package.json` | minor | 测试脚本与 dev 依赖 |
| `docs/demo/dual-subtitle.md` | minor | 文档补充 |
| `docs/demo/focus-mode.md` | minor | 文档补充 |

**Modification level definitions:**
- **minor**: Cosmetic or trivial changes (<10 LOC)
- **medium**: Moderate logic changes (10-50 LOC)
- **major**: Significant structural changes (>50 LOC, interface changes, or new files)
- **remove**: File deletion

**Current architecture notes:**
- 字幕模式已语义化（`source/target/dual/dual_reversed`），无需轨道抽象
- `FocusModeHandler` 已监听 `visibilitychange`，可复用同一入口
- 翻译可用性由 `content.translationStatus === "ready"` 决定

**Interface Design**

**New interfaces:**
- `frontend/lib/subtitleAutoSwitch.ts`
  - `getAutoSwitchModeOnHide(...) -> SubtitleDisplayMode | null`
  - `getAutoSwitchModeOnShow(...) -> SubtitleDisplayMode | null`
  - 语义：根据当前模式、是否可译、是否启用自动切换，返回需要切换/恢复的模式
  - 复杂度 < 20 LOC，无需步骤拆解

**Modified interfaces:**
- `PlaybackSettings` 追加布尔开关
```diff
 export interface PlaybackSettings {
     autoPauseOnLeave: boolean;
     autoResumeOnReturn: boolean;
+    autoSwitchSubtitlesOnLeave: boolean;
     summaryThresholdSeconds: number;
     subtitleContextWindowSeconds: number;
     subtitleRepeatCount: number;
 }
```

- `FocusModeHandlerProps` 增加字幕切换相关字段
```diff
 interface FocusModeHandlerProps {
     playerRef: React.RefObject<VideoPlayerRef | null>;
     subtitles: Subtitle[];
     currentTime: number;
     learnerProfile?: string;
     // Settings
     autoPauseOnLeave: boolean;
     autoResumeOnReturn: boolean;
+    autoSwitchSubtitlesOnLeave: boolean;
+    subtitleMode: SubtitleDisplayMode;
+    hasTranslation: boolean;
+    onSubtitleModeChange: (mode: SubtitleDisplayMode) => void;
     summaryThresholdSeconds: number;
     // Smart Skip settings
     skipRamblingEnabled: boolean;
     timelineEntries: TimelineEntry[];
     onAddToAsk: (item: AskContextItem) => void;
     onAddToNotes: (markdown: string) => void;
 }
```

**Documentation changes:**
- `docs/demo/dual-subtitle.md`: 增加“快捷切换与自动切换”说明
- `docs/demo/focus-mode.md`: 增加自动切换字幕说明

**Documentation Planning**

### High-level design docs (docs/)
- `docs/demo/dual-subtitle.md` — update 快捷切换与自动切换说明
```diff
 - 开始观看体验
   - 可在播放器区域或字幕区域灵活设置字幕的显示方式
+  - 支持一键在原文/译文之间切换（按钮/快捷键）
+  - 离开页面可自动切换为译文，返回后恢复原模式
```

- `docs/demo/focus-mode.md` — update 自动切换字幕的行为描述
```diff
 # 专注模式
+离开页面时可自动切换到译文字幕，返回后恢复离开前的字幕模式。
+（需在设置中开启）
```

### Folder READMEs
- N/A

### Interface docs
- N/A

**Command interface citation**: N/A（本计划未引用任何命令接口）

**Test Strategy**

**Test modifications:**
- `frontend/lib/__tests__/subtitleAutoSwitch.test.ts`
  - Test case: 自动切换关闭时不改变模式
  - Test case: 无翻译时不切换
  - Test case: `source/dual/dual_reversed` 在离开时切到 `target`
  - Test case: 返回时仅在自动切换触发且当前仍为 `target` 时恢复
  - Test case: 用户手动改回 `source` 时不被恢复覆盖

**New test files:**
- `frontend/lib/__tests__/subtitleAutoSwitch.test.ts` — 自动切换纯逻辑测试（Est: 60 LOC）

**Test data required:**
- 无

**Implementation Steps**

**Step 1: Documentation change** (Estimated: 30 LOC)
- File changes: `docs/demo/dual-subtitle.md`, `docs/demo/focus-mode.md`
Dependencies: None
Correspondence:
- Docs: 补充快捷切换与自动切换说明
- Tests: N/A

**Step 2: Test case changes** (Estimated: 90 LOC)
- File changes: `frontend/vitest.config.ts`, `frontend/lib/__tests__/subtitleAutoSwitch.test.ts`, `frontend/package.json`
Dependencies: Step 1
Correspondence:
- Docs: 对应 Step 1 的自动切换描述
- Tests: 新增自动切换逻辑单测

**Step 3: Implementation change** (Estimated: 140 LOC)
- File changes:
  - `frontend/stores/types.ts`
  - `frontend/stores/useGlobalSettingsStore.ts`
  - `frontend/hooks/useVideoPageSettings.ts`
  - `frontend/components/dialogs/settings/PlayerTab.tsx`
  - `frontend/app/video/[id]/VideoPageClient.tsx`
  - `frontend/components/features/FocusModeHandler.tsx`
  - `frontend/components/video/VideoPlayer.tsx`
  - `frontend/lib/subtitleAutoSwitch.ts`
Dependencies: Step 2
Correspondence:
- Docs: Step 1 的行为与设置描述
- Tests: Step 2 的自动切换单测逻辑落地

**Total estimated complexity:** 260 LOC (Medium)
**Recommended approach:** Single session (small, low-risk change set)

**Success Criteria**
- [ ] 离开页面 > 阈值时自动切到译文（有译文且开启开关）
- [ ] 返回页面时恢复离开前模式，不覆盖用户手动切换
- [ ] 原/译一键切换按钮 + `T` 快捷键可用

**Risks and Mitigations**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 自动切换与自动暂停逻辑互相短路 | M | M | 在 `visibilitychange` 中先处理字幕切换，再处理暂停/摘要 |
| 短暂切换标签页导致误触 | M | M | 增加 1-2s 防抖延迟 |
| 无译文仍切换导致空白字幕 | M | L | 仅在 `hasTranslation` 为 true 时切换 |

**Dependencies**
- 新增 dev 依赖：`vitest`（仅用于纯函数测试）
