# Frontend

DeepLecture 的前端基于 Next.js。

## 启动方式

正常本地使用时，请在仓库根目录执行：

```bash
npm start
```

这个命令会自动完成依赖准备，并启动：

- 后端 API：`http://localhost:11393`
- 前端 dev server：`http://localhost:3001`

大多数情况下，不需要在 `frontend/` 目录里再手动跑一次 `npm run dev`。

## 仅前端开发

如果你只是在单独迭代前端界面，可以在本目录执行：

```bash
npm install
npm run dev
```

然后访问 [http://localhost:3001](http://localhost:3001)。

## Task Stream Reconnect

Frontend task state is driven by SSE (`useTaskStatus` → `EventSource`):

1. **Connect**: `EventSource` opens `/api/task/stream/{contentId}`
2. **Snapshot**: Server sends `retry: 3000` + `initial` events for all active tasks
3. **Live**: Real-time `started`/`progress`/`completed`/`failed` events
4. **Reconnect**: On disconnect, browser auto-reconnects per `retry:` interval; new snapshot is sent
5. **Fallback**: Metadata polling only runs when SSE is disconnected (`isConnected === false`)

Task type normalization and mapping logic is in `lib/taskTypes.ts`.
