# Flashcards Feature Brainstorm

**Date:** 2026-03-01
**Status:** Decided
**Author:** EthanLee

## What We're Building

为 DeepLecture 添加 **Flashcards（闪卡）** 功能，帮助学生通过「正面：问题/术语 → 背面：答案/解释」的主动回忆方式，记忆视频讲座中的核心概念。

### 核心功能

1. **AI 生成闪卡** — 从视频字幕和/或幻灯片中自动提取核心概念，生成正反面卡片
2. **翻转卡片流模式** — 单卡展示，点击翻转查看背面，左右切换下一张（类似 Anki）
3. **列表浏览模式** — 所有卡片以列表形式展示，点击展开查看背面
4. **视频时间戳跳转** — 每张卡片关联视频时间戳，点击可跳转到视频对应位置
5. **只读** — v1 不支持用户编辑卡片内容

### 不做的事情（YAGNI）

- ❌ 间隔重复记忆（SRS）调度算法
- ❌ 用户自评标记（认识/模糊/不认识）
- ❌ 用户编辑卡片内容
- ❌ 卡片分类/标签筛选
- ❌ 导出到 Anki 等外部工具

## Why This Approach

### 方案 A（已选）：对齐 Quiz 模式

- **JSON 存储**，结构化数据天然适合卡片正反面和时间戳
- **复用两阶段 LLM 流水线**（知识提取 → 卡片格式化），与 Quiz/Cheatsheet 共享第一阶段
- **代码风格完全一致**，遵循现有 Clean Architecture 模式
- **复用 `useSSEGenerationRetry` hook**，前端状态管理与其他 feature tab 统一

### 被否决的方案

- **方案 B：Markdown 变体** — 基于 Cheatsheet 的 Markdown 存储。虽然人类可读，但增加解析复杂度，与 Quiz 的 JSON 模式不一致，时间戳跳转不如结构化数据方便。

## Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 功能目标 | 主动回忆学习 | 帮助学生记忆核心概念 |
| 卡片结构 | 基础正反面 + 视频时间戳 | 简单有效，支持跳转 |
| SRS 逻辑 | 不需要 | v1 保持简单，只做翻卡学习 |
| 前端交互 | 翻转卡片流 + 列表浏览（可切换） | 满足不同学习偏好 |
| 用户编辑 | 只读 | 简化 v1 实现 |
| 卡片数量 | 模型自行决定（不可配置） | 内容密度决定数量，类似 Cheatsheet 的模式 |
| 生成流水线 | 复用两阶段（知识提取 → 格式化） | 与 Quiz/Cheatsheet 一致 |
| 存储格式 | JSON（对齐 Quiz 模式） | 结构化数据，易于操作 |
| 架构模式 | 完全对齐 Quiz 的 Clean Architecture | 代码风格统一，维护成本低 |

## Data Model

```python
@dataclass
class FlashcardItem:
    front: str                          # 正面：问题或术语
    back: str                           # 背面：答案或解释
    source_timestamp: float | None      # 视频时间戳（秒），支持跳转
    source_category: str | None         # 来源分类（如 "definition", "concept", "formula"）
```

**存储路径：** `content/{content_id}/flashcard/{language}.json`

## Implementation Scope

### Backend（Python）

- `src/deeplecture/use_cases/flashcard.py` — FlashcardUseCase（get + generate）
- `src/deeplecture/use_cases/dto/flashcard.py` — FlashcardItem, GenerateFlashcardRequest, FlashcardResult
- `src/deeplecture/use_cases/interfaces/flashcard.py` — FlashcardStorageProtocol
- `src/deeplecture/use_cases/prompts/flashcard.py` — Prompt builder
- `src/deeplecture/infrastructure/repositories/fs_flashcard_storage.py` — 文件系统存储
- `src/deeplecture/presentation/api/routes/flashcard.py` — GET/POST generate 路由
- `src/deeplecture/di/container.py` — DI 注册

### Frontend（TypeScript/React）

- `frontend/lib/api/flashcard.ts` — API 客户端
- `frontend/components/features/FlashcardTab.tsx` — 主组件（含两种模式切换）
- Tab 注册集成

### Tests

- `tests/unit/use_cases/test_flashcard.py` — 用例单元测试

## Open Questions

- 翻转动画的具体视觉效果（可在实现阶段迭代）
