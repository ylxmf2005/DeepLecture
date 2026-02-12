# DeepLecture 功能正确性审查报告

**审查日期**: 2026-02-07
**审查范围**: 全项目功能正确性
**审查方法**: 4 域并行 agent 团队审查
**审查重点**: 功能是否正确实现、HCI 合理性、错误是否统一 toast 提示

---

## Executive Summary

| 严重程度 | 数量 | 说明 |
|---------|------|------|
| 🔴 Critical | 3 | 功能完全不可用或架构级死代码 |
| 🟠 High | 6 | 重要功能缺陷或数据丢失风险 |
| 🟡 Medium | 12 | 用户体验缺陷或代码质量问题 |
| 🟢 Low | 12 | 小问题或潜在风险 |
| ℹ️ Info | 12 | 设计观察或改进建议 |

### 功能状态一览

| 功能 | 状态 | 说明 |
|------|------|------|
| Upload (文件/URL) | ✅ 可用 | 异步 merge 丢失 task_id |
| Timeline 生成 | ✅ 可用 | 错误时缺 toast |
| Subtitle 生成/翻译/增强 | ✅ 可用 | 错误时缺 toast |
| Voiceover 生成 | ✅ 可用 | 前后端字段契约断裂、错误缺 toast |
| Slide Lecture 生成 | ✅ 可用 | 错误时缺 toast |
| Ask (AI 问答) | ✅ 可用 | 响应语言硬编码为中文 |
| Note 生成 | ✅ 可用 | 完整链路正确 |
| Explanation 生成 | ✅ 可用 | 依赖具体类型而非协议 |
| **Quiz 生成** | **❌ 完全不可用** | async/sync 不匹配 + 无前端 |
| **Cheatsheet 生成** | **❌ 完全不可用** | async/sync 不匹配，前端有但后端必崩 |
| Fact Verification | ⚠️ 部分可用 | 依赖外部 Claude Code CLI |
| Dictionary 查词 | ✅ 可用 | 设计合理 |
| DnD Tab 布局 | ✅ 可用 | 未来移除 tab 可能导致幽灵 tab |
| Live2D | ✅ 可用 | 模块级全局变量限制单实例 |
| Smart Skip | ✅ 可用 | 设计精巧 |
| SSE/Task 系统 | ✅ 可用 | 队列满时静默丢弃订阅者 |
| Settings/Config | ✅ 可用 | 架构良好 |

---

## 🔴 Critical Issues (3)

### C1. Quiz 和 Cheatsheet 功能完全不可用 — Async/Sync 不匹配
> **来源**: Domain B (B-C1)
> **位置**: `use_cases/quiz.py`, `use_cases/cheatsheet.py`

`QuizUseCase.generate()` 和 `CheatsheetUseCase.generate()` 声明为 `async def` 并使用 `await self._llm.complete()`，但存在三重故障：

1. **`LLMProtocol.complete()` 是同步方法** — `await` 非可等待对象会抛出 `TypeError`
2. **`TaskManager._execute_task()` 在线程池中同步调用** — `async def` 返回的 coroutine 永远不会被执行
3. **调用签名错误** — Quiz/Cheatsheet 用 `complete(system_prompt=..., user_prompt=...)`，但协议要求 `complete(prompt, *, system_prompt=...)`

**影响**: 用户点击生成 Quiz 或 Cheatsheet 后，任务会立即失败。Cheatsheet 前端有完整 UI 但后端必崩。

**修复**: 移除 `async`/`await`，对齐同步调用约定 `llm.complete(user_prompt, system_prompt=system_prompt)`。

---

### C2. Quiz 和 Cheatsheet 未集成 PromptRegistry
> **来源**: Domain B (B-C2)
> **位置**: `use_cases/quiz.py`, `use_cases/cheatsheet.py`, `prompts/registry.py`

两个用例直接调用 prompt 构建函数，绕过了 `PromptRegistry`。`create_default_registry()` 没有注册任何 quiz/cheatsheet prompt builder。这意味着：
- 用户无法在 Settings 中选择替代 prompt 实现
- 路由传入的 `prompts` 参数被完全忽略
- 违反了项目其他所有 AI 功能（Ask/Note/Explanation/Timeline）的架构模式

---

### C3. 死代码 ErrorContext 系统 (~200 行未使用)
> **来源**: Domain C (C-1)
> **位置**: `contexts/ErrorContext.tsx`, `hooks/useErrorHandler.ts`, `components/ui/Toast.tsx`

项目存在**两套 Toast 系统**：
- **Sonner** (活跃): 在 `layout.tsx` 中挂载 `<Toaster>`，约 12 处调用
- **自定义 ErrorContext** (死代码): `ErrorProvider` 从未在组件树中挂载

`ErrorContext.tsx`, `useErrorHandler.ts`, `Toast.tsx`, `useErrors()`, `handleApiError()` 全部未被任何组件使用。这会造成开发者混淆（"该用哪个错误系统？"）。

**修复**: 删除未使用的自定义错误处理系统，或将其替换为 sonner 的封装。

---

## 🟠 High Issues (6)

### H1. SSE 队列满时静默丢弃订阅者 — 客户端永久丢失事件
> **来源**: Domain D (D-005)
> **位置**: `presentation/sse/events.py:84-95`

当订阅者队列满（如浏览器 GC 暂停、tab 在后台），该订阅者被**永久移除**。客户端的 `EventSource` HTTP 连接仍然存活，但不再收到任何事件，且没有任何重连信号。

**影响**: 用户浏览器短暂卡顿后，所有后续任务状态更新将静默丢失。用户可能看到任务一直在 "processing"，实际早已完成。

**建议**: 改为跳过该事件但保留订阅关系（丢事件不丢连接），或发送一个特殊事件让客户端触发重连。

---

### H2. Tab 布局 merge 不清理已移除的 Tab ID
> **来源**: Domain D (D-010)
> **位置**: `frontend/stores/tabLayoutStore.ts:200-237`

`merge` 函数只添加缺失的 tab，从不移除已从代码中删除的 tab。未来如果删除某个 tab，已有用户的 localStorage 会保留一个幽灵 tab，导致渲染错误。

**修复**: 添加 `persistedSidebar.filter(tab => ALL_TABS.has(tab))` 过滤步骤。

---

### H3. Quiz — 无前端 API 客户端和组件
> **来源**: Domain B (B-H1)
> **位置**: `frontend/lib/api/` (缺少 quiz.ts)

后端 quiz 路由完整实现，但没有任何前端组件调用这些 API。`FlashcardTab.tsx` 显示的是词汇卡（来自 Zustand store），而非 AI 生成的测验题。

---

### H4. Quiz/Cheatsheet — 字幕加载缺少 language 参数
> **来源**: Domain B (B-H2)
> **位置**: `use_cases/quiz.py:227-234`, `use_cases/cheatsheet.py:183-188`

`_load_context()` 调用 `self._subtitles.load(content_id)` 但 `SubtitleStorageProtocol.load()` 需要两个参数 `(content_id, language)`。会导致 `TypeError`。

---

### H5. Quiz/Cheatsheet — 用户指令无 Prompt Injection 防护
> **来源**: Domain B (B-H3)
> **位置**: `use_cases/quiz.py`, `use_cases/cheatsheet.py`

`user_instruction` 直接嵌入 LLM prompt，无任何 sanitization。对比 Ask/Note 使用 `sanitize_question()` 和 `sanitize_learner_profile()`。

---

### H6. 异步 merge 操作返回中丢失 task_id
> **来源**: Domain A
> **位置**: `presentation/api/routes/upload.py:69-71`

多文件视频上传 merge 以 `async_mode=True` 执行，返回 `ImportJobResult`。但 `_serialize_upload_result` 只序列化 `content_id/filename/content_type/message`，**丢弃了 `job_id` (task_id) 和 `status`**。

**影响**: 前端无法追踪异步 merge 进度。用户上传多个视频后看到一个 content_id，但内容可能还在处理中。

---

## 🟡 Medium Issues (12)

### 前端静默失败系列 (7 处)

以下用户触发的操作在 API 调用失败时**只 log 不 toast**，用户无任何错误反馈：

| # | 操作 | 位置 | SSE 兜底? |
|---|------|------|----------|
| M1 | Voiceover 生成 | `useVoiceoverHandlers.ts:56` | 🔔 任务提交后有 |
| M2 | Voiceover 删除 | `useVoiceoverHandlers.ts:73` | ❌ |
| M3 | Timeline 生成 | `useTimelineHandlers.ts:75` | 🔔 任务提交后有 |
| M4 | Subtitle 生成 | `useSubtitleHandlers.ts:48` | 🔔 任务提交后有 |
| M5 | Subtitle 翻译 | `useSubtitleHandlers.ts:66` | 🔔 任务提交后有 |
| M6 | Slide 解释/讲座/上传 | `useSlideHandlers.ts:69,91,108` | 部分 🔔 |
| M7 | AskTab 初始化/会话管理 | `AskTab.tsx:98,128,153,186` | ❌ |

> **重要说明**: 对于 M1/M3/M4/M5 等基于 Task 的异步操作，如果任务**成功提交**后失败，`useTaskNotification` 会通过 SSE 发送 toast。但如果**提交 API 调用本身就失败**（如网络错误），用户完全无感知。

### 其他 Medium Issues

| # | 问题 | 位置 |
|---|------|------|
| M8 | Ask 响应语言硬编码为 "Simplified Chinese" | `prompts/ask.py:128` |
| M9 | Note 大纲解析失败时只 log WARNING，调试困难 | `use_cases/note.py:376` |
| M10 | ExplanationUseCase 依赖具体类 `FsExplanationStorage` 而非协议 | `use_cases/explanation.py:49` |
| M11 | `_reconcile_stale_processing()` 只覆盖 4 个 feature | `routes/content.py:78-89` |
| M12 | CheatsheetTab/VerifyTab SSE 重试逻辑重复 ~40 行 | 两个 Tab 组件 |

---

## 🟢 Low Issues (12)

| # | 问题 | 位置 | 来源 |
|---|------|------|------|
| L1 | `future.cancel()` 不能停止已运行的线程 | `task_queue.py:498` | D |
| L2 | SSE 重连后 stale task entries 不清理 | `useTaskStatus.ts:63` | D |
| L3 | `loadAIConfigFromServer` 忽略返回值 | `useGlobalSettingsStore.ts:197` | D |
| L4 | Escape handler 与 focus trap 重复 | `SettingsDialog.tsx:46` | D |
| L5 | Smart Skip 每次 timeupdate 线性扫描 | `useSmartSkip.ts:62` | D |
| L6 | Voiceover auto-switch 无法独立禁用 | `FocusModeHandler.tsx:149` | D |
| L7 | Quiz validate_quiz_item 字段检查顺序不优 | `use_cases/quiz.py:46` | B |
| L8 | Prompt 返回值约定不一致 (user, system) | `prompts/note.py:116` | B |
| L9 | Fact Verification 前端未传 LLM override | `api/factVerification.ts:38` | B |
| L10 | ClaimCard 置信度分数缺乏上下文说明 | `ClaimCard.tsx:88` | B |
| L11 | Cheatsheet `target_pages or 2` 混淆 None 和 0 | `routes/cheatsheet.py:100` | B |
| L12 | MarkdownNoteEditor auto-save 静默失败 | `MarkdownNoteEditor.tsx:45` | C |

---

## ℹ️ Info (12)

| # | 观察 | 位置 | 来源 |
|---|------|------|------|
| I1 | 视频扩展名前后端不完全一致 (.avi/.mkv) | upload 相关 | A |
| I2 | Timeline 复用 SubtitleGenerationError | `use_cases/timeline.py:192` | A |
| I3 | SlideLecture 用 ThreadPoolExecutor 而非 ParallelRunner | `slide_lecture.py:162` | A |
| I4 | Voiceover language 同时作为 TTS 和字幕语言 | `routes/voiceover.py:88` | A |
| I5 | 翻译失败时 fallback 文本 `[Translation failed: ...]` | `subtitle.py:336` | A |
| I6 | SSE event ID 每次连接重置（设计上可接受） | `events.py:177` | D |
| I7 | SQLite 每次操作开新连接（可接受） | `sqlite_task_storage.py:60` | D |
| I8 | `console.warn` 而非 scoped logger | `useDictionaryLookup.ts` | C |
| I9 | catch 块类型判断不一致 | `CheatsheetTab.tsx`, `VerifyTab.tsx` | C |
| I10 | `crepe.create()` promise 无 `.catch()` | `MarkdownNoteEditor.tsx:91` | C |
| I11 | Sonner 未设 toast 数量上限 | `layout.tsx:46` | C |
| I12 | Fact Verification 对 Claude Code CLI 有隐式依赖 | `fact_verification.py` | B |

---

## 错误处理一致性矩阵

### 图例
- ✅ Toast 提示用户
- 🔔 SSE 通知覆盖任务级错误（但提交失败无覆盖）
- 📋 组件内 inline 错误状态
- ⚠️ 静默（仅 log，用户无感知）

| 功能模块 | 操作 | 错误通知方式 |
|---------|------|-------------|
| Voiceover | 生成 | ⚠️ (🔔 SSE 覆盖任务错误) |
| Voiceover | 删除 | ⚠️ |
| Voiceover | 重命名 | ✅ toast.error + toast.success |
| Timeline | 生成 | ⚠️ (🔔 SSE 覆盖) |
| Subtitle | 生成 | ⚠️ (🔔 SSE 覆盖) |
| Subtitle | 翻译 | ⚠️ (🔔 SSE 覆盖) |
| Subtitle | 加载 | ✅ toast.error with description |
| Slide | 解释/讲座/上传 | ⚠️ |
| Ask | 发送消息 | 📋 inline 错误消息 |
| Ask | 初始化/会话管理 | ⚠️ |
| Note | 生成/加载 | ✅ toast.error |
| Explanation | 删除 | ✅ toast.error |
| Explanation | 加载历史 | ⚠️ |
| Cheatsheet | 加载/生成/保存 | 📋 inline loadError |
| Verify | 加载/生成 | 📋 inline loadError |
| Upload | 提交 | 📋 inline error state |
| VideoList | 重命名 | ⚠️ |
| NoteEditor | 自动保存 | ⚠️ |
| SSE Task | 任务完成/失败 | ✅ toast (可配置) |

---

## 架构正面评价

审查中也发现了许多设计良好的方面：

1. **Clean Architecture 分层**：领域层 → 应用层 → 基础设施层 → 表示层 分离清晰
2. **Task 系统崩溃恢复**：SQLite 持久化 + 启动时 `mark_inflight_as_error()` reconciliation
3. **SSE 设计**：先 subscribe 再发 initial events 避免 race condition
4. **Prompt 安全**：`prompt_safety.py` 提供了优秀的注入检测和输入 sanitization
5. **LLM JSON 解析**：`llm_json.py` 使用 `json_repair` 做容错解析
6. **Zustand Stores**：版本迁移、hydration、选择器优化都做得好
7. **DnD 系统**：snapshot/rollback 模式提供干净的撤销语义
8. **Smart Skip**：epsilon 容差和跳跃目标 guard 设计精巧
9. **API 错误分类**：`APIError` 统一分类（NETWORK/TIMEOUT/4xx/5xx）
10. **前端 Loading/Empty 状态**：所有主要组件都有适当的 loading 和空状态提示

---

## 修复优先级建议

### P0 — 立即修复（功能不可用）
1. 修复 quiz.py 和 cheatsheet.py 的 async/sync 不匹配
2. 将 quiz/cheatsheet prompt builders 注册到 PromptRegistry
3. 修复 quiz/cheatsheet 的 subtitle 加载缺参数问题

### P1 — 高优先级（数据丢失/安全）
4. 修复异步 merge 丢失 task_id
5. 修复 SSE 队列满时静默丢弃订阅者
6. 为 quiz/cheatsheet 添加 prompt injection 防护
7. 构建 Quiz 前端 API 客户端和组件

### P2 — 中优先级（用户体验）
8. 为所有静默失败的 handler 添加 `toast.error()` — 特别是任务提交失败时
9. 删除死代码 ErrorContext 系统
10. 修复 Tab Layout merge 不清理已移除 tab
11. 让 Ask 响应语言可配置

### P3 — 低优先级（代码质量）
12. ExplanationUseCase 改为依赖协议而非具体类
13. 扩展 `_reconcile_stale_processing()` 覆盖所有 feature
14. 提取 CheatsheetTab/VerifyTab 共享的 SSE 重试 hook
15. 统一 console.warn → scoped logger

---

## 子报告索引

| 文件 | 域 | 审查员 |
|------|---|-------|
| `review-domain-A-core-pipeline.md` | Upload/Timeline/Subtitle/Voiceover | reviewer-A |
| `review-domain-B-ai-generation.md` | Ask/Note/Quiz/Cheatsheet/Explanation/Verify | reviewer-B |
| `review-domain-C-error-handling.md` | 前端错误处理与 UX 一致性 | reviewer-C |
| `review-domain-D-state-sse-config.md` | Task/SSE/State/Config/DnD/Dictionary/Live2D | reviewer-D |
