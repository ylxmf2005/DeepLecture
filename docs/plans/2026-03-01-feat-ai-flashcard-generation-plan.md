---
title: "feat: Add AI-generated flashcards for active recall study"
type: feat
date: 2026-03-01
brainstorm: docs/brainstorms/2026-03-01-flashcards-brainstorm.md
---

# feat: Add AI-generated flashcards for active recall study

## Overview

为 DeepLecture 添加 AI 生成的 Flashcards（闪卡）功能，帮助学生通过「正面：问题/术语 → 背面：答案/解释」的主动回忆方式记忆视频讲座中的核心概念。每张卡片关联视频时间戳，支持一键跳转到视频对应位置。

前端提供两种交互模式：翻转卡片流（类似 Anki）和列表浏览（折叠展开），满足不同学习偏好。

## Problem Statement / Motivation

DeepLecture 已有 Quiz（测验）、Cheatsheet（速查表）、Notes（笔记）三种 AI 生成的学习辅助工具，但缺少一种针对**主动回忆记忆**的工具。Flashcards 是间隔重复学习的基础形式，用户需要一种快速翻阅核心概念的方式来巩固记忆。

## Proposed Solution

完全对齐现有 Quiz 的 Clean Architecture 模式，复用两阶段 LLM 流水线（知识提取 → 卡片格式化）。关键架构决策：

- **JSON 存储**，按语言分文件：`content/{content_id}/flashcard/{language}.json`
- **复用 `cheatsheet_extraction` 第一阶段**，新增 `flashcard_generation` 第二阶段 prompt
- **增强 KnowledgeItem**：添加 `source_start` 时间戳字段，让提取阶段保留时间信息
- **前端复用 `useSSEGenerationRetry` hook**，与其他 feature tab 统一
- **删除现有的词汇管理器 FlashcardTab**，用 AI 闪卡功能替代

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend                                                    │
│  FlashcardTab.tsx ──→ flashcard.ts API ──→ POST /generate   │
│       ↕ useSSEGenerationRetry                                │
│  FlipView / ListView ←── GET /flashcard/{id}                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Backend                                                     │
│  routes/flashcard.py ──→ FlashcardUseCase.generate()        │
│                              │                               │
│                    ┌─────────┴──────────┐                    │
│                    │ Stage 1            │ Stage 2             │
│                    │ cheatsheet_        │ flashcard_          │
│                    │ extraction         │ generation          │
│                    │ (shared)           │ (new)               │
│                    │ → KnowledgeItem[]  │ → FlashcardItem[]   │
│                    └─────────┬──────────┘                    │
│                              │                               │
│  FsFlashcardStorage ──→ content/{id}/flashcard/{lang}.json  │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Phases

---

#### Phase 1: 增强知识提取（添加时间戳）

**目标：** 让 KnowledgeItem 携带时间戳信息，供 Flashcard（以及未来其他功能）使用。

##### 1.1 修改字幕上下文加载

**文件：** `src/deeplecture/use_cases/cheatsheet.py` (lines 224-241)、`quiz.py` (lines 283-300)、`note.py` (lines 298-316)

当前 `_load_subtitle_context()` 丢弃时间戳：
```python
# 当前实现（丢弃时间戳）
lines = [seg.text.replace("\n", " ").strip() for seg in segments if seg.text.strip()]
return "\n".join(lines)
```

新增一个 **带时间戳的上下文加载方法**（仅供 Flashcard 使用，不修改现有方法以避免影响 Quiz/Cheatsheet/Note 的行为）：

```python
# flashcard.py 中的新方法
def _load_subtitle_context_with_timestamps(self, content_id: str) -> str:
    """Load subtitle text with timestamp markers for knowledge extraction."""
    # ... 加载 segments ...
    lines = []
    for seg in segments:
        text = seg.text.replace("\n", " ").strip()
        if text:
            minutes, secs = divmod(int(seg.start), 60)
            hours, minutes = divmod(minutes, 60)
            lines.append(f"[{hours:02d}:{minutes:02d}:{secs:02d}] {text}")
    return "\n".join(lines)
```

##### 1.2 修改 KnowledgeItem DTO

**文件：** `src/deeplecture/use_cases/dto/cheatsheet.py` (lines 16-35)

添加可选的 `source_start` 字段：

```python
@dataclass
class KnowledgeItem:
    category: str
    content: str
    criticality: str
    tags: list[str] = field(default_factory=list)
    source_start: float | None = None  # NEW: 视频时间戳（秒）
```

**向后兼容：** 默认值 `None`，`from_dict()` 中用 `.get()` 读取，现有 Quiz/Cheatsheet 代码不受影响。

##### 1.3 更新 cheatsheet_extraction prompt

**文件：** `src/deeplecture/use_cases/prompts/cheatsheet.py` (lines 11-68)

修改提取 prompt，当输入包含时间标记 `[HH:MM:SS]` 时，要求 LLM 在输出的 JSON 中包含 `source_start` 字段：

```python
# 在 JSON schema 说明中添加
"source_start": 123.0  // 对应内容出现的视频秒数（来自输入中的时间标记），可选
```

##### 1.4 更新提取逻辑

**文件：** `src/deeplecture/use_cases/cheatsheet.py` — `_extract_knowledge_items()` 方法

更新 `KnowledgeItem.from_dict()` 调用以接受 `source_start` 字段。

##### 1.5 更新现有测试

**文件：** `tests/unit/use_cases/test_cheatsheet.py`、`tests/unit/use_cases/test_quiz.py`

确保现有测试在 KnowledgeItem 增加可选字段后仍然通过。

---

#### Phase 2: Backend — Flashcard 核心实现

##### 2.1 DTO 定义

**新建文件：** `src/deeplecture/use_cases/dto/flashcard.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FlashcardItem:
    """单张闪卡。"""
    front: str                              # 正面：问题或术语
    back: str                               # 背面：答案或解释
    source_timestamp: float | None = None   # 视频时间戳（秒）
    source_category: str | None = None      # definition | concept | formula | ...

    def to_dict(self) -> dict[str, Any]:
        return {
            "front": self.front,
            "back": self.back,
            "source_timestamp": self.source_timestamp,
            "source_category": self.source_category,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FlashcardItem:
        return cls(
            front=data.get("front", ""),
            back=data.get("back", ""),
            source_timestamp=data.get("source_timestamp"),
            source_category=data.get("source_category"),
        )


@dataclass
class GenerateFlashcardRequest:
    """生成请求参数。"""
    content_id: str
    language: str                       # 必填
    context_mode: str = "both"          # subtitle | slide | both
    user_instruction: str = ""
    min_criticality: str = "medium"     # high | medium | low
    subject_type: str = "auto"          # stem | humanities | auto
    llm_model: str | None = None
    prompts: dict[str, str] | None = None


@dataclass
class FlashcardStats:
    """生成统计信息。"""
    total_items: int = 0
    valid_items: int = 0
    filtered_items: int = 0
    by_category: dict[str, int] = field(default_factory=dict)


@dataclass
class FlashcardResult:
    """GET/基础响应 DTO。"""
    content_id: str
    language: str
    items: list[FlashcardItem] = field(default_factory=list)
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "language": self.language,
            "items": [item.to_dict() for item in self.items],
            "count": len(self.items),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class GeneratedFlashcardResult:
    """生成完成响应 DTO。"""
    content_id: str
    language: str
    items: list[FlashcardItem]
    updated_at: datetime | None
    used_sources: list[str]
    stats: FlashcardStats

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "language": self.language,
            "items": [item.to_dict() for item in self.items],
            "count": len(self.items),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "used_sources": self.used_sources,
            "stats": {
                "total_items": self.stats.total_items,
                "valid_items": self.stats.valid_items,
                "filtered_items": self.stats.filtered_items,
                "by_category": self.stats.by_category,
            },
        }
```

**注意：** 没有 `question_count` / `card_count` — 卡片数量由模型自行决定。

##### 2.2 Storage Protocol

**新建文件：** `src/deeplecture/use_cases/interfaces/flashcard.py`

```python
class FlashcardStorageProtocol(Protocol):
    def load(self, content_id: str, language: str | None = None) -> tuple[dict[str, Any], datetime] | None: ...
    def save(self, content_id: str, language: str, data: dict[str, Any]) -> datetime: ...
    def exists(self, content_id: str, language: str | None = None) -> bool: ...
```

完全对齐 `QuizStorageProtocol` 签名。

##### 2.3 Storage 实现

**新建文件：** `src/deeplecture/infrastructure/repositories/fs_flashcard_storage.py`

- `NAMESPACE = "flashcard"`
- 路径：`content/{content_id}/flashcard/{language}.json`
- 对齐 `FsQuizStorage` 的原子写入模式（tempfile + os.replace）

##### 2.4 Flashcard 生成 Prompt

**新建文件：** `src/deeplecture/use_cases/prompts/flashcard.py`

```python
def build_flashcard_generation_prompts(
    knowledge_items_json: str,
    language: str,
    user_instruction: str = "",
) -> tuple[str, str]:
    """构建闪卡生成 prompt。

    与 quiz_generation 不同：不指定数量，由模型根据知识项数量自行决定。
    """
    system_prompt = f"""You are an expert educator creating flashcards for active recall study.

OUTPUT FORMAT (CRITICAL):
Output ONLY a JSON array:
[
  {{
    "front": "Question or term (concise, clear)",
    "back": "Answer or explanation (thorough but focused)",
    "source_timestamp": 123.0,
    "source_category": "definition"
  }}
]

RULES:
- Create ONE flashcard per knowledge item (some items may warrant 2 if complex)
- "front" should be a concise question, term, or prompt that triggers recall
- "back" should be a clear, complete answer (2-4 sentences)
- "source_timestamp" — copy directly from the knowledge item's source_start field (null if unavailable)
- "source_category" — copy directly from the knowledge item's category field
- Output language: {language}

CARD QUALITY GUIDELINES:
- Front side: Use questions ("What is...?"), fill-in-the-blank, or single terms
- Back side: Include the key answer + brief context/example
- Avoid yes/no questions — prefer open recall
- Each card should test ONE concept
- Do NOT duplicate cards for the same concept
"""

    user_prompt = f"""Create flashcards from these knowledge items:

{knowledge_items_json}

{"Additional instructions: " + user_instruction if user_instruction else ""}
"""
    return system_prompt, user_prompt
```

##### 2.5 Prompt Registry 注册

**文件：** `src/deeplecture/use_cases/prompts/registry.py`

添加 `FlashcardGenerationBuilder` 类（对齐 `QuizGenerationBuilder`），并注册：

```python
registry.register(
    "flashcard_generation",
    FlashcardGenerationBuilder("default", "Default", "Flashcard generation from knowledge items"),
    is_default=True,
)
```

##### 2.6 FlashcardUseCase

**新建文件：** `src/deeplecture/use_cases/flashcard.py`

构造函数（对齐 QuizUseCase）：

```python
class FlashcardUseCase:
    def __init__(
        self,
        *,
        flashcard_storage: FlashcardStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        llm_provider: LLMProviderProtocol,
        path_resolver: PathResolverProtocol,
        prompt_registry: PromptRegistryProtocol,
        metadata_storage: MetadataStorageProtocol | None = None,
        pdf_text_extractor: PdfTextExtractorProtocol | None = None,
    ) -> None:
```

核心方法：

- **`get(content_id, language)`** → `FlashcardResult`
  - 从 storage 加载 JSON，解析为 `FlashcardItem` 列表
- **`generate(request: GenerateFlashcardRequest)`** → `GeneratedFlashcardResult`
  - Stage 1: 加载上下文（**使用带时间戳的字幕格式**），调用 `cheatsheet_extraction` 提取 KnowledgeItem
  - 按 criticality 过滤
  - Stage 2: 将 KnowledgeItem JSON 传入 `flashcard_generation` prompt
  - 验证 & 过滤无效卡片
  - 保存并返回

验证函数：

```python
def validate_flashcard_item(item: dict) -> tuple[bool, str]:
    """验证单张卡片。"""
    if not item.get("front") or not isinstance(item["front"], str):
        return False, "missing or empty 'front'"
    if not item.get("back") or not isinstance(item["back"], str):
        return False, "missing or empty 'back'"
    ts = item.get("source_timestamp")
    if ts is not None and (not isinstance(ts, (int, float)) or ts < 0):
        return False, "invalid source_timestamp"
    return True, ""
```

##### 2.7 DI Container 注册

**文件：** `src/deeplecture/di/container.py`

添加两个 property（对齐 quiz_storage / quiz_usecase 模式）：

```python
@property
def flashcard_storage(self) -> FsFlashcardStorage:
    if "flashcard_storage" not in self._cache:
        self._cache["flashcard_storage"] = FsFlashcardStorage(self.path_resolver)
    return self._cache["flashcard_storage"]

@property
def flashcard_usecase(self) -> FlashcardUseCase:
    if "flashcard_uc" not in self._cache:
        self._cache["flashcard_uc"] = FlashcardUseCase(
            flashcard_storage=self.flashcard_storage,
            subtitle_storage=self.subtitle_storage,
            llm_provider=self.llm_provider,
            path_resolver=self.path_resolver,
            prompt_registry=self.prompt_registry,
            metadata_storage=self.metadata_storage,
            pdf_text_extractor=self.pdf_text_extractor,
        )
    return self._cache["flashcard_uc"]
```

##### 2.8 API 路由

**新建文件：** `src/deeplecture/presentation/api/routes/flashcard.py`

```python
bp = Blueprint("flashcard", __name__)

@bp.route("/<content_id>", methods=["GET"])
@handle_errors
def get_flashcard(content_id: str) -> Response:
    """GET /api/flashcard/{content_id}?language=en"""
    # validate content_id, language
    # container.flashcard_usecase.get(content_id, language)
    # return success(result.to_dict()) or not_found()

@bp.route("/<content_id>/generate", methods=["POST"])
@rate_limit("generate")
@handle_errors
def generate_flashcard(content_id: str) -> Response:
    """POST /api/flashcard/{content_id}/generate"""
    # validate: language (required), context_mode, user_instruction
    # resolve LLM model via resolve_models_for_task(task_key="flashcard_generation")
    # build GenerateFlashcardRequest
    # submit async task via task_manager.submit(task_type="flashcard_generation")
    # return accepted({content_id, task_id, status, message})
```

##### 2.9 Blueprint 注册

**文件：** `src/deeplecture/presentation/api/app.py`

```python
from deeplecture.presentation.api.routes.flashcard import bp as flashcard_bp
app.register_blueprint(flashcard_bp, url_prefix="/api/flashcard")
```

---

#### Phase 3: Frontend — API 客户端 & Tab 组件

##### 3.1 API 客户端

**新建文件：** `frontend/lib/api/flashcard.ts`

```typescript
export interface FlashcardItem {
  front: string;
  back: string;
  sourceTimestamp: number | null;
  sourceCategory: string | null;
}

export interface FlashcardResponse {
  contentId: string;
  language: string;
  items: FlashcardItem[];
  count: number;
  updatedAt: string | null;
}

export interface GenerateFlashcardResponse {
  contentId: string;
  taskId: string;
  status: "pending";
  message: string;
}

export interface GenerateFlashcardParams {
  contentId: string;
  language: string;
  contextMode?: "subtitle" | "slide" | "both";
  instruction?: string;
}

export const getFlashcard = async (
  contentId: string,
  language: string,
): Promise<FlashcardResponse | null> => {
  // GET /api/flashcard/{contentId}?language=...
  // return null on 404
};

export const generateFlashcard = async (
  params: GenerateFlashcardParams,
): Promise<GenerateFlashcardResponse> => {
  // POST /api/flashcard/{contentId}/generate
  // withLLMOverrides({...})
};
```

##### 3.2 删除旧 FlashcardTab

**删除文件：** `frontend/components/features/FlashcardTab.tsx`（现有的词汇管理器）

##### 3.3 新建 FlashcardTab 组件

**新建文件：** `frontend/components/features/FlashcardTab.tsx`

组件结构：

```
FlashcardTab
├── Props: { videoId, onSeek, refreshTrigger }
├── State: viewMode ("flip" | "list"), currentIndex
├── Hook: useSSEGenerationRetry<FlashcardData>({
│       taskType: "flashcard_generation",
│       fetchContent: getFlashcard(videoId, language),
│       submitGeneration: generateFlashcard({...}),
│       extraDeps: [language],
│   })
├── States: Loading → Generating → Error → Idle (CTA) → Content
│
├── Content View:
│   ├── Header: 模式切换 (Flip ↔ List) + 卡片数量 + 重新生成按钮
│   │
│   ├── FlipView:
│   │   ├── 单卡展示（CSS 3D 翻转动画）
│   │   ├── 进度指示器: "Card 5 / 23"
│   │   ├── 导航: ← → 按钮 + 键盘 Left/Right
│   │   ├── 翻转: 点击卡片或 Space 键
│   │   ├── 时间戳跳转按钮（如有）
│   │   └── 到达末尾: 显示完成卡片 + "重新开始" 按钮
│   │
│   └── ListView:
│       ├── 折叠/展开手风琴（显示 front，展开显示 back）
│       ├── 支持多张同时展开
│       └── 每张卡片显示 category badge + 时间戳跳转
```

##### 3.4 SSE 刷新触发器集成

**文件：** `frontend/app/video/[id]/VideoPageClient.tsx`

在 SSE 事件处理器中添加 `flashcard_generation` 任务类型，递增 `refreshFlashcard` 计数器。

**文件：** `frontend/components/video/TabContentRenderer.tsx`

- 添加 `refreshFlashcard` prop
- 在 `"flashcard"` case 中渲染 `<FlashcardTab>` 替代 `<FeaturePlaceholder>`

##### 3.5 Tab 配置确认

**文件：** `frontend/components/dnd/DraggableTabBar.tsx` (line ~35)

`flashcard` 已经存在于 `TAB_CONFIG` 中，无需修改。确认图标合适即可。

---

#### Phase 4: 测试

##### 4.1 后端单元测试

**新建文件：** `tests/unit/use_cases/test_flashcard.py`

```python
class TestValidateFlashcardItem:
    """验证逻辑测试。"""
    def test_valid_item(self): ...
    def test_empty_front_rejected(self): ...
    def test_empty_back_rejected(self): ...
    def test_negative_timestamp_rejected(self): ...
    def test_null_timestamp_accepted(self): ...

class TestFlashcardItemDTO:
    """DTO 序列化测试。"""
    def test_to_dict(self): ...
    def test_from_dict(self): ...
    def test_from_dict_missing_optional_fields(self): ...

class TestFlashcardUseCase:
    """用例集成测试（mock LLM）。"""
    def test_get_returns_none_when_not_found(self): ...
    def test_get_returns_items(self): ...
    def test_generate_two_stage_pipeline(self): ...
    def test_generate_filters_invalid_items(self): ...
```

##### 4.2 更新现有测试

**文件：** `tests/unit/use_cases/test_cheatsheet.py`、`tests/unit/use_cases/test_quiz.py`

确保 KnowledgeItem 新增 `source_start` 可选字段后，现有测试不受影响。

---

## Acceptance Criteria

### Functional Requirements

- [ ] **生成：** 用户在 Flashcard tab 点击 "Generate"，异步生成 AI 闪卡
- [ ] **翻转模式：** 单卡展示，点击/Space 翻转，Left/Right 切换，到末尾显示完成页
- [ ] **列表模式：** 折叠手风琴，点击展开查看 back
- [ ] **模式切换：** Flip ↔ List 可切换
- [ ] **时间戳跳转：** 点击卡片上的时间戳，视频跳转到对应位置
- [ ] **多语言支持：** 切换语言后显示对应语言的卡片或 Generate CTA
- [ ] **异步任务：** 生成过程通过 SSE 通知前端，支持页面刷新后恢复
- [ ] **重新生成：** 支持重新生成（覆盖旧数据）

### Non-Functional Requirements

- [ ] **架构一致性：** 完全对齐 Quiz 的 Clean Architecture 模式
- [ ] **向后兼容：** KnowledgeItem 新增字段不影响现有 Quiz/Cheatsheet 功能
- [ ] **键盘支持：** Flip 模式支持 Space（翻转）、Left/Right（导航）

### Quality Gates

- [ ] `uv run pytest tests/unit/use_cases/test_flashcard.py -q` 全部通过
- [ ] 现有测试 `test_quiz.py`、`test_cheatsheet.py` 不受影响
- [ ] `cd frontend && npm run -s typecheck` 通过
- [ ] Context mode 遵循统一模式（`subtitle | slide | both`），复用共享 helpers

## Dependencies & Prerequisites

- 现有的 `cheatsheet_extraction` prompt 和知识提取流水线
- `useSSEGenerationRetry` hook 和 SSE 任务系统
- `FsQuizStorage` 作为存储实现的参考模板

## Risk Analysis & Mitigation

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| KnowledgeItem 增加 source_start 影响现有功能 | Quiz/Cheatsheet 行为改变 | 字段可选 + 默认 None，现有代码忽略该字段 |
| LLM 时间戳不准确 | 跳转位置偏差 | timestamp 来自字幕原始数据，LLM 只是传递 |
| LLM 生成卡片数量失控 | UX 问题 | prompt 中引导合理数量，验证阶段可加软上限 |
| 修改 extraction prompt 影响提取质量 | 所有功能质量下降 | 仅在有时间标记的输入时提示输出 source_start |

## References & Research

### Internal References

- Quiz UseCase 完整模式: `src/deeplecture/use_cases/quiz.py:77-491`
- Cheatsheet 知识提取: `src/deeplecture/use_cases/cheatsheet.py:278-326`
- KnowledgeItem DTO: `src/deeplecture/use_cases/dto/cheatsheet.py:16-35`
- 字幕上下文加载: `src/deeplecture/use_cases/cheatsheet.py:224-241`
- Segment 实体（含时间戳）: `src/deeplecture/domain/entities/media.py`
- DI Container 注册: `src/deeplecture/di/container.py:582-594`
- API 路由模式: `src/deeplecture/presentation/api/routes/quiz.py:28-128`
- Blueprint 注册: `src/deeplecture/presentation/api/app.py:49-98`
- Prompt Registry: `src/deeplecture/use_cases/prompts/registry.py:406-466`
- Tab 配置: `frontend/components/dnd/DraggableTabBar.tsx:27-41`
- TabContentRenderer: `frontend/components/video/TabContentRenderer.tsx:396-397`
- SSE 刷新触发器: `frontend/app/video/[id]/VideoPageClient.tsx`
- Context Mode 统一教训: `docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md`
- Brainstorm 文档: `docs/brainstorms/2026-03-01-flashcards-brainstorm.md`

### New Files to Create

| File | Purpose |
|------|---------|
| `src/deeplecture/use_cases/flashcard.py` | FlashcardUseCase |
| `src/deeplecture/use_cases/dto/flashcard.py` | DTOs |
| `src/deeplecture/use_cases/interfaces/flashcard.py` | StorageProtocol |
| `src/deeplecture/use_cases/prompts/flashcard.py` | Prompt builder |
| `src/deeplecture/infrastructure/repositories/fs_flashcard_storage.py` | FS 存储 |
| `src/deeplecture/presentation/api/routes/flashcard.py` | API 路由 |
| `frontend/lib/api/flashcard.ts` | API 客户端 |
| `frontend/components/features/FlashcardTab.tsx` | 前端组件（替换旧文件） |
| `tests/unit/use_cases/test_flashcard.py` | 单元测试 |

### Files to Modify

| File | Change |
|------|--------|
| `src/deeplecture/use_cases/dto/cheatsheet.py` | KnowledgeItem 添加 `source_start` |
| `src/deeplecture/use_cases/prompts/cheatsheet.py` | extraction prompt 支持时间戳 |
| `src/deeplecture/use_cases/prompts/registry.py` | 注册 flashcard_generation builder |
| `src/deeplecture/di/container.py` | 注册 flashcard_storage + flashcard_usecase |
| `src/deeplecture/presentation/api/app.py` | 注册 flashcard blueprint |
| `frontend/components/video/TabContentRenderer.tsx` | 渲染 FlashcardTab |
| `frontend/app/video/[id]/VideoPageClient.tsx` | SSE 刷新触发器 |
