# Podcast Feature Brainstorm

**Date:** 2026-03-03
**Status:** Decided
**Author:** EthanLee

## What We're Building

为 DeepLecture 添加 **Podcast（播客）** 功能，类似 Google NotebookLM 的 Audio Overview，将课程内容转化为两人对话式的音频播客。用户可以自定义角色设定、选择 LLM 和 TTS 模型、以及 prompt template。

### 核心功能

1. **AI 对话脚本生成** — 从视频字幕和/或幻灯片中提取要点，生成结构化的双人对话脚本
2. **戏剧化改写** — 第二次 LLM pass 将对话改写为更自然、口语化的版本（含语气词、非语言表达）
3. **多角色 TTS 合成** — 两个角色分别使用不同的 TTS 模型/voice 合成音频，拼接为完整播客
4. **可配置角色** — 通过 prompt template 自定义角色设定和对话风格
5. **富媒体播客播放器** — 类似 NotebookLM 的完整 UI：两个头像动画 + 进度条 + 分段点击跳转 + 交互字幕同步高亮
6. **灵活模型选择** — 用户可为每个角色独立选择 TTS 模型，LLM 模型遵循已有的级联配置

### 不做的事情（YAGNI）

- ❌ 超过两人的多人对话（v1 固定两个角色）
- ❌ 用户上传自定义语音/声音克隆
- ❌ 实时流式播客生成（先完整生成后播放）
- ❌ 播客编辑器（用户手动编辑对话脚本后重新合成）
- ❌ 播客导出为 RSS/Apple Podcast 格式
- ❌ 背景音乐/音效叠加

## Why This Approach

### 方案 B（已选）：三阶段管线 + 戏剧化改写

```
Stage 1: Knowledge Extraction (复用 cheatsheet_extraction)
  └── Output: KnowledgeItem[]

Stage 2: Dialogue Draft (新 prompt: podcast_dialogue)
  └── Output: DialogueItem[] (结构化对话)

Stage 3: Dramatization (新 prompt: podcast_dramatize)
  ├── 添加语气词: "嗯", "对对对", "哇"
  ├── 添加非语言: (laughs), (sighs)
  └── Output: DialogueItem[] (自然化对话)

Stage 4: TTS Synthesis (并行)
  ├── Speaker A → TTS Model A → audio_a[]
  ├── Speaker B → TTS Model B → audio_b[]
  └── Merge → final.mp3 + timestamps
```

**优点：**
- Stage 1 复用现有 knowledge extraction，与 Quiz/Cheatsheet/Flashcard 保持架构一致
- Stage 3 的戏剧化步骤显著提升对话自然度（参考 Meta NotebookLlama 架构）
- 各阶段解耦，便于独立调试和优化 prompt

### 被否决的方案

- **方案 A：两阶段管线** — 跳过戏剧化改写，直接从 KnowledgeItem 生成对话后进入 TTS。更简单但对话不够自然。
- **方案 C：直接生成** — 不复用 knowledge extraction，直接把原始字幕/幻灯片传给 LLM 生成对话。与现有架构不一致，无法复用提取结果。

## Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 功能目标 | 双人对话式播客 | 类似 NotebookLM Audio Overview |
| 对话风格 | 可配置角色（通过 prompt template） | 灵活支持"主持人+嘉宾"、"老师+学生"等多种风格 |
| 生成管线 | 三阶段（提取 → 对话 → 戏剧化） + TTS | 参考 NotebookLlama，戏剧化提升自然度 |
| LLM 选择 | 复用现有级联配置体系 | 与 Quiz/Cheatsheet 一致 |
| TTS 选择 | 每个角色可选不同 TTS 模型 | 灵活性最大化 |
| 输入源 | 复用现有 _load_context 管线 | 支持 subtitle/slide/both |
| 输出格式 | 合并音频 + 带时间戳的交互字幕 | 富媒体播客体验 |
| 前端 UI | 富媒体播客播放器 | 两个头像 + 进度条 + 分段跳转 + 字幕同步 |
| 存储格式 | JSON（对话脚本）+ 音频文件 | 结构化存储 |
| 架构模式 | 完全对齐现有 Clean Architecture | 代码风格统一 |

## Data Model

### 后端 DTO

```python
@dataclass
class DialogueItem:
    speaker: str      # "host" | "guest"
    text: str         # 对话文本（戏剧化后版本）

@dataclass
class PodcastDialogue:
    items: list[DialogueItem]
    title: str             # 播客标题
    summary: str           # 播客摘要

@dataclass
class PodcastAudioSegment:
    speaker: str           # "host" | "guest"
    text: str              # 对话文本
    audio_file: str        # 音频文件路径
    start_time: float      # 在合并音频中的起始时间（秒）
    end_time: float        # 在合并音频中的结束时间（秒）

@dataclass
class PodcastResult:
    dialogue: PodcastDialogue       # 完整对话脚本
    segments: list[PodcastAudioSegment]  # 带时间戳的音频片段
    audio_file: str                 # 合并后的完整音频路径
    duration: float                 # 总时长（秒）
    used_sources: list[str]         # 使用的内容来源

@dataclass
class GeneratePodcastRequest:
    content_id: str
    language: str
    context_mode: str = "both"
    user_instruction: str = ""
    subject_type: str = "auto"
    llm_model: str | None = None
    tts_model_host: str | None = None     # 主持人 TTS 模型
    tts_model_guest: str | None = None    # 嘉宾 TTS 模型
    voice_id_host: str | None = None      # 主持人声音 ID
    voice_id_guest: str | None = None     # 嘉宾声音 ID
    prompts: dict[str, str] | None = None  # prompt 模板覆盖
```

### 前端类型

```typescript
interface DialogueItem {
  speaker: "host" | "guest";
  text: string;
}

interface PodcastSegment {
  speaker: "host" | "guest";
  text: string;
  startTime: number;
  endTime: number;
}

interface PodcastResult {
  dialogue: { items: DialogueItem[]; title: string; summary: string };
  segments: PodcastSegment[];
  audioUrl: string;
  duration: number;
}
```

## Prompt 设计

### 新增 Prompt func_ids

| func_id | 描述 | 阶段 |
|---------|------|------|
| `podcast_dialogue` | 从 KnowledgeItem 生成结构化双人对话脚本 | Stage 2 |
| `podcast_dramatize` | 将结构化对话改写为自然口语化版本 | Stage 3 |

### podcast_dialogue 设计要点

- 输入：KnowledgeItem JSON + 角色设定 + 语言
- 输出：JSON 格式的 `DialogueItem[]`
- 角色设定通过 prompt template 的 `{host_role}` 和 `{guest_role}` 占位符配置
- 默认模板：主持人引导话题 + 嘉宾深入解释

### podcast_dramatize 设计要点

- 输入：Stage 2 输出的 DialogueItem JSON
- 输出：改写后的 DialogueItem JSON
- 参考 NotebookLlama 的 "oscar winning screenwriter" 改写策略
- 添加自然语言元素：语气词、打断、反应
- 保持内容准确性，只改形式不改内容

## 前端 UI 设计

### 播客播放器 (PodcastTab.tsx)

参考项目：
- [Meeting-BaaS/transcript-seeker](https://github.com/Meeting-BaaS/transcript-seeker) — 转录同步 UI
- [wavesurfer.js](https://github.com/katspaugh/wavesurfer.js) — 波形可视化
- [Metaview blog](https://www.metaview.ai/resources/blog/syncing-a-transcript-with-audio-in-react) — 性能优化：DOM ref mutation 而非 React state

### UI 组件

1. **播放控制栏** — 播放/暂停、进度条、时间显示、播放速度
2. **双头像区域** — 两个角色的头像，当前说话者高亮/动画
3. **对话字幕区域** — 滚动显示对话文本，当前播放段落高亮，点击任意段落跳转
4. **生成控制面板** — LLM 选择、两个 TTS 模型选择、prompt template 选择

### 性能注意

- 字幕同步高亮使用 DOM ref mutation（不用 React state 驱动 re-render）
- 音频文件懒加载
- 波形可视化可选（非 MVP 必需）

## 后端架构

### 新增文件

| 层 | 文件 | 描述 |
|----|------|------|
| DTO | `use_cases/dto/podcast.py` | `GeneratePodcastRequest`, `DialogueItem`, `PodcastResult` 等 |
| Interface | `use_cases/interfaces/podcast.py` | `PodcastStorageProtocol` |
| Prompt | `use_cases/prompts/podcast.py` | `build_podcast_dialogue_prompts()`, `build_podcast_dramatize_prompts()` |
| Use Case | `use_cases/podcast.py` | `PodcastUseCase` (三阶段管线 + TTS 合成) |
| Storage | `infrastructure/repositories/fs_podcast_storage.py` | JSON + 音频文件存储 |
| Route | `presentation/api/routes/podcast.py` | GET + POST endpoints |
| DI | `di/container.py` | 注册 podcast_storage + podcast_usecase |
| Prompt Registry | `use_cases/prompts/registry.py` | 注册 `podcast_dialogue` 和 `podcast_dramatize` |

### 新增前端文件

| 文件 | 描述 |
|------|------|
| `frontend/lib/api/podcast.ts` | API 客户端 |
| `frontend/components/features/PodcastTab.tsx` | 播客播放器主组件 |

### 修改文件

- `frontend/stores/tabLayoutStore.ts` — 注册 `podcast` tab（已存在 TabId）
- `frontend/components/video/TabContentRenderer.tsx` — 添加 podcast 渲染 case
- `frontend/components/video/VideoPageClient.tsx` — 添加 refreshPodcast
- `src/deeplecture/presentation/api/routes/__init__.py` — 注册 podcast route
- `src/deeplecture/presentation/api/app.py` — 注册 blueprint

## TTS 集成

### 双 TTS 模型支持

Podcast 特殊之处在于需要为两个角色使用不同的 TTS 模型。现有的 `resolve_models_for_task()` 只返回单个 `tts_model`。

**方案：** 在 Request DTO 中添加 `tts_model_host` 和 `tts_model_guest` 两个独立字段，在 use case 层分别通过 `tts_provider.get()` 获取对应的 TTS 实例。Route 层需要做两次 TTS 模型解析。

### 音频合成流程

```
对话脚本: [host_1, guest_1, host_2, guest_2, ...]
    ↓ 按 speaker 分组
host_texts: [host_1, host_2, ...]  →  TTS Model A  →  host_audios[]
guest_texts: [guest_1, guest_2, ...] →  TTS Model B  →  guest_audios[]
    ↓ 按原始顺序交叉合并
merged_audio = interleave(host_audios, guest_audios)
    ↓ 计算时间戳
segments = calculate_timestamps(merged_audio)
    ↓ 导出
final.mp3 + segments.json
```

## Open Questions

1. **音频格式** — 合并音频用 MP3 还是 WAV？MP3 更小但需要编码库。
2. **音频合并工具** — 使用 ffmpeg（已集成）还是 pydub？
3. **头像设计** — 使用固定的默认头像还是根据角色生成？
4. **长内容分块** — 参考 Podcastfy 的 Content Chunking with Contextual Linking 策略，是否需要在 v1 实现？
5. **Voice ID 管理** — 如何在前端展示可用的 voice ID 列表？需要新的 API 端点？

## 参考资料

- [souzatharsis/podcastfy](https://github.com/souzatharsis/podcastfy) — 最完整的开源 podcast 生成工具
- [mozilla-ai/document-to-podcast](https://github.com/mozilla-ai/document-to-podcast) — Mozilla AI 的本地 podcast 生成
- [meta-llama/NotebookLlama](https://github.com/meta-llama/llama-recipes/tree/main/recipes/quickstart/NotebookLlama) — Meta 官方参考管线
- [Together.ai PDF-to-Podcast](https://docs.together.ai/docs/open-notebooklm-pdf-to-podcast) — Pydantic 结构化输出 + scratchpad 策略
- [nari-labs/dia](https://github.com/nari-labs/dia) — 专为对话设计的 TTS（[S1]/[S2] 标签）
- [Nicole Hennig — Reverse Engineering NotebookLM](https://nicolehennig.com/notebooklm-reverse-engineering-the-system-prompt-for-audio-overviews/)
- [Meeting-BaaS/transcript-seeker](https://github.com/Meeting-BaaS/transcript-seeker) — 转录同步 UI
- [wavesurfer.js](https://github.com/katspaugh/wavesurfer.js) — 波形可视化
- [Metaview — Syncing Transcript with Audio in React](https://www.metaview.ai/resources/blog/syncing-a-transcript-with-audio-in-react)
