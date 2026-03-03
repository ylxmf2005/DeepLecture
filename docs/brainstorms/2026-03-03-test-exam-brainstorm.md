# Test (Exam-Style Questions) Feature Brainstorm

**Date:** 2026-03-03
**Status:** Decided
**Author:** EthanLee

## What We're Building

为 DeepLecture 添加 **Test（考试题）** 功能，生成比 Quiz（选择题）更深层次的混合大题型，模拟真实考试场景。题目要求用户组织语言进行深度思考，覆盖分析、综合、评价等高阶认知层次。

### 核心功能

1. **AI 生成混合大题型** — 从视频字幕和/或幻灯片中提取知识点，生成简答题、论述题、案例分析题、比较题等多种开放式题型
2. **LLM 自动选择题型** — 不硬性限定题型列表，由 LLM 根据内容特征自动决定最合适的题型组合
3. **参考答案 + 评分要点** — 每道题附带详细的参考答案（reference answer）和评分标准/要点（scoring criteria）
4. **布鲁姆认知层次标注** — 每道题标注对应的认知层次（记忆、理解、应用、分析、评价、创造），确保题目覆盖多个层次
5. **纯展示模式** — 生成后直接展示所有题目，点击展开查看参考答案和评分要点

### 与 Quiz 的区分

| 维度 | Quiz | Test |
|------|------|------|
| 题型 | 纯选择题（MCQ） | 混合开放式大题（简答、论述、案例分析等） |
| 思维层次 | 记忆、理解为主 | 分析、综合、评价等高阶思维 |
| 作答方式 | 点选选项 | 需要组织语言表达（v1 仅展示，不提供作答输入） |
| 答案形式 | 单一正确选项 | 参考答案 + 评分要点 |
| 用途 | 快速自测、知识检查 | 深度复习、模拟考试准备 |

### 不做的事情（YAGNI）

- ❌ 用户作答输入框（v1 纯展示）
- ❌ AI 自动评分/评价用户答案
- ❌ 分值/总分计算
- ❌ 定时考试模式
- ❌ 题目难度手动配置
- ❌ 导出为 PDF 试卷

## Why This Approach

### 方案 B（已选）：布鲁姆认知层次增强的两阶段管线

- **复用两阶段 LLM 流水线**（知识提取 → 考试题生成），与 Quiz/Flashcard/Cheatsheet 共享第一阶段
- **Stage 2 prompt 融入布鲁姆认知分类学**，显式要求 LLM 覆盖多个认知层次，确保题目深度分布合理
- **LLM 自主决定题型组合**，不硬编码题型列表，适应不同学科内容
- **代码量与方案 A 几乎相同**，仅 prompt 中多了认知层次的引导和 TestItem 多一个 `cognitive_level` 字段

### 被否决的方案

- **方案 A：标准两阶段管线** — 可行但题目深度分布不够均匀，缺少认知层次引导
- **方案 C：分离式生成** — 题目和答案分两次 LLM 调用生成。答案质量可能更高，但 token 消耗翻倍、延迟增加、架构偏离现有模式，属于过度设计

## Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 功能目标 | 深度复习、模拟考试准备 | 与 Quiz 形成互补 |
| 题型范围 | LLM 自动决定混合题型 | 适应不同学科，不硬编码题型列表 |
| 每题结构 | 题目 + 参考答案 + 评分要点 + 认知层次 | 完整的考试题信息 |
| 认知层次 | 布鲁姆分类学标注 | 确保题目覆盖高阶思维 |
| 前端交互 | 纯展示模式（折叠答案） | v1 简单，后续可加作答功能 |
| AI 评分 | 不需要（v1） | 作为未来迭代功能 |
| 题目数量 | 模型自行决定 | 根据内容密度决定，不可配置 |
| 生成流水线 | 布鲁姆增强的两阶段管线 | 与现有架构一致，prompt 增强 |
| 存储格式 | JSON（对齐 Quiz/Flashcard 模式） | 结构化数据，易于操作 |
| 架构模式 | 完全对齐现有 Clean Architecture | 代码风格统一，维护成本低 |

## Data Model

```python
@dataclass
class TestItem:
    question_type: str          # 题型标签（如 "short_answer", "essay", "case_analysis", "compare_contrast" 等）
    question: str               # 题目内容
    reference_answer: str       # 参考答案
    scoring_criteria: list[str] # 评分要点列表
    cognitive_level: str        # 布鲁姆认知层次（remember/understand/apply/analyze/evaluate/create）
    source_category: str | None # 来源知识点分类
    source_tags: list[str]      # 来源标签
```

**存储路径：** `content/{content_id}/test/{language}.json`

## Implementation Scope

### Backend（Python）

- `src/deeplecture/use_cases/dto/test.py` — TestItem, GenerateTestRequest, TestResult, GeneratedTestResult, TestStats
- `src/deeplecture/use_cases/interfaces/test.py` — TestStorageProtocol
- `src/deeplecture/infrastructure/repositories/fs_test_storage.py` — 文件系统存储
- `src/deeplecture/use_cases/prompts/test.py` — Prompt builder（含布鲁姆认知层次引导）
- `src/deeplecture/use_cases/prompts/registry.py` — 注册 `test_generation` prompt
- `src/deeplecture/use_cases/test_generation.py` — TestUseCase（get + generate）
- `src/deeplecture/presentation/api/routes/test.py` — GET/POST generate 路由
- `src/deeplecture/di/container.py` — DI 注册

### Frontend（TypeScript/React）

- `frontend/lib/api/test.ts` — API 客户端
- `frontend/components/features/TestTab.tsx` — 主组件（纯展示模式，折叠答案）
- Tab 注册集成（`"test"` TabId 已存在，只需替换 placeholder）

### Tests

- `tests/unit/use_cases/test_test_generation.py` — 用例单元测试

## Open Questions

- 认知层次标签在 UI 中的展示方式（颜色标签？图标？）— 可在实现阶段迭代
- 评分要点的最佳展示格式（有序列表 vs 无序列表）— 实现时决定
