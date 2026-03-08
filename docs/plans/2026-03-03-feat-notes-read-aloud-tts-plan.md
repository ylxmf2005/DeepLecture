---
title: "feat: Add notes read-aloud with streaming TTS and translation"
type: feat
date: 2026-03-03
brainstorm: docs/brainstorms/2026-03-03-notes-read-aloud-brainstorm.md
---

# feat: Add notes read-aloud with streaming TTS and translation

## Overview

为 DeepLecture 的 Notes 功能添加朗读/播放能力。用户可以让 AI 生成的笔记以语音形式逐句朗读，支持多语言朗读和跨语言翻译。采用混合模式：立即逐句流式播放 + 缓存已合成片段供重听。

核心流程：加载笔记 → Markdown 过滤 → (可选翻译) → 逐句 TTS → SSE 信号通知 → 前端 REST 拉取音频 → 顺序播放。

## Problem Statement / Motivation

DeepLecture 已有 Voiceover（配音）功能将字幕时间线转为同步音频，但 Notes（笔记）是独立生成的 Markdown 文档，无法使用 Voiceover 的字幕对齐机制。用户需要一种便捷的方式"听"笔记，尤其是：

- 通勤/运动时想回顾笔记内容
- 笔记用中文写的，但想用英文朗读来练习听力
- 边听边看，加深理解

## Proposed Solution

新建独立的 `ReadAloudUseCase`，复用现有 `TTSProviderProtocol` + `EdgeTTS` 网关，新增 `TranslationProviderProtocol`（DeepL Free）和 `MarkdownTextFilter`。

**音频传输架构：SSE 信号 + REST 拉取**
- SSE 用于逐句推送元数据（"第 N 句已准备好"）
- 前端收到信号后通过 REST 端点拉取该句的 MP3 音频
- 已拉取的音频由前端缓存，重听时秒播

**段落跳转：断开重连**
- 用户点击某段落的朗读按钮时，关闭当前 SSE 连接
- 重新建立带 `start_paragraph` 参数的新连接
- 已缓存的音频仍然有效

## Technical Approach

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend                                                     │
│                                                               │
│  NotesPanel.tsx                                               │
│    ├── ReadAloudControls (play/pause/stop + progress bar)     │
│    ├── ParagraphPlayButton (每段开头的跳转按钮)                │
│    └── useReadAloud() hook                                    │
│           ├── SSE: EventSource(/api/read-aloud/stream/{id})   │
│           ├── REST: fetch(/api/read-aloud/audio/{id}/{idx})   │
│           └── AudioContext: 顺序播放 + 缓存                    │
└──────────────────────────────────────────────────────────────┘
                            │
┌──────────────────────────────────────────────────────────────┐
│  Backend                                                      │
│                                                               │
│  routes/read_aloud.py                                         │
│    ├── GET /stream/{content_id}  → SSE 流                     │
│    └── GET /audio/{content_id}/{sentence_key}  → MP3 bytes    │
│                            │                                  │
│  ReadAloudUseCase.generate_stream()                           │
│    ├── NoteStorage.load()  → Markdown 内容                    │
│    ├── MarkdownTextFilter.filter()  → 纯文本段落/句子          │
│    ├── (可选) TranslationProvider.translate()  → 翻译         │
│    ├── TTSProvider.get().synthesize()  → MP3 bytes            │
│    └── ReadAloudCacheStorage.save()  → 临时缓存               │
│                            │                                  │
│  EventPublisher.publish()  → SSE 信号                         │
└──────────────────────────────────────────────────────────────┘
```

### Implementation Phases

---

#### Phase 1: 基础设施层 — 文本过滤 + 翻译网关 + 配置

**目标：** 建立文本过滤器、DeepL 翻译网关、语言-声音映射配置。

##### 1.1 Markdown 文本过滤器

**新增文件：** `src/deeplecture/use_cases/interfaces/text_filter.py`

```python
class TextFilterProtocol(Protocol):
    def filter_to_sentences(self, markdown_text: str) -> list[FilteredParagraph]: ...

@dataclass
class FilteredParagraph:
    index: int
    title: str | None          # Markdown heading 文本（如有）
    sentences: list[str]       # 过滤后的纯文本句子列表
```

**新增文件：** `src/deeplecture/infrastructure/shared/markdown_text_filter.py`

过滤流程：
1. `markdown.markdown(text)` → HTML
2. 移除 `<pre><code>` 块（代码）
3. 移除 `<img>` 标签（图片）
4. `BeautifulSoup(html).get_text()` → 纯文本
5. 正则清理：LaTeX (`$...$`, `$$...$$`) → 移除、URL → 移除、HTML 实体 → 解码
6. 按空行分段落，提取 heading 作为段落标题
7. 每段按句号/问号/感叹号（含中日韩标点 `。？！`）分句
8. 过滤空句子和纯符号句子（最小长度 ≥ 2 个字符）

**新增依赖（pyproject.toml）：** `markdown>=3.5`, `beautifulsoup4>=4.12`

##### 1.2 翻译网关

**新增文件：** `src/deeplecture/use_cases/interfaces/translation.py`

```python
class TranslationProviderProtocol(Protocol):
    def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> str: ...
    def translate_batch(self, texts: list[str], target_lang: str, source_lang: str | None = None) -> list[str]: ...
    def is_available(self) -> bool: ...
```

**新增文件：** `src/deeplecture/infrastructure/gateways/deepl_translation.py`

```python
class DeepLTranslator:
    """DeepL Free API translation gateway."""

    def __init__(self, config: DeepLConfig):
        self._translator = deepl.Translator(config.auth_key) if config.auth_key else None

    def translate(self, text, target_lang, source_lang=None) -> str: ...
    def translate_batch(self, texts, target_lang, source_lang=None) -> list[str]: ...
    def is_available(self) -> bool:
        return self._translator is not None
```

语言代码映射（内部 ISO 639-1 → DeepL 格式）：
- `en` → `EN-US`, `zh` → `ZH-HANS`, `ja` → `JA`, `ko` → `KO`, `de` → `DE`, `fr` → `FR`, `es` → `ES`

**新增依赖（pyproject.toml）：** `deepl>=1.18`

##### 1.3 配置扩展

**修改文件：** `src/deeplecture/config/settings.py`

新增配置类：

```python
class ReadAloudVoiceConfig(BaseModel):
    """语言到 Edge TTS 声音的映射"""
    language: str              # ISO 639-1, e.g. "en"
    voice: str                 # Edge TTS voice ID, e.g. "en-US-AriaNeural"

class DeepLConfig(BaseModel):
    auth_key: str = ""         # 空字符串 = 未配置

class ReadAloudConfig(BaseModel):
    voices: list[ReadAloudVoiceConfig] = []   # 语言-声音映射
    default_voice: str = "en-US-AriaNeural"   # 找不到映射时的 fallback
    min_sentence_length: int = 2              # 最小句子长度（字符）
    max_concurrent_tts: int = 3               # 并行 TTS 合成数
    deepl: DeepLConfig = DeepLConfig()
```

**修改文件：** `config/conf.yaml`

```yaml
read_aloud:
  default_voice: "en-US-AriaNeural"
  max_concurrent_tts: 3
  voices:
    - language: "zh"
      voice: "zh-CN-XiaoxiaoNeural"
    - language: "en"
      voice: "en-US-AriaNeural"
    - language: "ja"
      voice: "ja-JP-NanamiNeural"
    - language: "ko"
      voice: "ko-KR-SunHiNeural"
    - language: "fr"
      voice: "fr-FR-DeniseNeural"
    - language: "de"
      voice: "de-DE-KatjaNeural"
    - language: "es"
      voice: "es-ES-ElviraNeural"
  deepl:
    auth_key: ""  # 用户需自行配置 DEEPL_AUTH_KEY 环境变量
```

---

#### Phase 2: 应用层 — DTO + UseCase

**目标：** 实现 ReadAloudUseCase 核心管线。

##### 2.1 DTO 定义

**新增文件：** `src/deeplecture/use_cases/dto/read_aloud.py`

```python
@dataclass
class ReadAloudRequest:
    content_id: str
    target_language: str           # 朗读语言 ISO 639-1 (如 "en", "zh")
    source_language: str | None = None  # 笔记原文语言 (None = 不翻译)
    tts_model: str | None = None   # TTS 模型名 (None = 用 task_models 配置)
    start_paragraph: int = 0       # 从第几段开始 (用于段落跳转)

@dataclass
class ReadAloudMeta:
    """SSE 首事件：朗读元数据"""
    total_paragraphs: int
    total_sentences: int
    paragraphs: list[ParagraphMeta]

@dataclass
class ParagraphMeta:
    index: int
    title: str | None
    sentence_count: int

@dataclass
class SentenceReady:
    """SSE 事件：某句音频已准备好"""
    paragraph_index: int
    sentence_index: int
    sentence_key: str              # 用于 REST 拉取的唯一键 "p{para}_s{sent}"
    original_text: str             # 原文
    spoken_text: str               # 实际朗读文本（可能翻译后的）

@dataclass
class ReadAloudComplete:
    """SSE 事件：朗读完成"""
    total_paragraphs: int
    total_sentences: int
    total_errors: int
```

##### 2.2 音频缓存接口 + 实现

**新增文件：** `src/deeplecture/use_cases/interfaces/read_aloud.py`

```python
class ReadAloudCacheProtocol(Protocol):
    def save_audio(self, content_id: str, sentence_key: str, audio_data: bytes) -> None: ...
    def load_audio(self, content_id: str, sentence_key: str) -> bytes | None: ...
    def clear(self, content_id: str) -> None: ...
```

**新增文件：** `src/deeplecture/infrastructure/repositories/fs_read_aloud_cache.py`

存储路径：`content/{content_id}/read_aloud_cache/{sentence_key}.mp3`

- 临时性质，可随时清除
- 笔记更新时，清除对应 content_id 的缓存

##### 2.3 ReadAloudUseCase

**新增文件：** `src/deeplecture/use_cases/read_aloud.py`

```python
class ReadAloudUseCase:
    def __init__(
        self,
        note_storage: NoteStorageProtocol,
        text_filter: TextFilterProtocol,
        translation_provider: TranslationProviderProtocol,
        tts_provider: TTSProviderProtocol,
        cache: ReadAloudCacheProtocol,
        event_publisher: EventPublisherProtocol,
        path_resolver: PathResolverProtocol,
        config: ReadAloudConfig,
    ): ...

    def generate_stream(self, request: ReadAloudRequest) -> None:
        """主管线：加载笔记 → 过滤 → (翻译) → 逐句TTS → 缓存 → 发SSE信号"""

        # 1. 加载笔记
        result = self.note_storage.load(request.content_id)
        if not result:
            raise NoteNotFoundError(request.content_id)
        markdown_content, _ = result

        # 2. 过滤 + 分句
        paragraphs = self.text_filter.filter_to_sentences(markdown_content)
        if not paragraphs or all(len(p.sentences) == 0 for p in paragraphs):
            raise NoSpeakableContentError(request.content_id)

        # 3. 发送元数据事件
        # ... publish meta event with total counts

        # 4. 从 start_paragraph 开始逐段逐句处理
        for para in paragraphs[request.start_paragraph:]:
            # publish paragraph_start event
            for sent_idx, sentence in enumerate(para.sentences):
                # 4a. 翻译（如果需要）
                spoken_text = sentence
                if request.source_language and request.target_language != request.source_language:
                    if self.translation_provider.is_available():
                        spoken_text = self.translation_provider.translate(
                            sentence, target_lang=request.target_language,
                            source_lang=request.source_language
                        )

                # 4b. 选择对应语言的 TTS 声音
                voice = self._resolve_voice(request.target_language)

                # 4c. TTS 合成
                tts = self.tts_provider.get(request.tts_model)
                audio_data = tts.synthesize(spoken_text, voice=voice)

                # 4d. 缓存音频
                sentence_key = f"p{para.index}_s{sent_idx}"
                self.cache.save_audio(request.content_id, sentence_key, audio_data)

                # 4e. 发送 SSE 信号
                # publish sentence_ready event

            # publish paragraph_end event

        # 5. 发送完成事件
```

关键设计点：
- `_resolve_voice(language)`: 从 `ReadAloudConfig.voices` 中查找语言对应的声音 ID
- 错误处理：单句 TTS 失败不中断整个流程，跳过并发 `sentence_error` 事件
- 翻译失败：降级到原文朗读，发 `translation_fallback` 警告事件

---

#### Phase 3: 表示层 — API 路由

**目标：** 实现 SSE 流端点和音频 REST 端点。

##### 3.1 朗读路由

**新增文件：** `src/deeplecture/presentation/api/routes/read_aloud.py`

```python
bp = Blueprint("read_aloud", __name__, url_prefix="/api/read-aloud")

@bp.route("/stream/<content_id>", methods=["GET"])
def stream_read_aloud(content_id: str) -> FlaskResponse:
    """SSE 流：逐句推送朗读信号"""
    content_id = validate_content_id(content_id)
    target_language = request.args.get("target_language", "en")
    source_language = request.args.get("source_language")  # None = 不翻译
    tts_model = request.args.get("tts_model")
    start_paragraph = int(request.args.get("start_paragraph", 0))

    container = get_container()

    # 在后台线程启动生成
    req = ReadAloudRequest(
        content_id=content_id,
        target_language=target_language,
        source_language=source_language,
        tts_model=tts_model,
        start_paragraph=start_paragraph,
    )
    thread = threading.Thread(
        target=container.read_aloud_usecase.generate_stream,
        args=(req,),
        daemon=True,
    )
    thread.start()

    # SSE 流
    return FlaskResponse(
        stream_with_context(
            container.event_publisher.stream(
                f"read_aloud:{content_id}",
                timeout=30.0,
                retry_ms=3000,
            )
        ),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@bp.route("/audio/<content_id>/<sentence_key>", methods=["GET"])
def get_sentence_audio(content_id: str, sentence_key: str) -> FlaskResponse:
    """REST 端点：拉取单句 MP3 音频"""
    content_id = validate_content_id(content_id)
    container = get_container()

    audio_data = container.read_aloud_cache.load_audio(content_id, sentence_key)
    if not audio_data:
        return FlaskResponse("Audio not found", status=404)

    return FlaskResponse(
        audio_data,
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Length": str(len(audio_data)),
        },
    )
```

SSE 事件类型：
| 事件 | 数据 | 说明 |
|------|------|------|
| `read_aloud_meta` | `{total_paragraphs, total_sentences, paragraphs: [...]}` | 首事件，总量信息 |
| `paragraph_start` | `{paragraph_index, title, sentence_count}` | 段落开始 |
| `sentence_ready` | `{paragraph_index, sentence_index, sentence_key, original_text, spoken_text}` | 某句音频已就绪 |
| `sentence_error` | `{paragraph_index, sentence_index, error}` | 单句合成失败 |
| `translation_fallback` | `{paragraph_index, sentence_index, reason}` | 翻译降级警告 |
| `paragraph_end` | `{paragraph_index}` | 段落结束 |
| `read_aloud_complete` | `{total_paragraphs, total_sentences, total_errors}` | 全部完成 |
| `read_aloud_error` | `{error, detail}` | 致命错误（如笔记不存在） |

##### 3.2 路由注册

**修改文件：** `src/deeplecture/presentation/api/app.py`

```python
from deeplecture.presentation.api.routes.read_aloud import bp as read_aloud_bp
app.register_blueprint(read_aloud_bp)
```

---

#### Phase 4: DI 容器注册

**修改文件：** `src/deeplecture/di/container.py`

新增属性：

```python
@property
def read_aloud_config(self) -> ReadAloudConfig:
    return self._settings.read_aloud

@property
def deepl_translator(self) -> DeepLTranslator:
    if "deepl_translator" not in self._cache:
        self._cache["deepl_translator"] = DeepLTranslator(
            config=self._settings.read_aloud.deepl
        )
    return self._cache["deepl_translator"]

@property
def markdown_text_filter(self) -> MarkdownTextFilter:
    if "markdown_text_filter" not in self._cache:
        self._cache["markdown_text_filter"] = MarkdownTextFilter(
            min_sentence_length=self._settings.read_aloud.min_sentence_length
        )
    return self._cache["markdown_text_filter"]

@property
def read_aloud_cache(self) -> FsReadAloudCache:
    if "read_aloud_cache" not in self._cache:
        self._cache["read_aloud_cache"] = FsReadAloudCache(self.path_resolver)
    return self._cache["read_aloud_cache"]

@property
def read_aloud_usecase(self) -> ReadAloudUseCase:
    if "read_aloud_uc" not in self._cache:
        self._cache["read_aloud_uc"] = ReadAloudUseCase(
            note_storage=self.note_storage,
            text_filter=self.markdown_text_filter,
            translation_provider=self.deepl_translator,
            tts_provider=self.tts_provider,
            cache=self.read_aloud_cache,
            event_publisher=self.event_publisher,
            path_resolver=self.path_resolver,
            config=self.read_aloud_config,
        )
    return self._cache["read_aloud_uc"]
```

---

#### Phase 5: 前端实现

**目标：** 在 NotesPanel 中集成朗读 UI。

##### 5.1 API 客户端

**新增文件：** `frontend/lib/api/readAloud.ts`

```typescript
export const createReadAloudEventSource = (
  contentId: string,
  params: {
    target_language: string;
    source_language?: string;
    tts_model?: string;
    start_paragraph?: number;
  }
): EventSource => {
  const query = new URLSearchParams({
    target_language: params.target_language,
    ...(params.source_language && { source_language: params.source_language }),
    ...(params.tts_model && { tts_model: params.tts_model }),
    ...(params.start_paragraph !== undefined && { start_paragraph: String(params.start_paragraph) }),
  });
  return new EventSource(`${API_BASE_URL}/api/read-aloud/stream/${contentId}?${query}`);
};

export const fetchSentenceAudio = async (
  contentId: string,
  sentenceKey: string
): Promise<ArrayBuffer> => {
  const res = await fetch(`${API_BASE_URL}/api/read-aloud/audio/${contentId}/${sentenceKey}`);
  if (!res.ok) throw new Error(`Audio fetch failed: ${res.status}`);
  return res.arrayBuffer();
};
```

##### 5.2 useReadAloud Hook

**新增文件：** `frontend/hooks/useReadAloud.ts`

核心状态机：

```
IDLE → LOADING → PLAYING ⇄ PAUSED → IDLE
                    ↓
                 STOPPED → IDLE
```

主要逻辑：
- `play(targetLang, sourceLang?)`: 建立 SSE 连接，开始接收信号
- `pause()`: 暂停 AudioContext，保持 SSE 连接
- `resume()`: 恢复 AudioContext
- `stop()`: 关闭 SSE 连接，重置进度，保留已缓存音频
- `jumpToParagraph(index)`: 关闭当前 SSE，以 `start_paragraph=index` 重连
- SSE `onmessage`: 解析事件类型，收到 `sentence_ready` 时 fetch 音频并排入播放队列
- 播放队列：`AudioContext.decodeAudioData()` → `AudioBufferSourceNode` 顺序播放
- 前端缓存：`Map<sentenceKey, AudioBuffer>` 内存缓存，重听时直接取用

##### 5.3 UI 组件

**修改文件：** `frontend/components/video/NotesPanel.tsx`

在笔记面板顶部添加：

```
┌─────────────────────────────────────┐
│ [▶ Play] [⏸ Pause] [⏹ Stop]       │
│ [========●==========] 12/42 句      │
│ 🌐 朗读语言: [English ▾]           │
│     翻译自: [中文 ▾] (可选)         │
└─────────────────────────────────────┘
```

每个段落标题旁添加小播放按钮 `[▶]`，点击跳转到该段落朗读。

当前正在朗读的句子在笔记文本中高亮显示（DOM ref mutation，不用 React state 驱动 re-render，参考 podcast 的字幕同步模式）。

---

## Acceptance Criteria

### 功能需求

- [x] 用户可以点击播放按钮开始朗读整篇笔记
- [x] 朗读逐句进行，当前句子在笔记中高亮
- [x] 进度条显示已朗读/总句子数，可视化进度
- [x] 暂停/继续/停止按钮正常工作
- [x] 每个段落开头有跳转按钮，点击可跳到该段落朗读
- [ ] 朗读语言可选择（下拉框）
- [x] 当选择的朗读语言与笔记语言不同时，自动翻译后朗读
- [x] Markdown 代码块、LaTeX 公式、URL、图片等不可朗读内容被正确过滤
- [x] TTS 使用 Edge TTS，声音按 config.yaml 中的语言映射选择
- [x] 已播放的音频缓存在前端，重听时秒播无需重新合成

### 错误处理

- [x] 笔记未生成时，显示"请先生成笔记"提示
- [x] 笔记过滤后无可朗读内容时，显示"没有可朗读的内容"提示
- [x] DeepL 未配置时，翻译选项不可用（仍可同语言朗读）
- [x] 单句 TTS 失败时跳过该句继续朗读，UI 显示跳过标记
- [ ] SSE 断连时自动重连

### 配置

- [x] config.yaml 中可配置 7 种语言的默认 Edge TTS 声音
- [x] config.yaml 中可配置 DeepL API key
- [x] TTS 模型通过 `task_models.note_read_aloud` 配置

## Dependencies & Risks

### 新增依赖

| 包名 | 版本 | 用途 | 大小 |
|------|------|------|------|
| `markdown` | >=3.5 | Markdown → HTML 解析 | 轻量 |
| `beautifulsoup4` | >=4.12 | HTML → 纯文本提取 | 轻量 |
| `deepl` | >=1.18 | DeepL 翻译 API | 轻量 |

### 风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| DeepL Free 50 万字符/月额度不够 | 翻译功能不可用 | 翻译功能可选，不影响同语言朗读；未来可接入其他翻译 API |
| Edge TTS 服务不稳定 | 部分句子合成失败 | 复用现有重试机制（TTSConfig.max_retries=3），失败句子跳过 |
| 长笔记（100+ 段落）SSE 队列溢出 | 音频丢失 | 控制 TTS 并发数（max_concurrent_tts），SSE 队列设置合理大小 |
| 浏览器音频自动播放策略 | 首次播放被阻止 | Play 按钮需用户点击，满足浏览器 user gesture 要求 |

## 新增/修改文件清单

### 新增文件（后端）

| 文件 | 描述 |
|------|------|
| `src/deeplecture/use_cases/dto/read_aloud.py` | DTO 数据类 |
| `src/deeplecture/use_cases/interfaces/text_filter.py` | TextFilterProtocol |
| `src/deeplecture/use_cases/interfaces/translation.py` | TranslationProviderProtocol |
| `src/deeplecture/use_cases/interfaces/read_aloud.py` | ReadAloudCacheProtocol |
| `src/deeplecture/use_cases/read_aloud.py` | ReadAloudUseCase |
| `src/deeplecture/infrastructure/shared/markdown_text_filter.py` | Markdown → 纯文本过滤 |
| `src/deeplecture/infrastructure/gateways/deepl_translation.py` | DeepL 翻译网关 |
| `src/deeplecture/infrastructure/repositories/fs_read_aloud_cache.py` | 文件系统音频缓存 |
| `src/deeplecture/presentation/api/routes/read_aloud.py` | API 路由 |

### 新增文件（前端）

| 文件 | 描述 |
|------|------|
| `frontend/lib/api/readAloud.ts` | API 客户端 |
| `frontend/hooks/useReadAloud.ts` | 朗读状态管理 hook |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/deeplecture/config/settings.py` | 新增 ReadAloudConfig, DeepLConfig, ReadAloudVoiceConfig |
| `config/conf.yaml` | 新增 read_aloud 配置区块 |
| `src/deeplecture/di/container.py` | 注册 read_aloud 相关组件 |
| `src/deeplecture/presentation/api/app.py` | 注册 read_aloud blueprint |
| `frontend/components/video/NotesPanel.tsx` | 集成朗读 UI 控件 |
| `pyproject.toml` | 新增 markdown, beautifulsoup4, deepl 依赖 |

## References & Research

### Internal References

- SSE 基础设施: `src/deeplecture/presentation/sse/events.py` — EventPublisher
- Edge TTS 网关: `src/deeplecture/infrastructure/gateways/tts.py:32-92`
- TTS Provider: `src/deeplecture/infrastructure/providers/tts_provider.py`
- Note Storage: `src/deeplecture/infrastructure/repositories/fs_note_storage.py`
- SSE 路由模式: `src/deeplecture/presentation/api/routes/task.py:59-90`
- DI 容器: `src/deeplecture/di/container.py`
- 配置: `src/deeplecture/config/settings.py`
- Voiceover 错误恢复: `src/deeplecture/use_cases/voiceover.py:278-371`
- Context Mode 统一: `docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md`

### External References

- [edge-tts](https://github.com/rany2/edge-tts) — Edge TTS Python 库
- [deepl-python](https://github.com/DeepLcom/deepl-python) — DeepL 官方 Python SDK
- [Python-Markdown](https://python-markdown.github.io/) — Markdown 解析器
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML 解析器
- [DeepL API Limits](https://developers.deepl.com/docs/resources/usage-limits) — 500K chars/month free
- [DeepL Supported Languages](https://developers.deepl.com/docs/getting-started/supported-languages) — 36 种语言

### Brainstorm

- `docs/brainstorms/2026-03-03-notes-read-aloud-brainstorm.md`
