---
title: "feat: Add NotebookLM-style podcast dialogue generation"
type: feat
date: 2026-03-03
brainstorm: docs/brainstorms/2026-03-03-podcast-brainstorm.md
---

# feat: Add NotebookLM-style podcast dialogue generation

## Overview

为 DeepLecture 添加 **Podcast（播客）** 功能，类似 Google NotebookLM 的 Audio Overview，将课程内容（字幕/幻灯片）转化为两人对话式的音频播客。

后端采用**三阶段 LLM 管线**（知识提取 → 对话脚本 → 戏剧化改写）+ **双角色并行 TTS 合成** + **音频合并**。前端提供富媒体播客播放器：双头像动画、进度条、交互字幕同步高亮、分段点击跳转。

用户可自定义角色设定（通过 prompt template）、LLM 模型、每个角色的 TTS 模型/voice。

## Problem Statement / Motivation

DeepLecture 已有 Quiz、Cheatsheet、Notes、Flashcard 四种 AI 生成的学习辅助工具，但全部是**文字形式**。缺少一种利用音频通道的学习方式——通过听对话式的内容回顾，用户可以在通勤、运动等场景下继续学习。

Google NotebookLM 的 Audio Overview 功能已经验证了这种体验的价值：将文档内容转化为轻松的两人对话，比单纯阅读更容易吸收和记忆。

## Proposed Solution

完全对齐现有 Clean Architecture 模式，在 Quiz/Cheatsheet 的两阶段管线基础上扩展为三阶段。关键架构决策：

- **三阶段 LLM 管线**：复用 `cheatsheet_extraction` → 新增 `podcast_dialogue` → 新增 `podcast_dramatize`
- **双 TTS 模型**：每个角色（host/guest）可独立选择 TTS 模型和 voice ID
- **音频处理**：复用现有 `AudioProcessorProtocol`（FFmpeg）进行转码、拼接、格式转换
- **JSON + M4A 存储**：`content/{id}/podcast/{lang}.json`（脚本+时间戳）+ `content/{id}/podcast/{lang}.m4a`（音频）
- **富媒体前端播放器**：wavesurfer.js 可选，HTML5 Audio API + DOM ref mutation 同步字幕
- **前端复用 `useSSEGenerationRetry` hook**，与其他 feature tab 统一

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend                                                    │
│  PodcastTab.tsx ──→ podcast.ts API ──→ POST /generate        │
│       ↕ useSSEGenerationRetry                                │
│  PodcastPlayer ←── GET /api/podcast/{id}                     │
│       ↕ <audio> ←── GET /api/podcast/{id}/audio              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Backend                                                     │
│  routes/podcast.py ──→ PodcastUseCase.generate()             │
│                              │                               │
│          ┌───────────────────┼──────────────────┐            │
│          │ Stage 1           │ Stage 2           │ Stage 3    │
│          │ cheatsheet_       │ podcast_          │ podcast_   │
│          │ extraction        │ dialogue          │ dramatize  │
│          │ (shared)          │ (new)             │ (new)      │
│          │ → KnowledgeItem[] │ → DialogueItem[]  │ → Dramatized │
│          └───────────────────┼──────────────────┘  DialogueItem[]
│                              │                               │
│          ┌───────────────────┼──────────────────┐            │
│          │ Stage 4: Parallel TTS                 │            │
│          │ Host → TTS Model A → wav[]            │            │
│          │ Guest → TTS Model B → wav[]           │            │
│          │ Interleave + silence gaps → concat    │            │
│          │ → M4A + timestamp manifest            │            │
│          └──────────────────────────────────────┘            │
│                              │                               │
│  FsPodcastStorage ──→ content/{id}/podcast/{lang}.json       │
│                      content/{id}/podcast/{lang}.m4a         │
└─────────────────────────────────────────────────────────────┘
```

## Technical Approach

### Architecture

本功能与 voiceover/slide_lecture 共享最多模式（LLM + TTS + 音频合并），而非 quiz/cheatsheet（仅 LLM）。关键区别：

| 维度 | Quiz/Cheatsheet | Voiceover | **Podcast** |
|------|-----------------|-----------|-------------|
| LLM 阶段 | 2 阶段 | 无 | **3 阶段** |
| TTS | 无 | 单模型 | **双模型** |
| 音频处理 | 无 | concat + encode | **concat + silence + encode** |
| 存储 | JSON only | JSON + M4A | **JSON + M4A** |
| 并行执行 | 无 | voiceover_tts | **podcast_tts** |

### Implementation Phases

---

#### Phase 1: Backend 核心 — DTO + Storage + Interface

**目标：** 建立数据层基础，定义所有类型和存储协议。

##### 1.1 DTO 定义

**新建文件：** `src/deeplecture/use_cases/dto/podcast.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DialogueItem:
    """单条对话。"""
    speaker: str                        # "host" | "guest"
    text: str                           # 对话文本（戏剧化后）

    def to_dict(self) -> dict[str, Any]:
        return {"speaker": self.speaker, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DialogueItem:
        return cls(speaker=data.get("speaker", "host"), text=data.get("text", ""))


@dataclass
class PodcastSegment:
    """带时间戳的音频片段（对应一条 DialogueItem）。"""
    speaker: str                        # "host" | "guest"
    text: str                           # 对话文本
    start_time: float                   # 在合并音频中的起始时间（秒）
    end_time: float                     # 结束时间（秒）

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PodcastSegment:
        return cls(
            speaker=data.get("speaker", "host"),
            text=data.get("text", ""),
            start_time=float(data.get("start_time", 0)),
            end_time=float(data.get("end_time", 0)),
        )


@dataclass
class GeneratePodcastRequest:
    """生成请求参数。"""
    content_id: str
    language: str                           # 必填：输出语言
    context_mode: str = "both"              # subtitle | slide | both
    user_instruction: str = ""              # 额外指导
    subject_type: str = "auto"              # stem | humanities | auto
    llm_model: str | None = None            # LLM 模型覆盖
    tts_model_host: str | None = None       # 主持人 TTS 模型
    tts_model_guest: str | None = None      # 嘉宾 TTS 模型
    voice_id_host: str | None = None        # 主持人 voice ID
    voice_id_guest: str | None = None       # 嘉宾 voice ID
    turn_gap_seconds: float = 0.3           # 对话转换间隔（秒）
    prompts: dict[str, str] | None = None   # prompt 模板覆盖


@dataclass
class PodcastResult:
    """GET/响应 DTO。"""
    content_id: str
    language: str
    title: str = ""
    summary: str = ""
    segments: list[PodcastSegment] = field(default_factory=list)
    duration: float = 0.0                   # 总时长（秒）
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "language": self.language,
            "title": self.title,
            "summary": self.summary,
            "segments": [s.to_dict() for s in self.segments],
            "segment_count": len(self.segments),
            "duration": self.duration,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class GeneratedPodcastResult:
    """生成完成响应 DTO。"""
    content_id: str
    language: str
    title: str
    summary: str
    segments: list[PodcastSegment]
    duration: float
    updated_at: datetime | None
    used_sources: list[str]
    stats: PodcastStats

    def to_dict(self) -> dict[str, Any]:
        return {
            **PodcastResult(
                content_id=self.content_id,
                language=self.language,
                title=self.title,
                summary=self.summary,
                segments=self.segments,
                duration=self.duration,
                updated_at=self.updated_at,
            ).to_dict(),
            "used_sources": self.used_sources,
            "stats": {
                "total_dialogue_items": self.stats.total_dialogue_items,
                "tts_success_count": self.stats.tts_success_count,
                "tts_failure_count": self.stats.tts_failure_count,
            },
        }


@dataclass
class PodcastStats:
    """生成统计信息。"""
    total_dialogue_items: int = 0
    tts_success_count: int = 0
    tts_failure_count: int = 0
```

##### 1.2 Storage Protocol

**新建文件：** `src/deeplecture/use_cases/interfaces/podcast.py`

```python
class PodcastStorageProtocol(Protocol):
    def load(self, content_id: str, language: str | None = None) -> tuple[dict[str, Any], datetime] | None: ...
    def save(self, content_id: str, language: str, data: dict[str, Any]) -> datetime: ...
    def exists(self, content_id: str, language: str | None = None) -> bool: ...
    def get_audio_path(self, content_id: str, language: str) -> str: ...
```

注意：比其他 storage 多一个 `get_audio_path()` 方法，用于构建音频文件 URL。

##### 1.3 Storage 实现

**新建文件：** `src/deeplecture/infrastructure/repositories/fs_podcast_storage.py`

```python
class FsPodcastStorage:
    NAMESPACE = "podcast"

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver

    def _get_json_path(self, content_id: str, language: str) -> Path:
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE, f"{language}.json"))

    def _get_audio_path(self, content_id: str, language: str) -> Path:
        return Path(self._paths.build_content_path(content_id, self.NAMESPACE, f"{language}.m4a"))

    def get_audio_path(self, content_id: str, language: str) -> str:
        return str(self._get_audio_path(content_id, language))

    def load(self, content_id, language=None) -> tuple[dict[str, Any], datetime] | None:
        # 对齐 FsFlashcardStorage.load() 模式
        ...

    def save(self, content_id, language, data) -> datetime:
        # 原子写入 JSON manifest（tempfile + os.replace）
        # 音频文件由 use case 单独写入（不通过此方法）
        ...
```

**存储布局：**
```
content/{content_id}/podcast/
├── en.json              # 对话脚本 + 时间戳 manifest
├── en.m4a               # 合并后的完整音频
├── en_segments/          # 中间文件（生成后清理）
│   ├── 000_host.wav
│   ├── 001_guest.wav
│   ├── ...
│   └── silence.wav
└── zh.json              # 其他语言...
```

##### 1.4 Export 注册

**修改文件：** `src/deeplecture/use_cases/interfaces/__init__.py` — 导出 `PodcastStorageProtocol`
**修改文件：** `src/deeplecture/infrastructure/repositories/__init__.py` — 导出 `FsPodcastStorage`
**修改文件：** `src/deeplecture/infrastructure/__init__.py` — 导出 `FsPodcastStorage`

---

#### Phase 2: Backend — Prompt 设计与注册

**目标：** 创建对话生成和戏剧化改写的 prompt，注册到 PromptRegistry。

##### 2.1 Podcast Prompt 构建函数

**新建文件：** `src/deeplecture/use_cases/prompts/podcast.py`

两个 prompt 函数：

**A. `build_podcast_dialogue_prompts()`** — Stage 2：从 KnowledgeItem 生成结构化对话

```python
def build_podcast_dialogue_prompts(
    knowledge_items_json: str,
    language: str,
    host_role: str = "A curious podcast host who guides the discussion",
    guest_role: str = "An expert guest who explains concepts with analogies",
    user_instruction: str = "",
) -> tuple[str, str]:
    """Stage 2: 生成结构化双人对话脚本。"""
    system_prompt = f"""You are a world-class podcast script writer.

TASK: Transform the provided knowledge items into an engaging two-person podcast dialogue.

SPEAKERS:
- "host": {host_role}
- "guest": {guest_role}

OUTPUT FORMAT (CRITICAL):
Output ONLY a JSON object:
{{
  "title": "Podcast episode title",
  "summary": "2-3 sentence summary of what the episode covers",
  "scratchpad": "Your planning notes (conversation flow, key topics to cover, opening hook)",
  "dialogue": [
    {{"speaker": "host", "text": "Opening line..."}},
    {{"speaker": "guest", "text": "Response..."}},
    ...
  ]
}}

GUIDELINES:
- Start with host introducing the topic engagingly
- Alternate between speakers naturally (not strictly ABAB — sometimes 2-3 lines from same speaker)
- Guest explains core concepts, host asks follow-up questions
- Cover all major knowledge items but weave them into natural conversation
- End with a summary/wrap-up
- Target 30-80 dialogue turns depending on content density
- Each dialogue turn: 1-4 sentences (keep it conversational, not lecture-style)
- Output language: {language}
"""
    user_prompt = f"""Create a podcast dialogue from these knowledge items:

{knowledge_items_json}

{"Additional instructions: " + user_instruction if user_instruction else ""}
"""
    return system_prompt, user_prompt
```

**B. `build_podcast_dramatize_prompts()`** — Stage 3：戏剧化改写

```python
def build_podcast_dramatize_prompts(
    dialogue_json: str,
    language: str,
    user_instruction: str = "",
) -> tuple[str, str]:
    """Stage 3: 改写对话使其更自然、口语化。"""
    system_prompt = f"""You are an award-winning audio drama screenwriter.

TASK: Rewrite the podcast dialogue to sound natural when read aloud by a TTS engine.

REWRITE RULES:
1. Add natural filler words and reactions:
   - English: "Right", "Exactly", "Hmm", "Oh wow", "You know", "I mean"
   - Chinese: "嗯", "对对对", "哇", "是的是的", "你知道吗", "就是说"
   - Match the language of the input
2. Add non-verbal cues in parentheses ONLY if TTS supports them: (laughs), (sighs), (pauses)
3. Use contractions and informal grammar where natural
4. Break long sentences into shorter, punchier ones
5. Add brief interruptions and reactions from the other speaker
6. Keep ALL factual content intact — change FORM, not SUBSTANCE

OUTPUT FORMAT:
Output ONLY a JSON object with the same structure as input:
{{
  "title": "...",
  "summary": "...",
  "dialogue": [
    {{"speaker": "host", "text": "Rewritten line..."}},
    ...
  ]
}}

IMPORTANT:
- The output dialogue may have MORE items than input (due to added reactions)
- Each speaker's core points must be preserved
- Output language: {language}
"""
    user_prompt = f"""Rewrite this podcast dialogue to sound natural and engaging:

{dialogue_json}

{"Additional instructions: " + user_instruction if user_instruction else ""}
"""
    return system_prompt, user_prompt
```

##### 2.2 Prompt Registry 注册

**修改文件：** `src/deeplecture/use_cases/prompts/registry.py`

新增两个 Builder 类 + 注册：

```python
class PodcastDialogueBuilder(BasePromptBuilder):
    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.podcast import build_podcast_dialogue_prompts
        system_prompt, user_prompt = build_podcast_dialogue_prompts(
            knowledge_items_json=kwargs["knowledge_items_json"],
            language=kwargs["language"],
            host_role=kwargs.get("host_role", ""),
            guest_role=kwargs.get("guest_role", ""),
            user_instruction=kwargs.get("user_instruction", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return "Generates a two-person podcast dialogue script from knowledge items."


class PodcastDramatizeBuilder(BasePromptBuilder):
    def build(self, **kwargs) -> PromptSpec:
        from deeplecture.use_cases.prompts.podcast import build_podcast_dramatize_prompts
        system_prompt, user_prompt = build_podcast_dramatize_prompts(
            dialogue_json=kwargs["dialogue_json"],
            language=kwargs["language"],
            user_instruction=kwargs.get("user_instruction", ""),
        )
        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)

    def get_preview_text(self) -> str:
        return "Rewrites podcast dialogue to sound natural and conversational."

# 在 create_default_registry() 中注册：
registry.register(
    "podcast_dialogue",
    PodcastDialogueBuilder("default", "Default", "Two-person podcast dialogue generation"),
    is_default=True,
)
registry.register(
    "podcast_dramatize",
    PodcastDramatizeBuilder("default", "Default", "Dialogue dramatization for TTS"),
    is_default=True,
)
```

##### 2.3 Template Placeholder Rules

**修改文件：** `src/deeplecture/use_cases/prompts/template_definitions.py`

```python
_FUNC_PLACEHOLDER_RULES["podcast_dialogue"] = {
    "allowed": {"knowledge_items_json", "language", "host_role", "guest_role", "user_instruction"},
    "required": {"knowledge_items_json", "language"},
}
_FUNC_PLACEHOLDER_RULES["podcast_dramatize"] = {
    "allowed": {"dialogue_json", "language", "user_instruction"},
    "required": {"dialogue_json", "language"},
}
```

---

#### Phase 3: Backend — PodcastUseCase 核心管线

**目标：** 实现三阶段 LLM + 并行 TTS + 音频合并管线。

##### 3.1 ParallelGroup 注册

**修改文件：** `src/deeplecture/use_cases/interfaces/parallel.py`

添加 `"podcast_tts"` 到 `ParallelGroup` Literal 类型。

##### 3.2 PodcastUseCase

**新建文件：** `src/deeplecture/use_cases/podcast.py`

构造函数（融合 quiz + voiceover + slide_lecture 的依赖）：

```python
class PodcastUseCase:
    # 对话段数上限（防止 LLM 失控）
    MAX_DIALOGUE_ITEMS = 100
    # TTS 失败容忍阈值
    TTS_FAILURE_THRESHOLD = 0.5  # >50% 失败则中止
    # 默认转换间隔（秒）
    DEFAULT_TURN_GAP = 0.3
    # TTS 转码采样率
    SAMPLE_RATE = 24000

    def __init__(
        self,
        *,
        podcast_storage: PodcastStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        llm_provider: LLMProviderProtocol,
        tts_provider: TTSProviderProtocol,
        audio_processor: AudioProcessorProtocol,
        file_storage: FileStorageProtocol,
        path_resolver: PathResolverProtocol,
        prompt_registry: PromptRegistryProtocol,
        parallel_runner: ParallelRunnerProtocol,
        metadata_storage: MetadataStorageProtocol | None = None,
        pdf_text_extractor: PdfTextExtractorProtocol | None = None,
    ) -> None:
```

**核心 `generate()` 方法流程：**

```python
def generate(self, request: GeneratePodcastRequest) -> GeneratedPodcastResult:
    llm = self._llm_provider.get(request.llm_model)

    # --- Stage 1: Knowledge Extraction (复用) ---
    context, used_sources = self._load_context(request)   # 对齐 quiz/cheatsheet
    knowledge_items = self._extract_knowledge_items(
        context, request.language, request.subject_type,
        request.user_instruction, llm, request.prompts,
    )

    # --- Stage 2: Dialogue Generation ---
    raw_dialogue = self._generate_dialogue(
        knowledge_items, request.language, request.user_instruction,
        llm, request.prompts,
    )
    # 验证 + 截断到 MAX_DIALOGUE_ITEMS
    dialogue_items = self._validate_dialogue(raw_dialogue)

    # --- Stage 3: Dramatization ---
    dramatized = self._dramatize_dialogue(
        dialogue_items, request.language, request.user_instruction,
        llm, request.prompts,
    )

    # --- Stage 4: Parallel TTS Synthesis ---
    segments_dir = self._prepare_segments_dir(request.content_id, request.language)
    tts_host = self._tts_provider.get(request.tts_model_host)
    tts_guest = self._tts_provider.get(request.tts_model_guest)

    segment_results = self._synthesize_all_segments(
        dramatized, tts_host, tts_guest,
        request.voice_id_host, request.voice_id_guest,
        segments_dir, request.turn_gap_seconds,
    )

    # --- Stage 5: Audio Merge + Timestamp Calculation ---
    audio_path = self._podcast_storage.get_audio_path(
        request.content_id, request.language
    )
    segments = self._merge_and_calculate_timestamps(
        segment_results, audio_path, request.turn_gap_seconds,
    )

    # --- Cleanup intermediate WAVs ---
    self._cleanup_segments_dir(segments_dir)

    # --- Save manifest ---
    total_duration = segments[-1].end_time if segments else 0.0
    title = raw_dialogue.get("title", "Podcast")
    summary = raw_dialogue.get("summary", "")
    stats = PodcastStats(...)
    self._podcast_storage.save(request.content_id, request.language, {...})

    return GeneratedPodcastResult(...)
```

**关键内部方法：**

**`_generate_dialogue()`** — Stage 2
```python
def _generate_dialogue(self, knowledge_items, language, user_instruction, llm, prompts):
    items_json = json.dumps([item.to_dict() for item in knowledge_items], ensure_ascii=False)
    impl_id = prompts.get("podcast_dialogue") if prompts else None
    builder = self._prompt_registry.get("podcast_dialogue", impl_id)
    spec = builder.build(
        knowledge_items_json=items_json,
        language=language,
        user_instruction=user_instruction,
    )
    response = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)
    return parse_llm_json(response, default_type=dict, context="podcast dialogue")
```

**`_dramatize_dialogue()`** — Stage 3
```python
def _dramatize_dialogue(self, dialogue_items, language, user_instruction, llm, prompts):
    dialogue_json = json.dumps(
        {"dialogue": [item.to_dict() for item in dialogue_items]},
        ensure_ascii=False,
    )
    impl_id = prompts.get("podcast_dramatize") if prompts else None
    builder = self._prompt_registry.get("podcast_dramatize", impl_id)
    spec = builder.build(dialogue_json=dialogue_json, language=language, user_instruction=user_instruction)
    response = llm.complete(spec.user_prompt, system_prompt=spec.system_prompt)
    result = parse_llm_json(response, default_type=dict, context="podcast dramatize")
    return [DialogueItem.from_dict(d) for d in result.get("dialogue", [])]
```

**`_synthesize_all_segments()`** — Stage 4（并行 TTS）

```python
def _synthesize_all_segments(self, dialogue_items, tts_host, tts_guest,
                              voice_host, voice_guest, segments_dir, turn_gap):
    """为每条对话合成音频。参考 slide_lecture._synthesize_to_wav() 模式。"""
    def _synth_one(index_and_item):
        idx, item = index_and_item
        tts = tts_host if item.speaker == "host" else tts_guest
        voice = voice_host if item.speaker == "host" else voice_guest
        wav_path = os.path.join(segments_dir, f"{idx:03d}_{item.speaker}.wav")
        try:
            raw_bytes = tts.synthesize(item.text, voice=voice)
            # 写入 raw 文件 → 转码为标准 WAV
            ext = getattr(tts, "file_extension", ".wav") or ".wav"
            raw_path = os.path.join(segments_dir, f"{idx:03d}_raw{ext}")
            self._file_storage.write_bytes(raw_path, raw_bytes)
            self._audio.transcode_to_wav(raw_path, wav_path,
                                          sample_rate=self.SAMPLE_RATE, channels=1)
            os.remove(raw_path)
            duration = self._audio.probe_duration_seconds(wav_path)
            return (idx, item.speaker, item.text, wav_path, duration, True)
        except Exception:
            # 失败时生成静音（参考 SlideLectureUseCase 模式）
            self._audio.generate_silence_wav(
                wav_path, duration=0.5, sample_rate=self.SAMPLE_RATE, channels=1
            )
            return (idx, item.speaker, item.text, wav_path, 0.5, False)

    indexed = list(enumerate(dialogue_items))
    results = self._parallel_runner.map_ordered(
        _synth_one, indexed, group="podcast_tts"
    )
    # 检查失败率
    failures = sum(1 for r in results if not r[5])
    if len(results) > 0 and failures / len(results) > self.TTS_FAILURE_THRESHOLD:
        raise RuntimeError(f"TTS failure rate too high: {failures}/{len(results)}")
    return results
```

**`_merge_and_calculate_timestamps()`** — Stage 5

```python
def _merge_and_calculate_timestamps(self, segment_results, output_path, turn_gap):
    """合并音频并计算时间戳。参考 voiceover._concat_audio() 模式。"""
    # 生成静音 WAV 用于间隔
    silence_path = os.path.join(os.path.dirname(output_path), "_silence.wav")
    self._audio.generate_silence_wav(
        silence_path, duration=turn_gap, sample_rate=self.SAMPLE_RATE, channels=1
    )

    ordered_paths = []
    segments = []
    current_time = 0.0

    for idx, speaker, text, wav_path, duration, success in segment_results:
        if idx > 0:
            ordered_paths.append(silence_path)
            current_time += turn_gap
        ordered_paths.append(wav_path)
        segments.append(PodcastSegment(
            speaker=speaker, text=text,
            start_time=current_time, end_time=current_time + duration,
        ))
        current_time += duration

    # 合并为 M4A
    self._audio.concat_wavs_to_m4a(ordered_paths, output_path, bitrate="192k")
    os.remove(silence_path)
    return segments
```

##### 3.3 DI Container 注册

**修改文件：** `src/deeplecture/di/container.py`

```python
@property
def podcast_storage(self) -> FsPodcastStorage:
    if "podcast_storage" not in self._cache:
        self._cache["podcast_storage"] = FsPodcastStorage(self.path_resolver)
    return self._cache["podcast_storage"]

@property
def podcast_usecase(self) -> PodcastUseCase:
    if "podcast_uc" not in self._cache:
        self._cache["podcast_uc"] = PodcastUseCase(
            podcast_storage=self.podcast_storage,
            subtitle_storage=self.subtitle_storage,
            llm_provider=self.llm_provider,
            tts_provider=self.tts_provider,
            audio_processor=self.audio_processor,
            file_storage=self._file_storage,
            path_resolver=self.path_resolver,
            prompt_registry=self.prompt_registry,
            parallel_runner=self.parallel_runner,
            metadata_storage=self.metadata_storage,
            pdf_text_extractor=self.pdf_text_extractor,
        )
    return self._cache["podcast_uc"]
```

##### 3.4 Task Key 注册

**修改文件：** `src/deeplecture/presentation/api/shared/model_resolution.py`

将 `"podcast_generation"` 添加到 `LLM_TASK_KEYS` 和 `TTS_TASK_KEYS`。

---

#### Phase 4: Backend — API 路由

**目标：** 创建 REST API 端点（GET + POST + 音频流）。

##### 4.1 路由实现

**新建文件：** `src/deeplecture/presentation/api/routes/podcast.py`

```python
bp = Blueprint("podcast", __name__)

@bp.route("/<content_id>", methods=["GET"])
@handle_errors
def get_podcast(content_id: str) -> Response:
    """GET /api/podcast/{content_id}?language=en"""
    content_id = validate_content_id(content_id)
    language = validate_language(request.args.get("language"), ...)
    container = get_container()
    result = container.podcast_usecase.get(content_id, language)
    if not result or not result.segments:
        return not_found(f"Podcast not found for {content_id}")
    return success(result.to_dict())


@bp.route("/<content_id>/audio", methods=["GET"])
@handle_errors
def get_podcast_audio(content_id: str) -> Response:
    """GET /api/podcast/{content_id}/audio?language=en — 流式返回 M4A 文件"""
    content_id = validate_content_id(content_id)
    language = validate_language(request.args.get("language"), ...)
    container = get_container()
    audio_path = container.podcast_storage.get_audio_path(content_id, language)
    if not os.path.exists(audio_path):
        return not_found("Podcast audio not found")
    return send_file(
        audio_path,
        mimetype="audio/mp4",
        as_attachment=False,
        download_name=f"podcast_{language}.m4a",
    )


@bp.route("/<content_id>/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_podcast(content_id: str) -> Response:
    """POST /api/podcast/{content_id}/generate"""
    content_id = validate_content_id(content_id)
    data = request.get_json() or {}

    language = validate_language(data.get("language"), required=True)
    context_mode = data.get("context_mode", "both")
    user_instruction = data.get("user_instruction", "")
    llm_model = data.get("llm_model")
    tts_model_host = data.get("tts_model_host")
    tts_model_guest = data.get("tts_model_guest")
    voice_id_host = data.get("voice_id_host")
    voice_id_guest = data.get("voice_id_guest")
    turn_gap_seconds = float(data.get("turn_gap_seconds", 0.3))
    prompts = data.get("prompts")

    container = get_container()

    # LLM 解析（复用现有级联配置）
    llm_model, _ = resolve_models_for_task(
        container=container, content_id=content_id,
        task_key="podcast_generation", llm_model=llm_model, tts_model=None,
    )

    # TTS 解析：不通过 resolve_models_for_task，直接透传用户选择或使用默认
    if not tts_model_host:
        _, tts_model_host = resolve_models_for_task(
            container=container, content_id=content_id,
            task_key="podcast_generation", llm_model=None, tts_model=tts_model_host,
        )
    if not tts_model_guest:
        _, tts_model_guest = resolve_models_for_task(
            container=container, content_id=content_id,
            task_key="podcast_generation", llm_model=None, tts_model=tts_model_guest,
        )

    req = GeneratePodcastRequest(
        content_id=content_id, language=language, context_mode=context_mode,
        user_instruction=user_instruction, llm_model=llm_model,
        tts_model_host=tts_model_host, tts_model_guest=tts_model_guest,
        voice_id_host=voice_id_host, voice_id_guest=voice_id_guest,
        turn_gap_seconds=turn_gap_seconds, prompts=prompts,
    )

    def _run_generation(ctx: object) -> dict:
        result = container.podcast_usecase.generate(req)
        return result.to_dict()

    task_id = container.task_manager.submit(
        content_id=content_id,
        task_type="podcast_generation",
        task=_run_generation,
        metadata={"language": language},
    )

    return accepted({
        "content_id": content_id,
        "task_id": task_id,
        "status": "pending",
        "message": "Podcast generation started",
    })
```

##### 4.2 Blueprint 注册

**修改文件：** `src/deeplecture/presentation/api/routes/__init__.py`
```python
from deeplecture.presentation.api.routes.podcast import bp as podcast_bp
```

**修改文件：** `src/deeplecture/presentation/api/app.py`
```python
app.register_blueprint(podcast_bp, url_prefix="/api/podcast")
```

---

#### Phase 5: Frontend — API 客户端 + SSE 集成

**目标：** 建立数据层和异步任务集成。

##### 5.1 API 客户端

**新建文件：** `frontend/lib/api/podcast.ts`

```typescript
import { api } from "./client";
import { withAIOverrides } from "./ai-overrides";

export interface PodcastSegment {
  speaker: "host" | "guest";
  text: string;
  startTime: number;
  endTime: number;
}

export interface PodcastResponse {
  contentId: string;
  language: string;
  title: string;
  summary: string;
  segments: PodcastSegment[];
  segmentCount: number;
  duration: number;
  updatedAt: string | null;
}

export interface GeneratePodcastResponse {
  contentId: string;
  taskId: string;
  status: "pending";
  message: string;
}

export interface GeneratePodcastParams {
  contentId: string;
  language: string;
  contextMode?: "subtitle" | "slide" | "both";
  instruction?: string;
  ttsModelHost?: string;
  ttsModelGuest?: string;
  voiceIdHost?: string;
  voiceIdGuest?: string;
}

export const getPodcast = async (
  contentId: string,
  language: string,
): Promise<PodcastResponse | null> => {
  try {
    const response = await api.get<PodcastResponse>(`/podcast/${contentId}`, {
      params: { language },
    });
    return response.data;
  } catch (error: unknown) {
    if (error && typeof error === "object" && "status" in error && error.status === 404) {
      return null;
    }
    throw error;
  }
};

export const generatePodcast = async (
  params: GeneratePodcastParams,
): Promise<GeneratePodcastResponse> => {
  const response = await api.post<GeneratePodcastResponse>(
    `/podcast/${params.contentId}/generate`,
    withAIOverrides({
      language: params.language,
      context_mode: params.contextMode ?? "both",
      user_instruction: params.instruction ?? "",
      tts_model_host: params.ttsModelHost,
      tts_model_guest: params.ttsModelGuest,
      voice_id_host: params.voiceIdHost,
      voice_id_guest: params.voiceIdGuest,
    }),
  );
  return response.data;
};

/** 构建音频 URL */
export const getPodcastAudioUrl = (contentId: string, language: string): string => {
  return `/api/podcast/${contentId}/audio?language=${encodeURIComponent(language)}`;
};
```

##### 5.2 SSE 刷新触发器

**修改文件：** `frontend/hooks/useVideoPageState.ts`

- 添加 `refreshPodcast` state counter
- 在 SSE 事件处理器中添加 `"podcast_generation"` 任务类型分支
- 添加到 `CONTENT_REFRESH_TASK_TYPES`

**修改文件：** `frontend/components/video/VideoPageClient.tsx`

- 将 `refreshPodcast` 传递到 `TabContentRenderer`

##### 5.3 Task Type 标签

**修改文件：** `frontend/lib/taskTypes.ts`（如果存在）

添加 `"podcast_generation": "Podcast"` 到 `TASK_LABELS`。

---

#### Phase 6: Frontend — PodcastTab 播放器组件

**目标：** 构建富媒体播客播放器 UI。

##### 6.1 PodcastTab 主组件

**新建文件：** `frontend/components/features/PodcastTab.tsx`

```
PodcastTab
├── Props: { videoId, onSeek, refreshTrigger }
├── Hook: useSSEGenerationRetry<PodcastData>({
│       taskType: "podcast_generation",
│       fetchContent: getPodcast(videoId, language),
│       submitGeneration: generatePodcast({...}),
│   })
├── States: Loading → Generating → Error → Idle (CTA) → Content
│
├── Content View:
│   ├── Header: 标题 + 摘要 + 重新生成按钮
│   │
│   ├── PodcastPlayer:
│   │   ├── SpeakerAvatars: 两个圆形头像，当前说话者缩放+高亮
│   │   ├── AudioControls:
│   │   │   ├── PlayPauseButton
│   │   │   ├── ProgressBar (可点击 seek)
│   │   │   ├── TimeDisplay: "02:15 / 08:30"
│   │   │   └── SpeedSelector: 0.5x | 0.75x | 1x | 1.25x | 1.5x | 2x
│   │   └── <audio ref={audioRef} src={audioUrl} />
│   │
│   └── TranscriptPanel:
│       ├── 滚动区域，每个 segment 一行
│       ├── 按 speaker 着色（host=blue, guest=green）
│       ├── 当前播放段落高亮（DOM ref mutation，非 React state）
│       ├── 点击任意段落 → audio.currentTime = segment.startTime
│       └── 自动滚动跟随当前段落
│
├── GeneratePanel (CTA / 重新生成时显示):
│   ├── LLM 模型选择（复用现有 ModelSelector）
│   ├── Host TTS 模型 + Voice 选择
│   ├── Guest TTS 模型 + Voice 选择
│   └── Generate 按钮
```

##### 6.2 字幕同步核心逻辑

**性能关键：** 使用 DOM ref mutation 而非 React state 驱动 re-render。

```typescript
// 核心逻辑（参考 Metaview blog 模式）
const transcriptRef = useRef<HTMLDivElement>(null);
const activeIndexRef = useRef<number>(-1);

useEffect(() => {
  const audio = audioRef.current;
  if (!audio || !segments.length) return;

  const onTimeUpdate = () => {
    const time = audio.currentTime;
    // 二分查找当前段落
    const idx = findActiveSegment(segments, time);
    if (idx === activeIndexRef.current) return;

    // 移除旧高亮（DOM mutation）
    const oldEl = transcriptRef.current?.querySelector(`[data-idx="${activeIndexRef.current}"]`);
    if (oldEl) oldEl.classList.remove("active");

    // 添加新高亮
    const newEl = transcriptRef.current?.querySelector(`[data-idx="${idx}"]`);
    if (newEl) {
      newEl.classList.add("active");
      newEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    activeIndexRef.current = idx;
  };

  audio.addEventListener("timeupdate", onTimeUpdate);
  return () => audio.removeEventListener("timeupdate", onTimeUpdate);
}, [segments]);
```

##### 6.3 TabContentRenderer 集成

**修改文件：** `frontend/components/video/TabContentRenderer.tsx`

```typescript
// 顶部：动态导入
const PodcastTab = dynamic(
    () => import("@/components/features/PodcastTab").then((mod) => mod.PodcastTab),
    { loading: LoadingSpinner }
);

// TabContentProps：
refreshPodcast: number;

// switch case（替换 FeaturePlaceholder）：
case "podcast":
    return (
        <PodcastTab
            videoId={videoId}
            onSeek={onSeek}
            refreshTrigger={refreshPodcast}
        />
    );
```

---

#### Phase 7: 测试

##### 7.1 后端单元测试

**新建文件：** `tests/unit/use_cases/test_podcast.py`

```python
class TestDialogueItemDTO:
    """DTO 序列化测试。"""
    def test_to_dict(self): ...
    def test_from_dict(self): ...
    def test_from_dict_defaults(self): ...

class TestPodcastSegmentDTO:
    """Segment DTO 测试。"""
    def test_to_dict(self): ...
    def test_from_dict(self): ...

class TestPodcastUseCase:
    """用例集成测试（mock LLM + TTS）。"""
    def test_generate_three_stage_pipeline(self):
        """验证三阶段 LLM 调用顺序。"""
        ...
    def test_generate_dual_tts(self):
        """验证 host 和 guest 使用不同 TTS 模型。"""
        ...
    def test_tts_failure_fallback(self):
        """单个 TTS 失败时生成静音。"""
        ...
    def test_tts_high_failure_rate_aborts(self):
        """>50% TTS 失败时中止整个任务。"""
        ...
    def test_timestamp_calculation(self):
        """验证时间戳连续性（含间隔）。"""
        ...
    def test_dialogue_validation_truncates(self):
        """对话超过 MAX_DIALOGUE_ITEMS 时截断。"""
        ...
    def test_empty_dialogue_raises(self):
        """空对话抛出错误。"""
        ...

class TestPodcastRoute:
    """API 路由测试。"""
    def test_get_returns_404_when_not_found(self): ...
    def test_get_returns_result(self): ...
    def test_generate_returns_202(self): ...
    def test_audio_streams_file(self): ...
    def test_audio_returns_404_when_missing(self): ...
```

##### 7.2 Prompt 测试

**新建文件：** `tests/unit/use_cases/test_podcast_prompts.py`

```python
class TestPodcastDialoguePrompts:
    def test_system_prompt_includes_roles(self): ...
    def test_user_prompt_includes_knowledge_items(self): ...
    def test_custom_role_descriptions(self): ...

class TestPodcastDramatizePrompts:
    def test_system_prompt_includes_rewrite_rules(self): ...
    def test_user_prompt_includes_dialogue(self): ...
```

---

## Acceptance Criteria

### Functional Requirements

- [ ] **生成：** 用户在 Podcast tab 配置 LLM + 双 TTS 后点击 "Generate"，异步生成播客
- [ ] **三阶段管线：** 知识提取 → 对话脚本 → 戏剧化改写 → TTS 合成 → 音频合并
- [ ] **双角色 TTS：** Host 和 Guest 使用不同的 TTS 模型/voice
- [ ] **音频播放：** 完整的播客播放器（播放/暂停、进度条、时间显示、速度调节）
- [ ] **字幕同步：** 当前播放段落高亮 + 自动滚动跟随
- [ ] **分段跳转：** 点击任意对话段落跳转到音频对应位置
- [ ] **角色可视化：** 两个头像区域，当前说话者高亮/缩放动画
- [ ] **可配置角色：** 通过 prompt template 自定义 host_role / guest_role
- [ ] **多语言支持：** 切换语言后显示对应语言的播客或 Generate CTA
- [ ] **异步任务：** 通过 SSE 通知前端，支持页面刷新后恢复
- [ ] **重新生成：** 支持重新生成（覆盖旧数据）

### Non-Functional Requirements

- [ ] **架构一致性：** 对齐现有 Clean Architecture 模式
- [ ] **TTS 容错：** 单个 TTS 失败时生成静音；>50% 失败中止
- [ ] **对话上限：** 最多 100 条对话段落（防止成本失控）
- [ ] **字幕性能：** 使用 DOM ref mutation 而非 React state（避免不必要的 re-render）
- [ ] **间隔静音：** 对话转换间 300ms 默认间隔，支持配置

### Quality Gates

- [ ] `uv run pytest tests/unit/use_cases/test_podcast.py -q` 全部通过
- [ ] `uv run pytest tests/unit/use_cases/test_podcast_prompts.py -q` 全部通过
- [ ] 现有测试不受影响
- [ ] `cd frontend && npm run -s typecheck` 通过

## Dependencies & Prerequisites

- 现有的 `cheatsheet_extraction` prompt 和知识提取流水线（Stage 1 复用）
- `TTSProviderProtocol` + `AudioProcessorProtocol`（TTS 合成 + 音频处理）
- `ParallelRunnerProtocol`（并行 TTS）
- `useSSEGenerationRetry` hook（前端异步状态管理）
- FFmpeg（音频转码和合并）

## Risk Analysis & Mitigation

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 生成对话质量不稳定 | 播客不自然/内容偏差 | 三阶段管线：Stage 3 专门改善自然度 |
| TTS API 成本高（100+ 次调用） | 意外高额费用 | 对话上限 100 条 + rate_limit 装饰器 |
| 不同 TTS 模型采样率不一致 | 音频合并失败 | 统一转码为 24kHz WAV（_synthesize_to_wav 模式） |
| 长内容生成超时 | 任务被 TaskManager 超时 kill | 估算 4-6 min，设置 15 min 超时 |
| 对话 JSON 解析失败（Stage 间传递） | 管线中断 | parse_llm_json 的 fallback + 每个 stage 独立 try/catch |
| 并发生成同一 content 的播客 | 文件覆盖/损坏 | 路由层检查 in-flight 任务，拒绝重复提交 |

## Future Considerations

- **长内容分块：** 参考 Podcastfy 的 Content Chunking with Contextual Linking 策略
- **播客独立提取 prompt：** 添加 `podcast_extraction` func_id 以支持播客专属的内容提取调优
- **Voice ID 发现 API：** 新增 `/api/config/tts-voices?model=...` 端点，列出可用 voice
- **背景音乐：** 添加可选的 intro/outro 音乐叠加
- **Dia TTS 集成：** 集成 Nari Labs Dia 以支持原生多角色 TTS（无需手动合并）
- **进度报告细化：** 在 SSE 中报告 Stage 级别进度（0-20% 提取, 20-55% 对话+戏剧化, 55-90% TTS, 90-100% 合并）

## References & Research

### Internal References

- Voiceover UseCase（TTS + 音频合并参考）: `src/deeplecture/use_cases/voiceover.py`
- SlideLecture UseCase（LLM + TTS 管线参考）: `src/deeplecture/use_cases/slide_lecture.py:103-437`
- Quiz UseCase（Clean Architecture 模式参考）: `src/deeplecture/use_cases/quiz.py:77-491`
- Cheatsheet 知识提取: `src/deeplecture/use_cases/cheatsheet.py:278-326`
- KnowledgeItem DTO: `src/deeplecture/use_cases/dto/cheatsheet.py:16-35`
- TTS Protocol: `src/deeplecture/use_cases/interfaces/services.py`
- TTS Provider Protocol: `src/deeplecture/use_cases/interfaces/tts_provider.py`
- Audio Processor Protocol: `src/deeplecture/use_cases/interfaces/audio.py`
- FFmpeg 音频处理: `src/deeplecture/infrastructure/gateways/ffmpeg_audio.py`
- Prompt Registry: `src/deeplecture/use_cases/prompts/registry.py:406-653`
- Template Definitions: `src/deeplecture/use_cases/prompts/template_definitions.py`
- Model Resolution: `src/deeplecture/presentation/api/shared/model_resolution.py`
- DI Container: `src/deeplecture/di/container.py:196-638`
- SSE 刷新触发器: `frontend/hooks/useVideoPageState.ts:257-404`
- Tab 注册: `frontend/stores/tabLayoutStore.ts:6-54`
- TabContentRenderer: `frontend/components/video/TabContentRenderer.tsx:421-422`
- Context Mode 统一教训: `docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md`
- Brainstorm 文档: `docs/brainstorms/2026-03-03-podcast-brainstorm.md`

### External References

- [souzatharsis/podcastfy](https://github.com/souzatharsis/podcastfy) — 最完整的开源 podcast 生成
- [mozilla-ai/document-to-podcast](https://github.com/mozilla-ai/document-to-podcast) — Mozilla AI 本地 podcast
- [meta-llama/NotebookLlama](https://github.com/meta-llama/llama-recipes/tree/main/recipes/quickstart/NotebookLlama) — Meta 四阶段参考管线
- [Together.ai PDF-to-Podcast](https://docs.together.ai/docs/open-notebooklm-pdf-to-podcast) — Pydantic 结构化输出 + scratchpad
- [Nicole Hennig — Reverse Engineering NotebookLM](https://nicolehennig.com/notebooklm-reverse-engineering-the-system-prompt-for-audio-overviews/)
- [Meeting-BaaS/transcript-seeker](https://github.com/Meeting-BaaS/transcript-seeker) — 转录同步 UI
- [wavesurfer.js](https://github.com/katspaugh/wavesurfer.js) — 波形可视化
- [Metaview — Syncing Transcript with Audio in React](https://www.metaview.ai/resources/blog/syncing-a-transcript-with-audio-in-react) — 性能优化
- [nari-labs/dia](https://github.com/nari-labs/dia) — 对话 TTS 模型

### New Files to Create

| File | Purpose |
|------|---------|
| `src/deeplecture/use_cases/podcast.py` | PodcastUseCase |
| `src/deeplecture/use_cases/dto/podcast.py` | DTOs |
| `src/deeplecture/use_cases/interfaces/podcast.py` | PodcastStorageProtocol |
| `src/deeplecture/use_cases/prompts/podcast.py` | Prompt builder functions |
| `src/deeplecture/infrastructure/repositories/fs_podcast_storage.py` | FS 存储 |
| `src/deeplecture/presentation/api/routes/podcast.py` | API 路由 |
| `frontend/lib/api/podcast.ts` | API 客户端 |
| `frontend/components/features/PodcastTab.tsx` | 播客播放器组件 |
| `tests/unit/use_cases/test_podcast.py` | Use case 测试 |
| `tests/unit/use_cases/test_podcast_prompts.py` | Prompt 测试 |

### Files to Modify

| File | Change |
|------|--------|
| `src/deeplecture/use_cases/interfaces/parallel.py` | 添加 `"podcast_tts"` 到 ParallelGroup |
| `src/deeplecture/use_cases/interfaces/__init__.py` | 导出 PodcastStorageProtocol |
| `src/deeplecture/use_cases/prompts/registry.py` | 注册 podcast_dialogue + podcast_dramatize builders |
| `src/deeplecture/use_cases/prompts/template_definitions.py` | 添加 placeholder rules |
| `src/deeplecture/infrastructure/repositories/__init__.py` | 导出 FsPodcastStorage |
| `src/deeplecture/infrastructure/__init__.py` | 导出 FsPodcastStorage |
| `src/deeplecture/di/container.py` | 注册 podcast_storage + podcast_usecase |
| `src/deeplecture/presentation/api/routes/__init__.py` | 导出 podcast_bp |
| `src/deeplecture/presentation/api/app.py` | 注册 blueprint |
| `src/deeplecture/presentation/api/shared/model_resolution.py` | 添加 podcast task key |
| `frontend/hooks/useVideoPageState.ts` | 添加 refreshPodcast + SSE handler |
| `frontend/components/video/VideoPageClient.tsx` | 传递 refreshPodcast |
| `frontend/components/video/TabContentRenderer.tsx` | 渲染 PodcastTab |
