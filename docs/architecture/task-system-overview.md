# DeepLecture 任务系统架构文档

## 概述

DeepLecture 使用基于 SSE (Server-Sent Events) 的异步任务系统来处理耗时的后台操作。本文档详细描述了从用户点击到任务完成的完整数据流、状态管理机制、以及前后端协同工作的方式。

---

## 1. 13 种任务类型

系统支持 13 种任务类型，分为 4 个类别：

| 分类 | 任务类型 | 说明 | 文件引用 |
|------|----------|------|----------|
| **字幕** | `subtitle_generation` | 从音频生成字幕（Whisper 转录） | `domain/entities/task.py:33` |
| | `subtitle_translation` | 翻译字幕到目标语言 | `frontend/lib/taskTypes.ts:57` |
| **视频** | `video_generation` | 生成带字幕的视频 | `frontend/lib/taskTypes.ts:65` |
| | `video_merge` | 合并幻灯片讲解视频 | `frontend/lib/taskTypes.ts:69` |
| | `video_import_url` | 从 URL 导入视频 | `frontend/lib/taskTypes.ts:73` |
| | `pdf_merge` | 合并 PDF 文件 | `frontend/lib/taskTypes.ts:77` |
| **AI 分析** | `timeline_generation` | 生成课程时间线 | `frontend/lib/taskTypes.ts:61` |
| | `voiceover_generation` | TTS 语音合成 | `frontend/lib/taskTypes.ts:81` |
| | `slide_explanation` | AI 幻灯片讲解 | `frontend/lib/taskTypes.ts:85` |
| | `fact_verification` | 事实核查 | `frontend/lib/taskTypes.ts:89` |
| | `note_generation` | 自动生成笔记 | `frontend/lib/taskTypes.ts:97` |
| | `quiz_generation` | 自动生成测验 | `frontend/lib/taskTypes.ts:101` |
| | `cheatsheet_generation` | 生成知识速查表 | `frontend/lib/taskTypes.ts:93` |

**遗留兼容性**: `subtitle_enhancement` 是 `subtitle_translation` 的别名，在前端会自动规范化 (`frontend/lib/taskTypes.ts:11-13`)。

---

## 2. 后端：任务状态机

任务状态由 `TaskStatus` 枚举定义 (`domain/entities/task.py:10-20`)，包含 4 种状态：

```
PENDING → PROCESSING → READY (成功)
                    ↘ ERROR (失败)
```

### 状态转换规则

```
                    ┌─────────────────────────────────────┐
                    │         PENDING (待处理)             │
                    │  - 任务已创建，等待 worker 执行       │
                    │  - progress = 0                     │
                    └──────────────┬──────────────────────┘
                                   │
                         worker 开始执行 / ctx.progress() 调用
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │       PROCESSING (执行中)            │
                    │  - worker 正在执行任务               │
                    │  - progress = 1-99                  │
                    └──────────────┬──────────────────────┘
                                   │
                      ┌────────────┴────────────┐
                      │                         │
               任务执行成功                  任务执行失败
              callable 正常返回             抛出异常 / 超时
                      │                         │
                      ▼                         ▼
         ┌─────────────────────────┐  ┌─────────────────────────┐
         │   READY (完成-终态)      │  │   ERROR (错误-终态)      │
         │  - progress = 100       │  │  - error 字段记录原因     │
         │  - 不可再变更            │  │  - 不可再变更            │
         └─────────────────────────┘  └─────────────────────────┘
```

**终态 (Terminal State)**: `READY` 和 `ERROR` 是终态，一旦进入就不能再改变 (`domain/entities/task.py:18-20`)。这是通过 `is_terminal()` 方法在状态更新前检查实现的 (`infrastructure/workers/task_queue.py:224`)。

**状态转换代码路径**:
- `PENDING → PROCESSING`: `TaskManager.update_task_progress()` (`infrastructure/workers/task_queue.py:229`)
- `PROCESSING → READY`: `TaskManager.complete_task()` (`infrastructure/workers/task_queue.py:244`)
- `PROCESSING → ERROR`: `TaskManager.fail_task()` (`infrastructure/workers/task_queue.py:269`)

---

## 3. 后端：数据流

从 API 请求到任务完成的完整流程：

```
用户点击按钮
    │
    ▼
Flask Route (presentation/api/routes/*.py)
    │ 调用 UseCase
    ▼
UseCase (use_cases/*.py)
    │ 创建 TaskFn callable
    ▼
TaskManager.submit() (infrastructure/workers/task_queue.py:131)
    │
    ├─ 1. 创建 Task 实体 (domain/entities/task.py:24)
    │     - id: {type}_{content_id}_{timestamp}_{uuid}
    │     - status: PENDING
    │     - progress: 0
    │
    ├─ 2. 写入内存字典 (self._tasks[task_id])
    │
    ├─ 3. 持久化到 SQLite (infrastructure/repositories/sqlite_task_storage.py:68)
    │     - INSERT OR REPLACE 语句
    │     - WAL 模式确保并发安全
    │
    ├─ 4. 放入队列 (self._queue.put_nowait(item))
    │     - 如果队列满，立即标记为 ERROR 并抛出异常
    │
    └─ 5. 广播 SSE "started" 事件 (presentation/sse/events.py:70)
         - 所有订阅该 content_id 的客户端立即收到通知

    ▼
WorkerPool 消费循环 (infrastructure/workers/task_queue.py:445)
    │ 从队列取出任务
    ▼
ThreadPoolExecutor 执行 (infrastructure/workers/task_queue.py:505)
    │
    ├─ 创建 TaskContext (传递给 callable)
    ├─ 调用 task callable (UseCase 定义的业务逻辑)
    │     - callable 内调用 ctx.progress(value) 更新进度
    │     - 每次 progress() 触发 SSE "progress" 事件
    │
    └─ 结果：
         - 成功: complete_task() → SSE "completed" 事件
         - 失败: fail_task() → SSE "failed" 事件
         - 超时: 超时监控线程取消 Future → SSE "failed" 事件

    ▼
前端 EventSource 收到 SSE 事件
    │
    ▼
useTaskStatus hook 更新本地状态
    │
    ▼
useVideoPageState 触发副作用 (刷新元数据、重新加载资源)
    │
    ▼
UI 更新 (进度条消失、toast 通知、刷新内容)
```

---

## 4. 持久化层

### Write-Through 模式

每次状态变更都同时写入内存和 SQLite (`infrastructure/workers/task_queue.py:295`):

```python
# 1. 更新内存（持有锁）
with self._lock:
    task.status = TaskStatus.READY
    task.updated_at = self._now_iso()
    snapshot = self._serialize_task(task)  # 捕获不可变快照

# 2. 持久化快照（锁外执行 I/O）
self._persist_snapshot(snapshot)

# 3. 广播事件
self._broadcast(content_id, {"event": "completed", "task": snapshot})
```

**为什么用快照 (Snapshot)？**
- 避免在持有锁时执行 I/O 操作（会阻塞其他线程）
- 持久化时操作的是不可变的 dict，不受并发修改影响
- 参考：`infrastructure/workers/task_queue.py:295-318`

### SQLite 配置

**WAL 模式** (`infrastructure/repositories/sqlite_task_storage.py:41`):
```sql
PRAGMA journal_mode=WAL
```
- 允许多线程并发读写
- 读不阻塞写，写不阻塞读
- 适合高频状态更新场景

**索引优化** (`infrastructure/repositories/sqlite_task_storage.py:55-56`):
```sql
CREATE INDEX idx_tasks_content_id ON tasks(content_id);
CREATE INDEX idx_tasks_status ON tasks(status);
```
- `content_id` 索引：加速 SSE 快照查询 (`list_by_content`)
- `status` 索引：加速启动协调查询 (`mark_inflight_as_error`)

### 启动协调 (Startup Reconciliation)

服务器重启时，将所有未完成的任务标记为错误 (`infrastructure/workers/task_queue.py:125-129`):

```python
affected = self._storage.mark_inflight_as_error(
    "Task interrupted by server restart"
)
# SQL: UPDATE tasks SET status='error' WHERE status IN ('pending','processing')
```

**为什么需要协调？**
- 服务器崩溃时，`PENDING` 和 `PROCESSING` 任务永远不会完成
- SSE 重连后客户端会收到这些"僵尸"任务的快照
- 协调将它们标记为 `ERROR`，避免 UI 永久显示"处理中"

### TTL 清理

定期清理过期的终态任务 (`infrastructure/workers/task_queue.py:362`):

```python
# 每 cleanup_interval_seconds 检查一次
# 删除 updated_at < (now - ttl_seconds) 的 READY/ERROR 任务
self._storage.delete_expired_terminal(ttl_seconds)
```

**目的**: 防止 tasks 表无限增长，保持查询性能。

---

## 5. SSE 实时推送层

### EventPublisher 架构

每个 `content_id` 对应一个事件通道，支持多个订阅者 (`presentation/sse/events.py:24`):

```
EventPublisher
    │
    ├─ _subscribers: dict[content_id, list[Queue]]
    │       │
    │       ├─ "video_abc123": [Queue1, Queue2, Queue3]  # 3 个浏览器标签页
    │       └─ "video_def456": [Queue4]
    │
    └─ broadcast(content_id, event_data)
           │ 遍历该 content_id 的所有订阅者队列
           └─ 非阻塞 put_nowait() 到每个 Queue
                  - 满了就移除（防止慢客户端拖垮系统）
```

### SSE 帧格式

标准 SSE 格式 (`presentation/sse/events.py:215`):

```
retry: 3000

id: 1
data: {"event":"connected","content_id":"video_abc"}

id: 2
data: {"event":"started","task":{...}}

id: 3
data: {"event":"progress","task":{"progress":50,...}}

: keepalive

id: 4
data: {"event":"completed","task":{"status":"ready",...}}
```

**字段说明**:
- `retry: 3000`: 告诉浏览器断线后 3 秒自动重连
- `id: N`: 事件序号（浏览器会在重连时发送 `Last-Event-ID` 头）
- `data: {...}`: JSON payload，包含 `event` 类型和 `task` 快照
- `: keepalive`: 注释行，30 秒无事件时发送（防止代理超时）

### Subscribe-Then-Snapshot 模式

避免竞态条件的关键设计 (`presentation/api/routes/task.py:69-72`):

```python
# 1. 先订阅（注册到 EventPublisher）
q = event_publisher.subscribe(content_id)

# 2. 再查询快照（调用 initial_events_factory）
tasks = task_manager.get_tasks_by_content(content_id)

# 3. 发送初始快照
for task in tasks:
    yield {"event": "initial", "task": task}

# 4. 开始流式推送新事件
while True:
    event = q.get(timeout=30)
    yield event
```

**为什么必须先订阅再查询？**

如果顺序反过来（先查询再订阅），会有竞态窗口：

```
时间线：
T1: 客户端查询快照 → 返回空列表 []
T2: 服务器完成任务 → 广播 "completed" 事件
T3: 客户端订阅通道 → 错过了 T2 的事件！

结果: 客户端永远不知道任务已完成
```

**Subscribe-Then-Snapshot 解决方案**:

```
T1: 客户端订阅通道
T2: 服务器完成任务 → 事件进入客户端队列 ✓
T3: 客户端查询快照 → 返回已完成的任务 ✓

结果: 客户端收到两次通知（快照 + 事件），但不会遗漏
```

前端会通过 `_eventType: "initial"` 区分快照和实时事件，避免重复通知 (`frontend/hooks/useVideoPageState.ts:294`)。

### 连接初始化流程

完整的 SSE 连接建立过程 (`presentation/sse/events.py:174`):

```
客户端 EventSource.connect()
    ▼
服务器 stream() 方法
    ├─ 1. 发送 retry: 3000 帧
    │     → 浏览器记住重连间隔
    │
    ├─ 2. 订阅通道
    │     → EventPublisher.subscribe(content_id) 返回 Queue
    │
    ├─ 3. 发送 connected 事件
    │     → id: 1, data: {"event":"connected",...}
    │
    ├─ 4. 调用 initial_events_factory()
    │     → 查询当前所有任务
    │     → 发送 id: 2,3,4... 快照事件
    │
    └─ 5. 进入事件循环
          while True:
              event = queue.get(timeout=30)  # 30 秒超时
              if timeout:
                  yield ": keepalive\n\n"   # 防止连接关闭
              else:
                  yield format_sse(event)   # 推送实时事件
```

---

## 6. 前端：任务监听与 UI 响应

### Hook 调用链

```
useVideoPageState (frontend/hooks/useVideoPageState.ts:173)
    │ 主状态容器：content, processing, timeline, voiceovers
    │
    ├─ useTaskStatus(videoId)
    │     │ SSE 连接与任务状态映射
    │     │ 返回: { tasks: Record<taskId, TaskStatus>, isConnected: boolean }
    │     └─ 内部：native EventSource + 自动重连
    │
    ├─ useTaskNotification()
    │     │ 通知系统：toast + title flash + browser notification
    │     └─ notifyTaskComplete(taskType, status, errorMessage)
    │
    └─ useVoiceoverManagement()
          │ voiceover 专属状态管理
          └─ 处理 voiceover_generation 任务
```

### useTaskStatus: SSE 连接

使用原生 `EventSource` API (`frontend/hooks/useTaskStatus.ts:45`):

```typescript
const eventSource = new EventSource(
    `${API_BASE_URL}/api/task/stream/${contentId}`
);

eventSource.onopen = () => {
    setIsConnected(true);
};

eventSource.onmessage = (event) => {
    const { event: eventType, task } = JSON.parse(event.data);
    setTasks(prev => ({
        ...prev,
        [task.task_id]: { ...task, _eventType: eventType }
    }));
};

eventSource.onerror = () => {
    setIsConnected(false);
    // 浏览器会根据 retry: 3000 自动重连，无需手动处理
};
```

**为什么用原生 EventSource 而不是手动 fetch？**
- 浏览器内置重连逻辑（遵循 `retry:` 帧）
- 自动处理 `Last-Event-ID`（服务器可用于断点续传）
- 更少的前端代码，更可靠的连接管理

### deriveProcessingState: UI 状态推导

单一数据源原则：从 `ContentMetadata` 推导 UI 状态 (`frontend/hooks/useVideoPageState.ts:71`):

```typescript
function deriveProcessingState(content: ContentItem | null) {
    if (content.subtitleStatus === "processing") {
        return { processing: true, action: "generate" };
    }
    if (content.translationStatus === "processing") {
        return { processing: true, action: "translate" };
    }
    if (content.videoStatus === "processing") {
        return { processing: true, action: "video" };
    }
    if (content.timelineStatus === "processing") {
        return { processing: true, action: "timeline", timelineLoading: true };
    }
    return { processing: false, action: null, timelineLoading: false };
}
```

**为什么从 content 推导而不是从 task 推导？**
- `ContentMetadata` 是持久化的业务状态，任务完成后会更新它
- 任务是瞬态的（TTL 清理后消失），content 状态是永久的
- 页面刷新后只能从 content 恢复 UI 状态（任务可能已被清理）

### 任务类型分类

**CONTENT_REFRESH_TASK_TYPES** (`frontend/hooks/useVideoPageState.ts:25`):

哪些任务完成后需要刷新 `ContentMetadata`：

```typescript
const CONTENT_REFRESH_TASK_TYPES = new Set([
    "subtitle_generation",     // 生成字幕 → subtitleStatus
    "subtitle_translation",    // 翻译字幕 → translationStatus
    "timeline_generation",     // 生成时间线 → timelineStatus
    "video_generation",        // 生成视频 → videoStatus
    "video_merge",             // 合并视频 → videoStatus
    "video_import_url",        // 导入视频 → videoStatus
    "pdf_merge",               // 合并 PDF → source_file
]);
```

**SUBTITLE_REFRESH_TASK_TYPES** (`frontend/hooks/useVideoPageState.ts:37`):

哪些任务需要强制刷新字幕（即使 status 仍是 `ready`）：

```typescript
const SUBTITLE_REFRESH_TASK_TYPES = new Set([
    "subtitle_generation",
    "subtitle_translation",
]);
```

**为什么需要 SUBTITLE_REFRESH_TASK_TYPES？**

解决 SSE 竞态 Bug：
1. 用户重新生成字幕（已经有 `subtitleStatus: "ready"`）
2. 后端完成任务，状态仍是 `ready`（没变化）
3. 前端 `subtitleStateKey` 不变 → UI 不刷新 → 显示旧字幕！

解决方案：任务完成时强制 bump `subtitleRefreshVersion`，即使状态未变 (`frontend/hooks/useVideoPageState.ts:306`)。

**TASK_TO_ACTION_MAP** (`frontend/hooks/useVideoPageState.ts:46`):

任务类型 → UI processingAction 映射：

```typescript
const TASK_TO_ACTION_MAP: Record<string, ProcessingAction> = {
    subtitle_generation: "generate",
    subtitle_translation: "translate",
    timeline_generation: "timeline",
    video_generation: "video",
    video_merge: "video",
    video_import_url: "video",
};
```

用途：判断任务完成时是否应该清除 `processing` 状态 (`frontend/hooks/useVideoPageState.ts:361`)。

### 通知系统

**useTaskNotification** (`frontend/hooks/useTaskNotification.ts:116`):

```typescript
notifyTaskComplete(taskType, status, errorMessage) {
    const labels = TASK_LABELS[normalizeTaskType(taskType)];

    // 1. Toast 通知（如果启用）
    if (settings.toastNotificationsEnabled) {
        toast.success(labels.success);  // 或 toast.error()
    }

    // 2. 标题闪烁（后台标签页）
    if (settings.titleFlashEnabled && document.hidden) {
        flashTitle(labels.success);
        // 标题每秒切换：✓ 字幕生成成功 <-> CourseSubtitle
    }

    // 3. 浏览器推送通知（后台标签页 + 已授权）
    if (settings.browserNotificationsEnabled && document.hidden) {
        new Notification("Task Complete", { body: labels.success });
    }
}
```

**为什么标题闪烁和浏览器通知只在后台标签页触发？**
- 用户正在看页面时，toast 通知已经足够
- 避免过度打扰（前台标签页不需要额外通知）
- `document.visibilityState === "hidden"` 检测标签页是否在后台

---

## 7. 完整数据流场景

以"生成字幕"为例，展示前后端完整交互：

```
═══════════════════════════════════════════════════════════════════════════════
                           用户点击 "Generate Subtitles"
═══════════════════════════════════════════════════════════════════════════════

前端 VideoActions.tsx
    │ 调用 generateSubtitles(videoId)
    ▼
POST /api/subtitle/generate
    │
    ▼
后端 Flask Route (presentation/api/routes/subtitle.py)
    │ 调用 GenerateSubtitleUseCase
    ▼
GenerateSubtitleUseCase (use_cases/subtitle.py)
    │
    ├─ 1. 更新 ContentMetadata
    │     metadata.subtitle_status = "processing"
    │     metadata.subtitle_job_id = task_id
    │     storage.save(metadata)
    │
    └─ 2. 提交任务
          task_id = task_manager.submit(
              content_id=video_id,
              task_type="subtitle_generation",
              task=lambda ctx: _generate_subtitle_impl(ctx, ...),
              timeout=1800,  # 30 分钟
          )

═══════════════════════════════════════════════════════════════════════════════
                              TaskManager.submit() 内部
═══════════════════════════════════════════════════════════════════════════════

TaskManager (infrastructure/workers/task_queue.py:131)
    │
    ├─ 1. 创建 Task 实体
    │     Task(
    │         id="subtitle_generation_video_abc_1234567890_a1b2c3d4",
    │         type="subtitle_generation",
    │         content_id="video_abc",
    │         status=PENDING,
    │         progress=0,
    │     )
    │
    ├─ 2. 内存存储
    │     self._tasks[task_id] = task
    │
    ├─ 3. SQLite 持久化
    │     INSERT OR REPLACE INTO tasks (...) VALUES (...)
    │
    ├─ 4. 队列入队
    │     self._queue.put_nowait(item)
    │
    └─ 5. SSE 广播
          event_publisher.broadcast(content_id, {
              "event": "started",
              "task": { "id": task_id, "status": "pending", ... }
          })

═══════════════════════════════════════════════════════════════════════════════
                           前端收到 SSE "started" 事件
═══════════════════════════════════════════════════════════════════════════════

EventSource.onmessage
    ▼
useTaskStatus.setTasks({ [task_id]: task })
    ▼
useVideoPageState.useEffect([tasks])
    │ 检测到新任务 status="pending"
    └─ （暂无操作，等待 PROCESSING）

═══════════════════════════════════════════════════════════════════════════════
                          WorkerPool 执行任务（后端后台）
═══════════════════════════════════════════════════════════════════════════════

WorkerPool._consume_loop()
    │ 从队列取出任务
    ▼
ThreadPoolExecutor.submit(_execute_task, item)
    │
    ▼
_execute_task()
    │
    ├─ 1. 创建 TaskContext
    │     ctx = TaskContext(task_id, content_id, "subtitle_generation", manager)
    │
    ├─ 2. 自动标记为 PROCESSING
    │     manager.update_task_progress(task_id, 1, emit_event=False)
    │     SQL: UPDATE tasks SET status='processing', progress=1
    │     （不触发 SSE，减少网络开销）
    │
    ├─ 3. 执行业务逻辑
    │     item.callable(ctx)  # UseCase 定义的实现函数
    │       │
    │       ├─ 提取音频: ffmpeg -i video.mp4 audio.wav
    │       │   ctx.progress(20)  → SSE "progress" 事件 (progress=20)
    │       │
    │       ├─ Whisper 转录
    │       │   ctx.progress(50)  → SSE "progress" 事件 (progress=50)
    │       │
    │       ├─ 保存 SRT 文件
    │       │   ctx.progress(80)  → SSE "progress" 事件 (progress=80)
    │       │
    │       └─ 返回（无异常）
    │
    ├─ 4. 标记完成
    │     manager.complete_task(task_id)
    │       ├─ 内存: task.status = READY, task.progress = 100
    │       ├─ SQLite: UPDATE tasks SET status='ready', progress=100
    │       └─ SSE 广播: {"event": "completed", "task": {...}}
    │
    └─ 5. 通知队列
          queue.task_done()

═══════════════════════════════════════════════════════════════════════════════
                       前端收到 SSE "progress" 事件（多次）
═══════════════════════════════════════════════════════════════════════════════

EventSource.onmessage (progress=20, 50, 80)
    ▼
useTaskStatus.setTasks({ [task_id]: { ...task, progress: 50 } })
    ▼
VideoActions Progress Bar
    <Progress value={50} />  → UI 显示 50% 进度条

═══════════════════════════════════════════════════════════════════════════════
                       前端收到 SSE "completed" 事件
═══════════════════════════════════════════════════════════════════════════════

EventSource.onmessage
    │ data: {"event":"completed","task":{"status":"ready",...}}
    ▼
useTaskStatus.setTasks({ [task_id]: { status: "ready", progress: 100 } })
    ▼
useVideoPageState.useEffect([tasks])
    │
    ├─ 1. 检查任务是否已处理
    │     if (handledTasksRef.current.has(task_id)) return;  // 防止重复处理
    │     handledTasksRef.current.add(task_id);
    │
    ├─ 2. 发送通知（仅实时事件，非初始快照）
    │     if (task._eventType !== "initial") {
    │         notifyTaskComplete("subtitle_generation", "ready");
    │         // Toast: ✓ Subtitles generated successfully
    │         // Title: ✓ 字幕生成成功 (闪烁 30 秒)
    │         // Browser: new Notification("Task Complete", ...)
    │     }
    │
    ├─ 3. 刷新 ContentMetadata（因为在 CONTENT_REFRESH_TASK_TYPES 中）
    │     const newContent = await getContentMetadata(videoId);
    │     setContent(newContent);
    │     // 现在 content.subtitleStatus = "ready"
    │
    ├─ 4. Bump subtitleRefreshVersion（强制字幕组件重新加载）
    │     setSubtitleRefreshVersion(v => v + 1);
    │     // SubtitlePanel useEffect([subtitleRefreshVersion]) 触发
    │
    ├─ 5. 清除 processingAction
    │     if (TASK_TO_ACTION_MAP[task.type] === processingAction) {
    │         setProcessing(false);
    │         setProcessingAction(null);
    │     }
    │
    └─ 6. UI 更新
          - 进度条消失
          - "Generate Subtitles" 按钮恢复可点击
          - 字幕面板加载新字幕文件
          - Toast 通知显示成功消息

═══════════════════════════════════════════════════════════════════════════════
                              数据流完成
═══════════════════════════════════════════════════════════════════════════════
```

---

## 8. 异常场景状态转换

| 场景 | 后端行为 | 前端行为 | 涉及文件 |
|------|---------|---------|---------|
| **任务执行正常** | `pending → processing → ready` | 进度条更新 → 成功通知 → 刷新内容 | `task_queue.py:244` |
| **任务执行报错** | `pending → processing → error` (捕获异常) | 进度条消失 → 错误 toast + 错误描述 | `task_queue.py:524` |
| **队列满** | `pending → error` (立即失败) | 错误 toast: "Task queue is full" | `task_queue.py:193` |
| **Worker 超时** | `processing → error` (超时监控线程) | 错误 toast: "Task timed out after Xs" | `task_queue.py:494` |
| **服务器重启** | `pending/processing → error` (启动协调) | SSE 重连 → 收到初始快照 → 看到 error 状态 → 错误通知 | `task_queue.py:127` |
| **SSE 断线（短时）** | 无影响（任务继续执行） | `isConnected=false` → 浏览器 3 秒后自动重连 → 收到快照恢复 | `useTaskStatus.ts:74` |
| **SSE 长时间断线** | 任务可能已完成并清理（TTL） | 重连后初始快照包含最新状态（或已被清理，从 content 状态恢复） | `events.py:189` |
| **浏览器标签不可见** | 无影响 | 任务完成时：标题闪烁 + 浏览器推送通知（不发 toast） | `useTaskNotification.ts:74` |
| **任务已终态时再次更新** | 检查 `is_terminal()` → 忽略更新请求 | 无影响（不会收到事件） | `task_queue.py:224` |
| **持久化失败** | 记录日志，任务继续执行（内存状态仍有效） | SSE 正常推送，UI 正常更新（但重启后会丢失） | `task_queue.py:295` |
| **SSE 订阅队列满** | 移除该订阅者（防止拖垮系统） | 连接断开 → 浏览器重连 → 恢复订阅 | `events.py:88` |
| **客户端手动断开** | `GeneratorExit` 异常 → 自动清理订阅 | EventSource.close() → 无事件接收 | `events.py:208` |

**关键错误处理路径**:

1. **异常捕获** (`task_queue.py:520-526`):
```python
try:
    item.callable(ctx)
    self._manager.complete_task(item.task_id)
except Exception as exc:
    logger.error("Task %s failed: %s", item.task_id, exc, exc_info=True)
    self._manager.fail_task(item.task_id, str(exc))
```

2. **超时监控** (`task_queue.py:478-500`):
```python
# 单独线程每秒检查所有 pending futures
for task_id, (future, deadline, item) in self._pending_futures.items():
    if time.monotonic() >= deadline and not future.done():
        future.cancel()
        self._manager.fail_task(task_id, f"Task timed out after {timeout}s")
```

3. **队列满保护** (`task_queue.py:190-194`):
```python
try:
    self._queue.put_nowait(item)
except queue.Full:
    self._fail_task_internal(task_id, "Task queue is full")
    raise RuntimeError(...)
```

---

## 9. 设计决策

### 为什么用 Write-Through 而不是 Event Sourcing？

**Event Sourcing** (事件溯源):
- 存储所有状态变更事件: `[TaskCreated, ProgressUpdated(20), ProgressUpdated(50), TaskCompleted]`
- 通过重放事件重建当前状态
- 优点: 完整历史、时间旅行、审计追踪
- 缺点: 查询当前状态需要聚合事件，复杂度高

**Write-Through** (直写):
- 每次状态变更直接写入最新快照
- SQLite 只存储当前状态，不存储历史
- 优点: 查询快（直接 SELECT），实现简单
- 缺点: 无历史记录

**DeepLecture 选择 Write-Through 的原因**:
1. **查询模式简单**: SSE 快照只需当前状态，不需要历史
2. **状态转换简单**: 只有 4 种状态，无复杂业务规则
3. **无时间查询**: 不需要"查找 1 小时前的任务状态"
4. **教育平台特性**: 任务量不大，无需复杂的事件分析

参考：`infrastructure/workers/task_queue.py:295`

### 为什么用 ThreadPoolExecutor 而不是 Celery/RQ？

**Celery/RQ** (分布式任务队列):
- 需要 Redis/RabbitMQ 作为 broker
- 支持多机分布式执行、任务优先级、结果持久化
- 适合高并发、大规模后台任务场景

**ThreadPoolExecutor** (本地线程池):
- Python 标准库，无外部依赖
- 适合单机应用，任务量适中
- 配置简单，易于调试

**DeepLecture 选择 ThreadPoolExecutor 的原因**:
1. **单机部署**: 教育平台，不需要分布式
2. **任务量适中**: 每个视频生成一次字幕，不是高频操作
3. **降低复杂度**: 避免引入额外的基础设施（Redis）
4. **本地开发友好**: 无需配置外部服务即可运行

参考：`infrastructure/workers/task_queue.py:394`

### 为什么用原生 EventSource 重连而不是手动 Retry？

**手动 Retry** (fetch + 轮询重连):
```typescript
async function connectSSE() {
    while (true) {
        try {
            const response = await fetch("/api/stream");
            const reader = response.body.getReader();
            // 读取流...
        } catch {
            await sleep(3000);  // 手动等待 3 秒
        }
    }
}
```

**原生 EventSource** (浏览器内置):
```typescript
const es = new EventSource("/api/stream");
es.onerror = () => {
    // 浏览器根据 retry: 3000 自动重连
};
```

**DeepLecture 选择原生 EventSource 的原因**:
1. **浏览器优化**: 原生实现更高效、更可靠
2. **协议标准**: 自动处理 `retry:` 帧、`Last-Event-ID` 头
3. **更少代码**: 前端无需实现重连逻辑
4. **连接管理**: 浏览器自动处理网络切换、休眠恢复

参考：`frontend/hooks/useTaskStatus.ts:45`

### 为什么用 Snapshot-Based Persistence？

**Lock-Held Persistence** (持锁期间持久化):
```python
with self._lock:
    task.status = READY
    self._storage.save(task)  # I/O 操作在锁内！
```
- 问题：SQLite 写入可能需要几毫秒，阻塞其他线程

**Snapshot-Based Persistence** (快照持久化):
```python
with self._lock:
    task.status = READY
    snapshot = dict(task)  # 捕获快照

# 锁外持久化
self._storage.save(snapshot)
```
- 优点：锁只持有微秒级（拷贝内存），I/O 在锁外执行

**DeepLecture 的实现**:
- 每次状态变更在锁内生成不可变快照 (`_serialize_task`)
- 持久化操作在锁外执行，操作快照而非活动对象
- 线程安全：快照是 dict，不受并发修改影响

参考：`infrastructure/workers/task_queue.py:232, 295-318`

---

## 总结

DeepLecture 的任务系统是一个**线性状态机 + SSE 推送 + 双向协调**的架构：

1. **后端**: ThreadPoolExecutor + SQLite WAL，Write-Through 持久化
2. **实时通信**: SSE 长连接，Subscribe-Then-Snapshot 避免竞态
3. **前端**: 原生 EventSource 自动重连，从 ContentMetadata 推导 UI 状态
4. **容错**: 启动协调、TTL 清理、超时监控、断线重连

设计原则：
- **简单优于复杂**: ThreadPool 而非 Celery，Write-Through 而非 Event Sourcing
- **标准优于自制**: 原生 EventSource 而非手动轮询
- **协调优于假设**: Subscribe-Then-Snapshot 而非查询-订阅

适用场景：
- ✅ 单机部署的 Web 应用
- ✅ 任务量适中（每用户每天几十个任务）
- ✅ 需要实时进度反馈
- ❌ 不适合分布式高并发场景（考虑 Celery + Redis）
- ❌ 不适合需要完整历史追溯（考虑 Event Sourcing）
