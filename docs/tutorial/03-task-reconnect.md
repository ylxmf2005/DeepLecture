# 教程：验证任务重连正确性

本教程帮助开发者验证任务状态在后端重启和 SSE 重连后的正确恢复行为。

## 前提条件

- 后端运行在开发模式
- 前端运行在 `localhost:3000`
- 浏览器开发者工具已打开

## 测试 1：后端重启恢复

1. 上传一个视频/PDF，触发 `subtitle_generation`
2. 在任务进行中（进度 < 100%），终止后端进程：`Ctrl+C`
3. 重新启动后端：`uv run python -m deeplecture`
4. 观察浏览器：
   - SSE 自动重连（Network 面板可见新的 `stream/` 请求）
   - 任务状态从 "processing" 变为 "error"
   - 用户可重新触发该任务

**预期结果**：不会出现永久卡在 "processing" 的情况。

## 测试 2：SSE 重连快照

1. 触发任意长时间任务（如 `timeline_generation`）
2. 在 Network 面板中找到 `stream/{content_id}` 请求
3. 右键 → Block request URL
4. 等待 2-3 秒，取消屏蔽
5. 观察新的 SSE 连接：
   - 第一帧应为 `retry: 3000`
   - 后续帧为 `initial` 事件（任务快照）
   - 每帧包含 `id:` 字段

**预期结果**：重连后任务状态与实际一致。

## 测试 3：SSE 帧格式验证

在 Network 面板中查看 EventStream：

```
retry: 3000

id: 1
data: {"event":"initial","task":{"id":"...","status":"processing","progress":42,...}}

id: 2
data: {"event":"progress","task":{"id":"...","status":"processing","progress":55,...}}
```

验证：
- [x] `retry:` 仅出现一次（连接建立时）
- [x] 每个 `data:` 帧都有对应的 `id:` 行
- [x] `id:` 值单调递增
- [x] 心跳为 `: keepalive` 注释（无 `id:`）
