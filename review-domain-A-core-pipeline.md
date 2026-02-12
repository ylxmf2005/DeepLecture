# Domain A: Core Pipeline Review

## 审查范围

### 后端用例层
- `src/deeplecture/use_cases/upload.py` — Upload use case (video/PDF upload, URL import, merge)
- `src/deeplecture/use_cases/timeline.py` — Timeline generation use case
- `src/deeplecture/use_cases/subtitle.py` — Subtitle generation, enhancement, translation
- `src/deeplecture/use_cases/voiceover.py` — Voiceover generation (TTS + A/V sync)
- `src/deeplecture/use_cases/slide_lecture.py` — Slide lecture generation

### 后端 DTO 层
- `src/deeplecture/use_cases/dto/voiceover.py` — Voiceover DTOs
- `src/deeplecture/use_cases/dto/subtitle.py` — Subtitle DTOs

### 后端 API 路由层
- `src/deeplecture/presentation/api/routes/upload.py` — Upload routes
- `src/deeplecture/presentation/api/routes/timeline.py` — Timeline routes
- `src/deeplecture/presentation/api/routes/subtitle.py` — Subtitle routes
- `src/deeplecture/presentation/api/routes/voiceover.py` — Voiceover routes
- `src/deeplecture/presentation/api/routes/generation.py` — Slide video generation routes

### 后端共享层
- `src/deeplecture/presentation/api/shared/errors.py` — Error handling
- `src/deeplecture/presentation/api/shared/response.py` — Response envelope

### 前端 API 层
- `frontend/lib/api/client.ts` — Axios client with interceptors
- `frontend/lib/api/transform.ts` — snake_case ↔ camelCase transforms
- `frontend/lib/api/content.ts` — Content/upload API functions
- `frontend/lib/api/subtitle.ts` — Subtitle API functions
- `frontend/lib/api/voiceover.ts` — Voiceover API functions

### 前端组件/Hooks
- `frontend/components/video/VideoUpload.tsx` + `upload/` 子组件
- `frontend/components/content/SubtitleList.tsx`
- `frontend/components/content/TimelineList.tsx`
- `frontend/hooks/useSubtitleManagement.ts`
- `frontend/hooks/useVoiceoverManagement.ts`
- `frontend/hooks/useVoiceoverSync.ts`
- `frontend/hooks/handlers/useSubtitleHandlers.ts`
- `frontend/hooks/handlers/useTimelineHandlers.ts`
- `frontend/hooks/handlers/useVoiceoverHandlers.ts`
- `frontend/hooks/handlers/useSlideHandlers.ts`
- `frontend/stores/uploadQueueStore.ts`

---

## 发现列表

### [Warning] Voiceover 生成：前端发送 `subtitle_source` 字段但后端完全忽略
- **位置**:
  - Frontend: `frontend/lib/api/voiceover.ts:20-24`
  - Backend: `src/deeplecture/presentation/api/routes/voiceover.py:54-96`
- **问题**: 前端 `generateVoiceover()` 构造了 `subtitle_source` 对象 (`{ type: "transcript" | "translation", language }`) 并发送到后端，但后端路由 `generate_voiceover()` 完全不读取 `subtitle_source`，只读取顶层的 `voiceover_name` 和 `language`。后端将 `language` 同时赋值给 `GenerateVoiceoverRequest.language` 和 `subtitle_language`。
- **影响**:
  1. **功能层面**：目前不会出错，因为 `language` 参数已经携带了正确的语言信息。但如果前端想通过 `subtitle_source.type` 区分 "用原始字幕" 和 "用翻译字幕" 生成 TTS，这个意图无法传达到后端。后端的 `VoiceoverUseCase._load_subtitle_segments()` 会按 fallback 顺序（enhanced → base）加载指定语言的字幕。
  2. **HCI 层面**：如果用户选择"用翻译字幕生成配音"，实际使用的字幕取决于 `language` 参数和 fallback 逻辑，而非显式的 `subtitle_source` 选择。
- **建议**: 如果 `subtitle_source` 不需要，应从前端移除死代码。如果需要区分 original/translation，后端应解析并使用该字段。

### [Warning] Voiceover 生成失败时无用户可见的错误提示
- **位置**: `frontend/hooks/handlers/useVoiceoverHandlers.ts:56-58`
- **问题**: `handleGenerateVoiceover` 的 catch 块仅调用 `log.error()` 和 `setVoiceoverProcessing(null)` — 没有 toast 通知。用户只能看到 processing 状态消失，但不知道为什么配音没有生成。相比之下，voiceover 的 rename 操作有 `toast.error("Failed to rename voiceover")`。
- **影响**: 用户操作流程中的静默失败。如果 TTS 服务不可用或字幕为空，用户只会看到按钮恢复可点击状态，没有任何反馈。
- **建议**: 添加 `toast.error("Failed to generate voiceover")` 或更具体的错误消息。

### [Warning] Voiceover 删除失败时无用户可见的错误提示
- **位置**: `frontend/hooks/handlers/useVoiceoverHandlers.ts:73-75`
- **问题**: `handleDeleteVoiceover` 的 catch 块同样只记日志，不通知用户。
- **影响**: 删除操作静默失败，用户可能认为已删除但实际并未删除。
- **建议**: 添加 `toast.error("Failed to delete voiceover")`。

### [Warning] Timeline 生成失败时无用户可见的错误提示
- **位置**: `frontend/hooks/handlers/useTimelineHandlers.ts` (基于 Explore agent 报告)
- **问题**: Timeline 生成失败时，错误只记日志，不显示 toast。处理状态被清除但用户不知道失败原因。
- **影响**: LLM 调用失败（如 API key 过期、配额耗尽）时，用户看到 processing 动画消失，但没有任何提示。
- **建议**: 添加 toast 错误通知，使其与 subtitle 生成的 toast 行为一致。

### [Warning] Subtitle 生成失败时前端 handler 无 toast 通知
- **位置**: `frontend/hooks/handlers/useSubtitleHandlers.ts` (基于 Explore agent 报告)
- **问题**: 虽然 `useSubtitleManagement` hook 加载字幕失败时有 `toast.error("Failed to load subtitles")`，但 `useSubtitleHandlers` 中触发生成/翻译的 handler 失败时只记日志，不显示 toast。
- **影响**: 用户点击"生成字幕"或"翻译"后，如果 ASR 服务或 LLM 不可用，不会收到错误反馈。
- **建议**: 在 handler 的 catch 块中添加 toast 通知。

### [Info] 前后端错误提示风格不一致
- **位置**: 整个前端 hooks/handlers 目录
- **问题**: 错误通知行为不统一：
  | 操作 | 有 Toast | 无 Toast (静默) |
  |------|----------|----------------|
  | 加载字幕 | ✅ (useSubtitleManagement) | |
  | 生成字幕 | | ❌ (useSubtitleHandlers) |
  | 翻译字幕 | | ❌ (useSubtitleHandlers) |
  | 生成 Timeline | | ❌ (useTimelineHandlers) |
  | 生成 Voiceover | | ❌ (useVoiceoverHandlers) |
  | 删除 Voiceover | | ❌ (useVoiceoverHandlers) |
  | 重命名 Voiceover | ✅ (toast.error + toast.success) | |
  | 上传文件 | ✅ (inline error banner) | |
- **影响**: 用户体验不一致。部分操作失败有反馈，部分静默。
- **建议**: 统一所有用户触发的操作（generate、delete、translate）都应有 toast 错误提示。

### [Info] Upload 流程中的 allowed video extensions 前后端不完全一致
- **位置**:
  - Backend: `src/deeplecture/use_cases/upload.py:64` → `{".mp4", ".mov", ".avi", ".mkv", ".webm"}`
  - Backend route: `src/deeplecture/presentation/api/routes/upload.py:41` → `{".mp4", ".mov", ".mkv", ".webm", ".avi"}`
  - Frontend: `frontend/components/video/upload/constants.ts` → `["mp4", "webm", "mov"]`
- **问题**: 后端支持 `.avi` 和 `.mkv`，但前端的文件选择器只允许 `.mp4`, `.webm`, `.mov`。前端 MIME 类型过滤也不包含 `video/x-msvideo` (avi) 和 `video/x-matroska` (mkv)。
- **影响**: 用户无法通过前端 UI 上传 `.avi` 和 `.mkv` 文件，虽然后端支持。这不是 bug（前端有意限制），但可能限制了用户需求。
- **建议**: 确认这是有意为之（前端只显示最常用格式）。如果需要支持 avi/mkv，更新前端 constants。

### [Info] Voiceover 路由将 `language` 同时作为 TTS 语言和字幕语言
- **位置**: `src/deeplecture/presentation/api/routes/voiceover.py:88-96`
- **问题**: `GenerateVoiceoverRequest` 的 `language` 和 `subtitle_language` 被设置为相同的值 (`language`)。这意味着 TTS 语言和字幕来源语言总是相同的。
- **影响**: 如果用户想用英文字幕但中文 TTS 语音，当前架构不支持。但这可能是设计上的合理简化。
- **建议**: 目前可接受，但如果未来需要跨语言 TTS，需要拆分这两个参数。

### [Info] Upload 路由的 `_serialize_upload_result` 使用了 duck typing
- **位置**: `src/deeplecture/presentation/api/routes/upload.py:172-179`
- **问题**: `_serialize_upload_result(result: object)` 接收 `object` 类型并直接访问 `.content_id` 等属性。虽然在 `UploadResult` 和 `ImportJobResult` 上都能工作（因为它们有相同的属性），但 `ImportJobResult` 有额外的 `status` 和 `job_id` 字段被丢弃。
- **影响**: 当 merge 操作异步执行时，返回的 `ImportJobResult` 的 `status` 和 `job_id` 被 `_serialize_upload_result` 静默丢弃。前端无法得到 task_id 来轮询状态。
- **建议**: 为 `ImportJobResult` 使用单独的序列化器，包含 `status` 和 `task_id` 字段。或者像 `import_from_url` 路由那样显式序列化。

### [Warning] 异步 merge (video/PDF) 返回的 response 丢失了 task_id
- **位置**: `src/deeplecture/presentation/api/routes/upload.py:69-71`
- **问题**: 当上传多个视频文件时，`merge_videos` 以 `async_mode=True` 调用，返回 `ImportJobResult`。但 `_serialize_upload_result` 只序列化 `content_id`, `filename`, `content_type`, `message`，**丢掉了 `job_id` (task_id) 和 `status`**。
- **影响**: 前端无法追踪异步 merge 操作的进度。没有 task_id，就无法通过 SSE 或轮询获取合并状态。用户上传多个视频后，可能看到一个 content_id 但内容实际还在处理中。
- **建议**: 检测 `result` 是否为 `ImportJobResult`，如果是，使用包含 `task_id` 和 `status` 的序列化格式（类似 `import_from_url` 的返回）。

### [Info] Timeline 使用 SubtitleGenerationError 而非专用错误类型
- **位置**: `src/deeplecture/use_cases/timeline.py:192`
- **问题**: Timeline 生成失败时抛出 `SubtitleGenerationError`，但 timeline 并不是 subtitle。这映射到 HTTP 500 (`SUBTITLE_GENERATION_FAILED`)。
- **影响**: 错误消息可能混淆日志分析。前端收到的错误码是 `SUBTITLE_GENERATION_FAILED`，但实际是 timeline 错误。
- **建议**: 考虑创建 `TimelineGenerationError` 或使用更通用的错误类型。

### [Info] Subtitle enhance_and_translate 的 enhanced 语言 key 硬编码
- **位置**: `src/deeplecture/use_cases/subtitle.py:168-169`
- **问题**: Enhanced 字幕保存为 `{source_language}_enhanced` 格式。这是一个约定而非显式配置。
- **影响**: 如果语言代码本身包含 `_enhanced`（极不可能），会导致冲突。更重要的是，前端也必须知道这个约定才能正确加载 enhanced 字幕。
- **建议**: 当前可接受，保持一致即可。

### [Info] SRT → VTT 转换中硬编码 `line:85%` 定位
- **位置**: `src/deeplecture/use_cases/subtitle.py:410`
- **问题**: `convert_srt_to_vtt` 在每个时间戳行末尾添加 `line:85%`，将字幕定位在画面底部 85% 处。
- **影响**: 如果前端使用自定义字幕渲染（而非原生 `<track>` 元素），这个定位可能被忽略。如果使用原生渲染，85% 是合理的底部位置。
- **建议**: 当前可接受，但注意前端如果已使用自定义 SubtitleList 组件渲染字幕，这个方法可能只在 VTT 下载功能中被用到。

### [Info] Voiceover 生成后的中间文件清理在 finally 块中
- **位置**: `src/deeplecture/use_cases/voiceover.py:207-209`
- **问题**: `segments_dir` 在 `finally` 块中被删除，即使生成失败。这是正确的行为，确保不留临时文件。
- **影响**: 无负面影响。设计合理。
- **建议**: 无需修改。这是一个良好的实践。

### [Info] Subtitle batch processing 的 fallback 在翻译失败时显示错误文本
- **位置**: `src/deeplecture/use_cases/subtitle.py:336-348`
- **问题**: 当 LLM 翻译失败时，fallback 会将 `text_target` 设置为 `"[Translation failed: {reason}]"`。这个错误文本会被保存到字幕文件中。
- **影响**: 用户在 UI 中会看到 `[Translation failed: ...]` 作为翻译文本。这比静默失败更好（用户至少知道翻译出了问题），但可能影响后续依赖翻译字幕的功能（如基于翻译字幕生成 voiceover）。
- **建议**: 当前设计可接受（fail-visible 优于 fail-silent）。但考虑在前端检测并高亮显示这类 fallback 文本。

### [Info] Upload 路由的 FormData 注释说明了前端绕过 snake_case 转换
- **位置**: `frontend/lib/api/content.ts:42`
- **问题**: 注释 `// NOTE: FormData bypasses our snake_case interceptor; send wire-format field name.` 表明开发者已意识到 FormData 不经过 snakifyKeys 处理，因此手动使用 `content_id` 而非 `contentId`。
- **影响**: 无负面影响。这是正确的处理方式，且有注释说明。
- **建议**: 无需修改。好的防御性编程实践。

### [Info] Slide lecture 使用 ThreadPoolExecutor 而非 ParallelRunner
- **位置**: `src/deeplecture/use_cases/slide_lecture.py:162-163`
- **问题**: SlideLectureUseCase 直接使用 `ThreadPoolExecutor` 进行并发 TTS + Video 处理，而其他用例（Timeline、Subtitle、Voiceover）都使用注入的 `ParallelRunnerProtocol`。
- **影响**: 不影响功能正确性，但与项目其他部分的并发模式不一致。直接使用 ThreadPoolExecutor 意味着无法通过 DI 控制并发策略。
- **建议**: 考虑迁移到 `ParallelRunnerProtocol`，保持一致性。但不是高优先级。

---

## 核心管线流程正确性总结

### Upload → Content Ready ✅
- 单文件上传（video/PDF）流程完整：验证 → 保存 → 创建 metadata → 返回 content_id
- URL 导入流程完整：验证 URL → 创建 placeholder → 提交异步任务 → worker 下载 → 更新 metadata
- 多文件 merge 流程完整：保存到 temp → merge → 创建 metadata
- 错误回滚机制完善：失败时清理临时文件和 metadata
- **问题**：异步 merge 的 task_id 在 response 中丢失

### Subtitle Generation (ASR) ✅
- 流程完整：metadata 校验 → ASR 转录 → 保存字幕 → 更新状态
- 错误处理：metadata 状态更新为 ERROR
- 前后端契约：请求/响应格式匹配（通过 snake_case ↔ camelCase 转换）

### Subtitle Enhancement + Translation ✅
- 流程完整：加载源字幕 → 提取背景 → 分批处理 → 保存 enhanced + translated → 更新状态
- Batch fallback 机制：LLM 失败时用原文 + 错误标记
- 并行处理：通过 ParallelRunner
- **注意**：Legacy 字段名兼容 (`text_en`/`text_zh` alongside `text_source`/`text_target`)

### Timeline Generation ✅
- 两阶段 LLM 处理：Segmentation → Explanation (parallel)
- Cache 机制：按 language + learner_profile 缓存
- Partial success 支持：部分 unit 失败不影响整体
- 错误类型复用 SubtitleGenerationError（见上方 Info）

### Voiceover Generation ✅
- 完整 pipeline：Load subtitles → TTS synthesis (concurrent) → Plan alignment → Apply → Concat → Timeline
- Plan+Apply 架构设计良好，分离纯计算和 I/O
- TTS 失败 fallback：超过阈值 raise，否则用 silence 替代
- Sync timeline JSON 格式完整，支持前端实时同步

### Slide Lecture Generation ✅
- 完整 pipeline：PDF render → LLM transcript (sequential) → TTS + Video (parallel) → Concat → Mux → Subtitles
- Transcript history 和 accumulated summaries 支持上下文
- Page-level error recovery：LLM 失败时使用 fallback page
- 字幕时间戳基于实际 TTS 音频时长计算，有 proportional scaling

---

## 总结

核心管线的功能实现整体完整，架构设计合理（Clean Architecture 分层、Plan+Apply 模式、依赖注入）。主要发现集中在：

1. **[Warning - 最高优先级] 异步 merge 操作丢失 task_id**：前端无法追踪多文件合并进度
2. **[Warning] 前端错误通知不一致**：voiceover 生成/删除、timeline 生成、subtitle 生成/翻译的 handler 在失败时静默，用户无感知
3. **[Warning] Voiceover `subtitle_source` 前后端契约断裂**：前端发送但后端不使用
4. **[Info] 多项小问题**：视频扩展名不一致、错误类型复用、并发模式不统一

总体评价：**管线可以走通**，核心功能正确。主要风险在 UX 层面（错误提示缺失）和一个数据丢失问题（async merge task_id）。
