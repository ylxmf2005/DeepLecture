# Notes Read-Aloud Feature Brainstorm

**Date:** 2026-03-03
**Status:** Decided
**Author:** EthanLee

## What We're Building

为 DeepLecture 的 Notes 功能添加 **朗读/播放** 能力，用户可以让 AI 生成的笔记以语音形式逐句朗读。支持多语言朗读，当笔记语言与用户期望的朗读语言不同时，自动翻译后再朗读。

### 核心功能

1. **混合模式朗读** — 立即逐句流式播放，同时缓存已合成的音频片段，重听时已缓存部分秒播
2. **多语言翻译朗读** — 用户可设置目标朗读语言（target language），当与笔记原文语言不同时，先通过 DeepL Free API 翻译再 TTS
3. **智能文本过滤** — 过滤 Markdown 标记、代码块、LaTeX 公式、URL、图片引用、HTML 标签等不可朗读内容，只保留纯自然语言文本
4. **按段落跳转** — 笔记每段开头有朗读跳转按钮，点击可跳到该段落开始朗读
5. **播放进度条** — 整篇笔记朗读带进度条，支持暂停/继续
6. **可配置 TTS 声音** — 在 config.yaml 中按语言配置 Edge TTS 声音，支持多种语言的默认声音映射

### 不做的事情（YAGNI）

- ❌ 音频文件持久化存储/下载（缓存仅在会话内有效）
- ❌ 前端声音选择器 UI（声音通过 config.yaml 配置）
- ❌ 多 TTS 引擎在 UI 层切换（默认 Edge TTS，通过配置切换）
- ❌ 朗读速度调节（v1 使用 TTS 默认语速）
- ❌ 背景音乐/音效
- ❌ 分享/导出音频

## Why This Approach

### 方案 A（已选）：独立用例 NoteReadAloud

新建一个独立的 `NoteReadAloudUseCase`，与现有 `VoiceoverUseCase` 平行。复用现有 `TTSProviderProtocol` 和 `EdgeTTS` 网关，新增 `TranslationProviderProtocol` 和 `TextFilterProtocol`。

```
用户点击朗读
  ↓
加载笔记内容 (Markdown)
  ↓
按段落拆分 → Paragraph[]
  ↓
每段: 智能文本过滤 → 纯文本句子[]
  ↓
(可选) 翻译: DeepL Free → 目标语言句子[]
  ↓
逐句 TTS 合成 (Edge TTS) → 音频片段[]
  ↓
SSE 流式推送音频片段 + 段落/句子索引
  ↓
前端: 逐句播放 + 缓存 + 进度条 + 段落高亮
```

**优点：**
- 职责清晰，不影响现有 voiceover 功能
- Voiceover 是基于字幕时间轴对齐的，与笔记朗读场景差异大，硬复用会增加不必要的复杂度
- 复用现有 TTS 基础设施（TTSProviderProtocol、EdgeTTS 网关）

### 被否决的方案

- **方案 B：扩展 VoiceoverUseCase** — Voiceover 是按字幕时间线对齐的，和笔记朗读的顺序文本流完全不同，硬塞进去会让两个场景互相干扰。
- **方案 C：通用 StreamingTTSService 抽象** — 目前只有笔记朗读一个消费者，过度抽象违反 YAGNI。

## Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 播放模式 | 混合模式（流式 + 缓存） | 即时开始播放，重听秒播 |
| TTS 引擎 | Edge TTS（默认，免费） | 项目已集成，质量好，零成本 |
| 翻译服务 | DeepL Free API（默认） | 翻译质量优秀，50 万字符/月免费 |
| 翻译场景 | 笔记语言 ≠ 用户设定的朗读语言时触发 | 简单明确的触发条件 |
| 文本过滤 | markdown + BeautifulSoup 组合 | 灵活控制过滤粒度，处理代码块/公式/URL |
| 声音配置 | config.yaml 按语言映射 Edge TTS 声音 | 运维友好，不暴露给终端用户 |
| 朗读范围 | 整篇 + 进度条 + 段落跳转按钮 | 完整的朗读体验 |
| 架构模式 | 独立用例，对齐 Clean Architecture | 不影响现有功能，代码风格统一 |
| 流式传输 | SSE（Server-Sent Events） | 项目已有 SSE 基础设施，前端可逐句接收播放 |

## 技术选型

### TTS: Edge TTS 声音配置

在 config.yaml 中为常见语言配置默认声音：

| 语言 | 代码 | 默认女声 | 默认男声 |
|------|------|----------|----------|
| 中文 | zh-CN | zh-CN-XiaoxiaoNeural | zh-CN-YunxiNeural |
| 英语 | en-US | en-US-AriaNeural | en-US-GuyNeural |
| 日语 | ja-JP | ja-JP-NanamiNeural | ja-JP-KeitaNeural |
| 韩语 | ko-KR | ko-KR-SunHiNeural | ko-KR-InJoonNeural |
| 法语 | fr-FR | fr-FR-DeniseNeural | fr-FR-HenriNeural |
| 德语 | de-DE | de-DE-KatjaNeural | de-DE-ConradNeural |
| 西班牙语 | es-ES | es-ES-ElviraNeural | es-ES-AlvaroNeural |

### 翻译: DeepL Free API

- **Python 库**: `pip install deepl`
- **免费额度**: 50 万字符/月
- **API Key**: 需用户自行注册，配置 `DEEPL_AUTH_KEY` 环境变量
- **端点**: `https://api-free.deepl.com`（Free key 自动判断）
- **支持语言**: 36 种，覆盖所有常见语言

### 文本过滤: Markdown → 纯文本

使用 `markdown` + `BeautifulSoup` 两步过滤：

1. `markdown.markdown(text)` → HTML
2. `BeautifulSoup(html).get_text()` → 纯文本
3. 额外正则清理: LaTeX (`$...$`, `$$...$$`)、URL、特殊符号
4. 空句子/纯符号句子跳过

## Data Model

### 后端 DTO

```python
@dataclass
class ReadAloudRequest:
    content_id: str
    target_language: str           # 朗读语言 (如 "en-US", "zh-CN")
    source_language: str | None = None  # 笔记原文语言 (None = 自动检测/不翻译)
    tts_model: str | None = None   # TTS 模型 (None = 使用配置默认值)
    start_paragraph: int = 0       # 从第几段开始 (用于段落跳转)

@dataclass
class ReadAloudSentence:
    paragraph_index: int           # 所属段落序号
    sentence_index: int            # 段落内句子序号
    original_text: str             # 原文
    spoken_text: str               # 实际朗读文本（可能是翻译后的）
    audio_data: bytes              # 音频数据 (MP3)

@dataclass
class ReadAloudParagraph:
    index: int                     # 段落序号
    title: str | None              # 段落标题 (如有 Markdown heading)
    sentence_count: int            # 句子数
```

### SSE 事件格式

```
event: paragraph_start
data: {"paragraph_index": 0, "title": "Introduction", "sentence_count": 5}

event: sentence_audio
data: {"paragraph_index": 0, "sentence_index": 0, "text": "...", "audio_base64": "..."}

event: paragraph_end
data: {"paragraph_index": 0}

event: read_aloud_complete
data: {"total_paragraphs": 10, "total_sentences": 42}
```

## 后端架构

### 新增文件

| 层 | 文件 | 描述 |
|----|------|------|
| DTO | `use_cases/dto/read_aloud.py` | `ReadAloudRequest`, `ReadAloudSentence`, `ReadAloudParagraph` |
| Interface | `use_cases/interfaces/translation.py` | `TranslationProviderProtocol` |
| Interface | `use_cases/interfaces/text_filter.py` | `TextFilterProtocol` |
| Use Case | `use_cases/read_aloud.py` | `ReadAloudUseCase` (主管线) |
| Gateway | `infrastructure/gateways/deepl_translation.py` | DeepL Free API 网关 |
| Shared | `infrastructure/shared/text_filter.py` | Markdown → 纯文本过滤实现 |
| Route | `presentation/api/routes/read_aloud.py` | SSE 流式朗读端点 |
| Config | `config/settings.py` | 扩展：`ReadAloudConfig`, `DeepLConfig`, 声音映射 |

### 修改文件

- `di/container.py` — 注册 translation_provider, text_filter, read_aloud_usecase
- `presentation/api/app.py` — 注册 read_aloud route
- `config.yaml` — 添加 read_aloud 配置区块 + 语言-声音映射

### 前端（暂不详细设计，留给 plan 阶段）

- Notes 组件中添加朗读播放控制 UI
- 段落跳转按钮
- 进度条 + 暂停/继续
- SSE 客户端接收音频片段并顺序播放

## Open Questions

1. **音频传输格式** — SSE 中传 base64 编码的音频片段，还是返回音频文件 URL？base64 更简单但数据量大。
2. **翻译缓存** — 翻译结果是否需要缓存到文件系统？相同笔记+相同语言的翻译可以复用。
3. **断句策略** — 中文句子用句号/问号/感叹号分句，英文用 sentence tokenizer？还是简单按标点分？
4. **DeepL Key 必须性** — 如果用户没配置 DeepL key，翻译功能降级为不可用？还是提供 fallback（如 Google Translate）？
5. **前端音频播放** — Web Audio API 还是简单的 `<audio>` 元素队列？

## 参考资料

- [edge-tts](https://github.com/rany2/edge-tts) — 免费 Edge TTS Python 库
- [deepl-python](https://github.com/DeepLcom/deepl-python) — DeepL 官方 Python SDK
- [Python-Markdown](https://python-markdown.github.io/) — Markdown → HTML 解析
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML → 纯文本提取
