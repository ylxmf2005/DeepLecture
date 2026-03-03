---
title: "feat: AI Test Paper Generation (Exam-Style Questions)"
type: feat
date: 2026-03-03
brainstorm: docs/brainstorms/2026-03-03-test-exam-brainstorm.md
---

# feat: AI Test Paper Generation (Exam-Style Questions)

## Overview

为 DeepLecture 添加 **Test Paper（考试题）** 功能，从视频讲座内容中生成混合开放式大题（简答题、论述题、案例分析题、比较题等），每道题附带参考答案、评分要点和布鲁姆认知层次标注。复用现有两阶段 LLM 管线，与 Quiz/Flashcard/Cheatsheet 共享第一阶段知识提取，仅 Stage 2 不同。

**关键区分**：Quiz = 选择题（记忆/理解层次），Test Paper = 开放式大题（分析/综合/评价等高阶思维）。

## Problem Statement / Motivation

当前 DeepLecture 的 Quiz 功能只支持选择题（MCQ），只能检测记忆和理解层次的知识掌握。学生在准备考试时需要更深度的练习：
- 用自己的语言组织答案（而非识别选项）
- 锻炼分析、综合、评价等高阶思维
- 熟悉真实考试的题型和评分标准

前端 `"test"` TabId 已注册并在 `DEFAULT_BOTTOM_TABS` 中，当前显示 `FeaturePlaceholder`。

## Proposed Solution

### 架构：布鲁姆增强的两阶段 LLM 管线

```
Stage 1（共享）: cheatsheet_extraction → KnowledgeItem[]
                 coverage_mode = "exam_focused"
                           ↓
Stage 2（专用）: test_paper_generation → TestQuestion[]
                 含布鲁姆认知层次引导
                           ↓
                 验证 + 过滤 → 保存 JSON
```

### 命名约定

| 维度 | 值 |
|------|-----|
| API URL prefix | `/api/test-paper` |
| task_type | `test_paper_generation` |
| prompt func_id | `test_paper_generation` |
| 存储 NAMESPACE | `test_paper` |
| 存储路径 | `content/{content_id}/test_paper/{language}.json` |
| 前端 TabId | `"test"`（已存在） |
| DI cache key | `test_paper_storage`, `test_paper_uc` |
| Python 模块名 | `test_paper.py`（避免与 pytest 的 `test_*.py` 冲突） |

---

## Technical Approach

### Data Model

```python
# src/deeplecture/use_cases/dto/test_paper.py

VALID_BLOOM_LEVELS = frozenset({
    "remember", "understand", "apply", "analyze", "evaluate", "create"
})

@dataclass
class TestQuestion:
    question_type: str              # LLM 自动选择，如 "short_answer", "essay", "case_analysis", "compare_contrast"
    stem: str                       # 题目内容
    reference_answer: str           # 参考答案
    scoring_criteria: list[str]     # 评分要点列表，如 ["准确定义概念 (2分)", "结合实例说明 (3分)"]
    bloom_level: str                # 布鲁姆认知层次: remember/understand/apply/analyze/evaluate/create
    source_timestamp: float | None  # 视频时间戳（秒），支持跳转
    source_category: str | None     # 来源知识点分类
    source_tags: list[str]          # 来源标签

    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestQuestion": ...


@dataclass
class GenerateTestPaperRequest:
    content_id: str
    language: str
    context_mode: str = "both"              # "subtitle" | "slide" | "both"
    user_instruction: str = ""
    min_criticality: str = "medium"
    subject_type: str = "general"
    llm_model: str | None = None
    prompts: dict[str, tuple[str, str]] | None = None


@dataclass
class TestPaperStats:
    total_questions: int
    valid_questions: int
    filtered_questions: int
    by_category: dict[str, int]
    by_bloom_level: dict[str, int]      # 每个认知层次的题目数
    by_question_type: dict[str, int]    # 每个题型的题目数

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class TestPaperResult:
    content_id: str
    language: str
    questions: list[TestQuestion]
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class GeneratedTestPaperResult:
    content_id: str
    language: str
    questions: list[TestQuestion]
    used_sources: list[str]
    stats: TestPaperStats
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]: ...
```

### Stage 2 Prompt 设计要点

`src/deeplecture/use_cases/prompts/test_paper.py` — `build_test_paper_generation_prompts()`:

**System Prompt 关键指令：**
1. **OUTPUT FORMAT**: JSON array of TestQuestion objects（先定义 schema）
2. **布鲁姆认知分类学**：明确列出六个层次及其含义，要求覆盖至少 3 个不同层次
3. **题型多样性**：要求至少 2 种不同题型，任一题型不超过 60%
4. **参考答案要求**：完整、准确、直接回答题目
5. **评分要点要求**：每个要点明确、可操作，可直接用于评分
6. **题目数量**：软引导 5-15 题（根据知识点数量，约每 3-5 个知识点生成 1 道题）
7. **语言一致性**：输出语言与内容语言一致
8. **source_timestamp**: 如果可用，关联到最相关的视频时间点

### Validation 规则

```python
# 模块级函数 validate_test_question()
def validate_test_question(data: dict) -> TestQuestion | None:
    """验证 LLM 输出的单个题目，返回 None 表示无效。"""
    # 必填字段检查: question_type, stem, reference_answer, scoring_criteria, bloom_level
    # stem 最小长度: 10 字符
    # reference_answer 最小长度: 20 字符
    # scoring_criteria 至少 1 个要点
    # bloom_level 必须在 VALID_BLOOM_LEVELS 中（宽松匹配：lowercase + strip）
    # question_type 不做枚举验证（LLM 自由选择）
    # source_timestamp 可选，验证 >= 0
```

---

## Implementation Phases

### Phase 1: Backend Core（Python，10 个文件）

按依赖顺序实现：

#### 1.1 DTO 定义

**新建** `src/deeplecture/use_cases/dto/test_paper.py`
- `TestQuestion` dataclass + `to_dict()` / `from_dict()`
- `GenerateTestPaperRequest` dataclass
- `TestPaperStats`, `TestPaperResult`, `GeneratedTestPaperResult` dataclasses
- `VALID_BLOOM_LEVELS` frozenset
- 参考: `src/deeplecture/use_cases/dto/quiz.py` 的完整结构

#### 1.2 Storage Interface

**新建** `src/deeplecture/use_cases/interfaces/test_paper.py`
- `TestPaperStorageProtocol(Protocol)` with `load()`, `save()`, `exists()`
- 参考: `src/deeplecture/use_cases/interfaces/quiz.py`

**修改** `src/deeplecture/use_cases/interfaces/__init__.py`
- 添加 import 和 `__all__` 条目

#### 1.3 Filesystem Storage

**新建** `src/deeplecture/infrastructure/repositories/fs_test_paper_storage.py`
- `FsTestPaperStorage` with `NAMESPACE = "test_paper"`
- 原子写入模式: `tempfile.NamedTemporaryFile` + `os.replace`
- 参考: `src/deeplecture/infrastructure/repositories/fs_quiz_storage.py`

**修改** `src/deeplecture/infrastructure/repositories/__init__.py`
- 添加 import 和 `__all__` 条目

**修改** `src/deeplecture/infrastructure/__init__.py`
- 添加 import 和 `__all__` 条目

#### 1.4 Prompt Builder

**新建** `src/deeplecture/use_cases/prompts/test_paper.py`
- `build_test_paper_generation_prompts(knowledge_items_json, language, user_instruction)` → `tuple[str, str]`
- System prompt 包含：布鲁姆认知层次定义、题型多样性要求、JSON schema、评分要点规范
- 软引导题目数量: 5-15 题

**修改** `src/deeplecture/use_cases/prompts/registry.py`
- 添加 `TestPaperGenerationBuilder(BasePromptBuilder)` 类
- 在 `create_default_registry()` 中注册 `func_id="test_paper_generation"`

#### 1.5 Use Case

**新建** `src/deeplecture/use_cases/test_paper.py`
- `validate_test_question()` 模块级函数
- `TestPaperUseCase` 类:
  - Constructor: `test_paper_storage`, `subtitle_storage`, `llm_provider`, `path_resolver`, `prompt_registry`, `metadata_storage`, `pdf_text_extractor`
  - `get(content_id, language)` → `TestPaperResult | None`
  - `generate(request: GenerateTestPaperRequest)` → `GeneratedTestPaperResult`
  - Stage 1: `_extract_knowledge_items()` 使用 `cheatsheet_extraction`，`coverage_mode="exam_focused"`
  - Stage 2: `_generate_test_paper()` 使用 `test_paper_generation`
  - `_validate_and_filter()` 验证每道题
  - 共享方法: `_load_context()`, `_load_subtitle_context_with_timestamps()`, `_load_slide_context()`, `_select_sources()`, `_filter_by_criticality()`
- 参考: `src/deeplecture/use_cases/quiz.py` 完整结构

#### 1.6 DI Container

**修改** `src/deeplecture/di/container.py`
- 添加 imports: `FsTestPaperStorage`, `TestPaperUseCase`
- 添加 `test_paper_storage` property → `FsTestPaperStorage(self.path_resolver)`
- 添加 `test_paper_usecase` property → `TestPaperUseCase(...)` with all dependencies

#### 1.7 API Route

**新建** `src/deeplecture/presentation/api/routes/test_paper.py`
- `bp = Blueprint("test_paper", __name__)`
- `GET /<content_id>`: 验证参数 → `container.test_paper_usecase.get()` → 404 or JSON
- `POST /<content_id>/generate`: `@rate_limit("generate")` + `@handle_errors`
  - 验证: `content_id`, `language`, `context_mode` (strict: subtitle/slide/both), `min_criticality`, `subject_type`
  - `resolve_models_for_task(container, content_id, "test_paper_generation", ...)`
  - 构建 `GenerateTestPaperRequest`
  - `container.task_manager.submit(content_id, "test_paper_generation", _run_generation, metadata)`
  - 返回 `accepted()`
- 参考: `src/deeplecture/presentation/api/routes/quiz.py`

**修改** `src/deeplecture/presentation/api/routes/__init__.py`
- 添加 `test_paper_bp` import 和 `__all__` 条目

**修改** `src/deeplecture/presentation/api/app.py`
- `app.register_blueprint(test_paper_bp, url_prefix="/api/test-paper")`

### Phase 2: Frontend（TypeScript/React，6 个文件）

#### 2.1 API Client

**新建** `frontend/lib/api/test-paper.ts`

```typescript
export interface TestQuestion {
  question_type: string;
  stem: string;
  reference_answer: string;
  scoring_criteria: string[];
  bloom_level: string;
  source_timestamp: number | null;
  source_category: string | null;
  source_tags: string[];
}

export interface TestPaperResponse {
  content_id: string;
  language: string;
  questions: TestQuestion[];
  updated_at: string;
}

export interface GenerateTestPaperResponse {
  content_id: string;
  task_id: string;
  status: string;
  message: string;
}

export interface GenerateTestPaperParams {
  contentId: string;
  language: string;
  contextMode?: string;
  userInstruction?: string;
  minCriticality?: string;
  subjectType?: string;
}

export async function getTestPaper(contentId: string, language: string): Promise<TestPaperResponse | null> { ... }
export async function generateTestPaper(params: GenerateTestPaperParams): Promise<GenerateTestPaperResponse> { ... }
```

参考: `frontend/lib/api/quiz.ts`

#### 2.2 Tab Component

**新建** `frontend/components/features/TestTab.tsx`

Props: `{ videoId: string; onSeek: (time: number) => void; refreshTrigger: number; }`

核心结构:
- 使用 `useSSEGenerationRetry<TestPaperResponse>` hook，`taskType: "test_paper_generation"`
- 4 状态渲染: loading / generating / error / idle (CTA) / content
- **颜色主题**: emerald（绿色系，区别于 Quiz 的 violet 和 Flashcard 的 sky）
- **内容渲染**:
  - 题目列表，每题编号显示
  - 每题标题行: 编号 + 题型 badge + 布鲁姆层次 badge + 题目内容
  - 可折叠区域: 参考答案 + 评分要点列表
  - 多选展开（multi-expand），默认全部折叠
  - 如有 `source_timestamp`，显示时间戳跳转按钮（调用 `onSeek`）

**布鲁姆层次 badge 配色方案：**
| 层次 | 颜色 | 含义 |
|------|------|------|
| remember | gray | 记忆 |
| understand | blue | 理解 |
| apply | green | 应用 |
| analyze | amber | 分析 |
| evaluate | orange | 评价 |
| create | red | 创造 |

**题型 badge**: 统一用中性色（如 slate），显示 `question_type` 的 human-readable 版本。

参考: `frontend/components/features/QuizTab.tsx` + `FlashcardTab.tsx`

#### 2.3 Tab Registration & Wiring

**修改** `frontend/components/video/TabContentRenderer.tsx`
- 添加 dynamic import: `const TestTab = dynamic(() => import("@/components/features/TestTab").then((mod) => mod.TestTab), { loading: LoadingSpinner })`
- 在 `TabContentProps` 中添加 `refreshTest: number;`
- 在 `renderTabContent` switch 的 `"test"` case 中替换 `FeaturePlaceholder` 为 `<TestTab videoId={videoId} onSeek={onSeek} refreshTrigger={refreshTest} />`

**修改** `frontend/hooks/useVideoPageState.ts`
- 添加 `const [refreshTest, setRefreshTest] = useState(0);`
- 在 SSE handler 中添加 `test_paper_generation` 分支:
  ```typescript
  } else if (taskType === "test_paper_generation" && isLiveEvent && task.status === "ready") {
      log.info("SSE: test_paper_generation completed, bumping refreshTest", { taskId, taskType, status: task.status });
      setRefreshTest((prev) => prev + 1);
  }
  ```
- 在返回对象中添加 `refreshTest`

**修改** `frontend/app/video/[id]/VideoPageClient.tsx`
- 将 `refreshTest` 从 `useVideoPageState` 解构并传递给 `TabContentRenderer`

**修改** `frontend/lib/taskTypes.ts`
- 在 `TASK_LABELS` 中添加:
  ```typescript
  test_paper_generation: {
      success: "Test paper generated successfully",
      error: "Test paper generation failed",
  },
  ```

### Phase 3: Unit Tests（Python，1 个文件）

**新建** `tests/unit/use_cases/test_test_paper.py`

测试类结构（参考 `tests/unit/use_cases/test_quiz.py`）:

- `TestValidateTestQuestion` — 验证函数测试
  - 有效题目通过验证
  - 缺少必填字段返回 None
  - stem 太短返回 None
  - reference_answer 太短返回 None
  - 无效 bloom_level 返回 None
  - bloom_level 大小写宽松匹配
  - scoring_criteria 为空列表返回 None
- `TestTestQuestionDTO` — 序列化/反序列化
  - `to_dict()` 正确序列化
  - `from_dict()` 正确反序列化
  - `from_dict()` 处理缺失可选字段
- `TestTestPaperUseCaseGet` — get() 方法
  - 正常获取
  - 不存在返回 None
- `TestTestPaperUseCaseGenerate` — generate() 方法
  - 完整流程 happy path（mock LLM 返回 Stage 1 + Stage 2 JSON）
  - 过滤无效题目
  - 无可用内容抛出 ValueError
  - slide context_mode 正确加载
  - both context_mode 正确加载
  - user_instruction 正确传递
- `TestTestPaperStats` — 统计 DTO
  - by_bloom_level 正确计算
  - by_question_type 正确计算

---

## Acceptance Criteria

### Functional Requirements

- [x] 从视频字幕和/或幻灯片生成混合开放式大题
- [x] 每道题包含: 题型标签、题目、参考答案、评分要点（list[str]）、布鲁姆认知层次
- [x] LLM 自动选择题型组合，生成至少 2 种不同题型
- [x] 布鲁姆认知层次覆盖至少 3 个不同层次
- [x] 每道题可选关联视频时间戳，支持点击跳转
- [x] 纯展示模式：所有题目列表展示，点击展开参考答案和评分要点
- [x] 支持 context_mode: subtitle / slide / both（严格验证，不接受 auto）
- [x] 异步生成：POST 返回 task_id → SSE 通知完成 → 前端自动刷新
- [x] 支持多语言（按语言存储和获取）
- [x] 支持重新生成（替换旧内容）

### Non-Functional Requirements

- [x] 完全遵循现有 Clean Architecture 分层
- [x] 复用两阶段 LLM 管线（共享 Stage 1 知识提取）
- [x] context_mode 使用共享验证（遵循 context-mode-unification 教训）
- [x] 原子写入存储（tempfile + os.replace）
- [x] 前端键盘可访问（Enter/Space 展开折叠，tabIndex，aria-expanded）

### Quality Gates

- [x] 所有单元测试通过
- [x] 覆盖 validate_test_question 边界情况
- [x] 覆盖 get() 和 generate() 的 happy path + error path
- [x] context_mode=invalid → 400 Bad Request
- [x] 前端 4 种状态（loading/generating/error/content）均正确渲染

---

## Complete File Checklist

### 新建文件（8 个）

| # | 文件路径 | 说明 |
|---|---------|------|
| 1 | `src/deeplecture/use_cases/dto/test_paper.py` | DTO 定义 |
| 2 | `src/deeplecture/use_cases/interfaces/test_paper.py` | Storage Protocol |
| 3 | `src/deeplecture/infrastructure/repositories/fs_test_paper_storage.py` | 文件系统存储 |
| 4 | `src/deeplecture/use_cases/prompts/test_paper.py` | Prompt builder |
| 5 | `src/deeplecture/use_cases/test_paper.py` | Use Case |
| 6 | `src/deeplecture/presentation/api/routes/test_paper.py` | API 路由 |
| 7 | `frontend/lib/api/test-paper.ts` | 前端 API 客户端 |
| 8 | `frontend/components/features/TestTab.tsx` | 前端 Tab 组件 |

### 修改文件（10 个）

| # | 文件路径 | 改动 |
|---|---------|------|
| 9 | `src/deeplecture/use_cases/interfaces/__init__.py` | 添加 TestPaperStorageProtocol export |
| 10 | `src/deeplecture/infrastructure/repositories/__init__.py` | 添加 FsTestPaperStorage export |
| 11 | `src/deeplecture/infrastructure/__init__.py` | 添加 FsTestPaperStorage export |
| 12 | `src/deeplecture/use_cases/prompts/registry.py` | 注册 test_paper_generation prompt |
| 13 | `src/deeplecture/di/container.py` | 添加 test_paper_storage + test_paper_usecase |
| 14 | `src/deeplecture/presentation/api/routes/__init__.py` | 导出 test_paper_bp |
| 15 | `src/deeplecture/presentation/api/app.py` | 注册 blueprint /api/test-paper |
| 16 | `frontend/components/video/TabContentRenderer.tsx` | 动态导入 TestTab + refreshTest prop + 替换 placeholder |
| 17 | `frontend/hooks/useVideoPageState.ts` | 添加 refreshTest 状态 + SSE handler |
| 18 | `frontend/app/video/[id]/VideoPageClient.tsx` | 传递 refreshTest |

### 修改文件（可选，低优先级）

| # | 文件路径 | 改动 |
|---|---------|------|
| 19 | `frontend/lib/taskTypes.ts` | 添加 test_paper_generation 到 TASK_LABELS |

### 新建测试文件（1 个）

| # | 文件路径 | 说明 |
|---|---------|------|
| 20 | `tests/unit/use_cases/test_test_paper.py` | 用例单元测试 |

---

## Dependencies & Prerequisites

- Flashcard feature 当前在 `feat/ai-flashcard-generation` 分支上开发中。Test Paper 功能应在 Flashcard 合并后基于最新代码开发，或在同一分支上继续开发（如果 Flashcard 尚未合并）。
- 需要确认 `cheatsheet_extraction` prompt 的 `coverage_mode="exam_focused"` 行为是否适合 Test Paper 场景。

## Risk Analysis & Mitigation

| 风险 | 影响 | 缓解 |
|------|------|------|
| LLM 生成的题型不够多样 | 所有题都是同一类型 | Prompt 中硬性要求至少 2 种题型，至少 3 个 Bloom 层次 |
| LLM 输出 JSON 格式不规范 | 验证失败，0 道有效题 | 使用现有 `parse_llm_json` 健壮解析 + 逐题验证 |
| bloom_level 标签不一致 | badge 显示异常 | 验证时 lowercase + strip，拒绝不在枚举内的值 |
| context_mode 不一致 | 静默失败（已有教训） | 严格验证 subtitle/slide/both，拒绝 auto |
| 题目数量过多导致 token 消耗高 | 成本和延迟 | Prompt 软引导 5-15 题 |

## Future Considerations（v2+）

- 用户作答输入框 + AI 自动评分/反馈
- 分值计算和总分统计
- 定时考试模式
- 导出为 PDF 试卷
- 题目难度手动配置
- Print-friendly CSS

## References & Research

### Internal References

- 架构模式: `src/deeplecture/use_cases/quiz.py` (完整 Quiz 实现)
- Flashcard 参考: `docs/plans/2026-03-01-feat-ai-flashcard-generation-plan.md`
- Context Mode 教训: `docs/solutions/logic-errors/context-mode-unification-note-quiz-cheatsheet-20260212.md`
- Prompt 注册: `src/deeplecture/use_cases/prompts/registry.py:449-467` (QuizGenerationBuilder)
- DI 容器: `src/deeplecture/di/container.py:196-200` (quiz_storage), `591-603` (quiz_usecase)
- SSE Handler: `frontend/hooks/useVideoPageState.ts:379-387` (quiz_generation branch)
- Tab 注册: `frontend/stores/tabLayoutStore.ts:15` ("test" already in TabId)
- Placeholder: `frontend/components/video/TabContentRenderer.tsx:419-422` (current "test" case)

### Brainstorm Document

- `docs/brainstorms/2026-03-03-test-exam-brainstorm.md`
