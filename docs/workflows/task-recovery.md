# 工作流：任务恢复（重启与重连）

## 场景 1：后端重启

```text
时间线：
  T0  用户发起 subtitle_generation，任务状态 = processing
  T1  后端进程被终止（SIGTERM / 崩溃）
  T2  后端重新启动
  T3  用户刷新页面或 SSE 自动重连
```

**恢复流程：**

1. **T2 - 启动修复**：`SQLiteTaskStorage.mark_inflight_as_error()` 将所有 `pending`/`processing` 任务标记为 `error`
2. **T3 - SSE 重连**：前端 EventSource 检测到连接断开，根据 `retry:` 值自动重连
3. **T3 - 快照发送**：SSE 端点先执行 content metadata 修复，再发送任务快照
4. **T3 - 前端更新**：前端收到 `initial` 事件，任务状态从 "processing" 更新为 "error"

**用户体验**：进度条消失，显示错误提示，用户可重新触发任务。

## 场景 2：SSE 连接中断（网络抖动）

```text
时间线：
  T0  SSE 连接正常，任务 processing 中
  T1  网络中断，SSE 断开
  T2  网络恢复，EventSource 自动重连（延迟由 retry: 控制）
  T3  收到新的任务快照
```

**恢复流程：**

1. **T1**：前端 `useTaskStatus` 检测 `onerror`，标记 `isConnected = false`
2. **T2**：EventSource 自动重连（浏览器原生行为）
3. **T3**：连接建立后收到完整任务快照，前端状态收敛到正确值

**用户体验**：可能出现短暂状态过期（秒级），重连后自动恢复。

## 场景 3：长时间断线

如果 SSE 连续 60 次心跳（30分钟）无事件，服务端关闭连接。前端保留 disconnected fallback 轮询确保最终一致性。

## 修复逻辑位置

| 修复类型 | 触发时机 | 代码位置 |
|---------|---------|---------|
| 启动修复 | 进程启动 | `SQLiteTaskStorage.mark_inflight_as_error()` |
| 内容元数据修复 | REST 读取 / SSE 连接 | `content.py:_reconcile_stale_processing()` |
| TTL 清理 | 定期检查 | `TaskManager._cleanup_expired_tasks()` + `SQLiteTaskStorage.delete_expired_terminal()` |
