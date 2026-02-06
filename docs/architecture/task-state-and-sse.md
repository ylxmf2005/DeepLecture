# 架构决策：任务状态持久化 + SSE 传输

## 背景

TaskManager 使用内存 `dict` 存储任务状态。后端重启后所有任务信息丢失，前端 UI 会卡在 "processing" 状态。SSE 流缺少 `id:` 和 `retry:` 字段，浏览器无法优雅地自动重连。

## 决策

### 1. SQLite 任务状态表（非事件日志）

使用单表 `tasks` 持久化**当前状态快照**，不做事件溯源。

理由：
- 同一时间每个 content 最多 0-3 个活跃任务，快照开销可忽略
- 不需要审计/历史回放，只需"这个任务还在跑吗？"
- 与现有 `sqlite_metadata.py` 模式一致

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_content_id ON tasks(content_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
```

### 2. 写穿透（Write-Through）持久化

TaskManager 在每次状态转换时同步写入 SQLite：
- `submit()` → INSERT
- `update_task_progress()` → UPDATE（仅在状态从 pending→processing 转换时写入；纯进度更新不持久化）
- `complete_task()` / `fail_task()` → UPDATE

内存 `dict` 仍是运行时热缓存，SQLite 是持久化层。

### 3. 启动修复（Startup Reconciliation）

服务启动时，将所有 `pending`/`processing` 状态的任务标记为 `error`：

```sql
UPDATE tasks SET status = 'error', error = '...', updated_at = '...'
WHERE status IN ('pending', 'processing');
```

这些任务不可能恢复（线程池已销毁），标记为 error 让前端正确显示失败状态。

### 4. SSE `id:` + `retry:` 帧

- `id:` 使用内存单调递增计数器（`itertools.count()`），非数据库 ID
- `retry: 3000` 在连接建立时发送一次
- 不依赖 `Last-Event-ID` 回放，重连时发送完整快照

### 5. 连接时修复（Reconciliation on SSE Connect）

SSE 流端点在发送快照前执行 `_reconcile_stale_processing()`，确保客户端拿到的快照反映真实状态。

## 替代方案（已排除）

| 方案 | 排除原因 |
|------|---------|
| 事件溯源 (Event Log) | 过度设计；不需要回放/审计 |
| `Last-Event-ID` 回放 | 代理可能丢弃 header；快照已足够 |
| 任务类型注册表 + JSON endpoint | 静态数据用 dict 即可 |
| 前端大规模重写 (`useTaskOrchestrator`) | 风险高；增量修改即可 |

## 影响

- **性能**：启用 WAL 模式减少写竞争；进度更新节流
- **一致性**：SQLite 为规范来源；内存 dict 为运行时缓存
- **前端**：可安全移除 connected-mode 轮询，仅保留 disconnected fallback
