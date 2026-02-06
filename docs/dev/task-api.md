# Task API

Task API 用于管理异步后台任务的状态查询和实时事件流。

## 任务类型

后端支持以下 13 种任务类型：

| 任务类型 | 说明 | 关联状态字段 |
|---------|------|-------------|
| `subtitle_generation` | 字幕生成 (ASR) | `subtitle_status` |
| `subtitle_translation` | 字幕翻译/增强 | `enhance_translate_status` |
| `timeline_generation` | 时间线生成 | `timeline_status` |
| `video_generation` | 视频生成 (slide lecture) | `video_status` |
| `video_import_url` | URL 视频导入 | `video_status` |
| `video_merge` | 视频合并 | `video_status` |
| `pdf_merge` | PDF 合并 | - |
| `voiceover_generation` | 语音合成 | - |
| `slide_explanation` | 幻灯片解释 | - |
| `fact_verification` | 事实核查 | - |
| `cheatsheet_generation` | 知识速查生成 | - |
| `note_generation` | 笔记生成 | `notes_status` |
| `quiz_generation` | 测验生成 | - |

## 任务状态

```
PENDING -> PROCESSING -> READY
                     \-> ERROR
```

| 状态 | 说明 | 是否终态 |
|------|------|---------|
| `pending` | 已入队，等待执行 | 否 |
| `processing` | 正在执行 | 否 |
| `ready` | 执行成功 | 是 |
| `error` | 执行失败 | 是 |

## REST 端点

### GET /api/task/{task_id}

获取单个任务状态。

**响应：**
```json
{
  "id": "subtitle_generation_abc123_1706000000_a1b2c3d4",
  "type": "subtitle_generation",
  "content_id": "abc123",
  "status": "processing",
  "progress": 42,
  "error": null,
  "result": null,
  "metadata": {},
  "created_at": "2025-01-23T10:00:00Z",
  "updated_at": "2025-01-23T10:00:05Z"
}
```

### GET /api/task/content/{content_id}

获取某内容的所有任务。

**响应：**
```json
{
  "content_id": "abc123",
  "tasks": [/* task objects */],
  "count": 2
}
```

## SSE 流端点

### GET /api/task/stream/{content_id}

建立 Server-Sent Events 连接，实时接收任务事件。

**响应头：**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**SSE 帧格式：**

连接后首先发送 `retry:` 帧（告知浏览器重连间隔），然后发送当前所有任务的快照，最后持续推送实时事件：

```
retry: 3000

id: 1
data: {"event":"initial","task":{...}}

id: 2
data: {"event":"initial","task":{...}}

id: 3
data: {"event":"progress","task":{...}}

id: 4
data: {"event":"completed","task":{...}}
```

**SSE 字段说明：**

| 字段 | 说明 |
|------|------|
| `id:` | 单调递增事件 ID，用于浏览器 `Last-Event-ID` 重连 |
| `retry:` | 重连间隔（毫秒），仅在连接建立时发送一次 |
| `data:` | JSON 负载，包含 `event` 类型和 `task` 对象 |

**事件类型：**

| 事件 | 触发时机 |
|------|---------|
| `initial` | 连接建立时的任务快照 |
| `started` | 新任务入队 |
| `progress` | 任务进度更新 |
| `completed` | 任务成功完成 |
| `failed` | 任务执行失败 |

**心跳：**

每 30 秒发送 SSE 注释作为心跳，防止代理/防火墙关闭空闲连接：
```
: keepalive
```

连续 60 次心跳无事件后，服务端主动关闭连接，客户端应自动重连。

## 重连行为

1. 浏览器 `EventSource` 根据 `retry:` 字段自动重连
2. 每次重连都会收到完整的任务快照（`initial` 事件）
3. 快照在订阅后发送（subscribe-then-snapshot 模式），保证不丢失事件
4. 重连时服务端执行陈旧任务修复（reconciliation）
