## Description

实现 Quiz 小测验功能，从课程字幕生成 MCQ（选择题）小测验。

**核心需求：**
- 在 DRY 前提下复用现有 AI 功能（知识抽取）
- 采用两阶段 LLM 管道：共享知识抽取 + 单次生成含干扰项的 MCQ
- 提供生成/保存/获取 API
- **中等长度 Prompt（60-80 行）**：平衡质量与 token 成本

**Refinement 重点**：
- 具体的 Prompt 算法设计
- 干扰项生成策略（误解多样性）
- JSON 校验与容错机制

## Proposed Solution

### Consensus Summary

**折中方案**：
- **从 Bold 采纳**：知识注入（结构化 KnowledgeItems 而非原文）+ 误解多样性干扰项
- **从 Critique 采纳**：中等长度 Prompt（60-80 行）+ 输出格式前置 + 移除难度控制
- **从 Reducer 采纳**：单阶段生成题目 + 严格 JSON 校验

### Goal

从已有课程内容生成结构化 MCQ 小测验，并提供稳定的 JSON 输出与存储接口。

**Success Criteria:**
- [ ] 生成结果为 JSON 数组，每题 4 选项、1 个正确答案、含简短解释
- [ ] API 能异步生成、读取、保存 Quiz，且失败场景给出明确错误
- [ ] JSON 校验通过（选项数量、答案索引范围、无重复选项）

**Out of Scope (v1):**
- 难度等级控制与标注（研究显示 LLM 准确率仅 37.75%）
- 多轮审稿/双模型校验（成本过高）
- 前端 Quiz/测验 UI（保持占位）
- Bloom 六级认知分类

### Prompt Algorithm Design

#### 1. 中等长度 Prompt（~60-80 行）

```python
def build_quiz_generation_prompts(
    knowledge_items_json: str,
    language: str,
    question_count: int = 5,
    user_instruction: str = "",
) -> tuple[str, str]:
    """Build quiz generation prompt - balanced approach."""

    system_prompt = f"""You are an expert educator creating quiz questions.

OUTPUT FORMAT (CRITICAL - READ FIRST):
Output ONLY a JSON array:
[
  {{
    "stem": "Question text",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer_index": 0,
    "explanation": "Why correct + why each distractor is wrong",
    "source_category": "formula|definition|condition|algorithm|constant|example"
  }}
]

REQUIREMENTS:
- Generate {question_count} questions
- Each question has EXACTLY 4 options
- answer_index is 0-based (0-3)
- Output language: {language}

DISTRACTOR GENERATION:
- Each distractor targets a DIFFERENT misconception type:
  * Computational errors (sign, operator, boundary)
  * Conceptual confusions (similar but distinct terms)
  * Partial understanding (missing key conditions)
  * Over-generalization (applying rule beyond scope)
- Distractors must be plausible but clearly wrong
- NO obviously absurd options

CATEGORY-SPECIFIC HINTS:
- formula: Test calculation, variable identification. Distractors: sign/operator errors
- definition: Test precise terminology. Distractors: related but distinct terms
- condition: Test when/triggers/exceptions. Distractors: necessary vs sufficient
- algorithm: Test step order, termination. Distractors: swapped steps
- constant: Test exact values, units. Distractors: magnitude errors"""

    user_prompt = f"""Generate quiz questions from these knowledge items:

{knowledge_items_json}

{f"Additional instructions: {user_instruction}" if user_instruction else ""}

Return ONLY the JSON array."""

    return system_prompt, user_prompt
```

#### 2. 干扰项生成策略（误解多样性）

| 误解类型 | 示例 |
|---------|------|
| 计算错误 | 符号错误、运算符混淆、边界值错误 |
| 概念混淆 | 相似但不同的术语、因果颠倒 |
| 部分理解 | 缺少关键限定条件、必要非充分 |
| 过度泛化 | 超出规则适用范围 |

**关键原则**：每个干扰项针对不同的误解类型，避免三个选项都是同一种错误的变体。

#### 3. JSON 校验与容错

```python
def validate_quiz_item(item: dict) -> tuple[bool, str]:
    """Validate a single quiz item."""
    # 1. 选项数量检查
    if len(item.get("options", [])) != 4:
        return False, "options must have exactly 4 items"

    # 2. 答案索引检查
    answer_index = item.get("answer_index")
    if not isinstance(answer_index, int) or not 0 <= answer_index <= 3:
        return False, "answer_index must be 0-3"

    # 3. 选项重复检查
    options = item.get("options", [])
    if len(set(options)) != len(options):
        return False, "duplicate options detected"

    # 4. 必填字段检查
    required = ["stem", "options", "answer_index", "explanation"]
    for field in required:
        if not item.get(field):
            return False, f"missing required field: {field}"

    return True, ""
```

### File Changes

| File | Level | Purpose | Est. LOC |
|------|-------|---------|----------|
| `src/deeplecture/use_cases/prompts/quiz.py` | major | Quiz 生成提示词 | 80 |
| `src/deeplecture/use_cases/quiz.py` | major | QuizUseCase（含校验） | 240 |
| `src/deeplecture/use_cases/dto/quiz.py` | major | Quiz DTOs | 120 |
| `src/deeplecture/use_cases/interfaces/quiz.py` | medium | Quiz 存储协议 | 40 |
| `src/deeplecture/infrastructure/repositories/fs_quiz_storage.py` | major | 文件系统存储 | 160 |
| `src/deeplecture/presentation/api/routes/quiz.py` | major | Quiz API | 170 |
| `src/deeplecture/di/container.py` | medium | DI 注入 | 40 |
| `tests/unit/use_cases/test_quiz.py` | medium | Quiz 单测 | 200 |
| `docs/dev/quiz-api.md` | medium | API 文档 | 80 |
| `docs/demo/quiz.md` | minor | 功能演示 | 20 |

### Interface Design

**QuizItem DTO:**
```python
@dataclass
class QuizItem:
    stem: str                    # 题目文本
    options: list[str]           # 4 个选项
    answer_index: int            # 正确答案索引 (0-3)
    explanation: str             # 解析（含每个干扰项错误原因）
    source_category: str | None  # 知识点类别
    source_tags: list[str]       # 知识点标签
```

**QuizUseCase.generate 流程:**
1. 加载上下文（字幕为主）
2. 复用知识抽取提示词生成 `KnowledgeItem`
3. 按 criticality 过滤
4. 调用 quiz 生成提示词，输入结构化 items
5. `parse_llm_json` + 规则校验
6. 过滤非法题目（选项重复、答案越界）
7. 存储 JSON 并返回结果

### Implementation Steps

| Step | Description | Est. LOC | Dependencies |
|------|-------------|----------|--------------|
| 1 | 文档更新 | 110 | None |
| 2 | 测试用例 | 220 | Step 1 |
| 3 | 功能实现 | 900 | Step 2 |

**Total Estimated:** ~1,230 LOC (Medium-High)

**Milestone Strategy:**
- **M1**: 文档 + 测试基线
- **M2**: Quiz use case + 存储 + API
- **Delivery**: 后端可用的 Quiz 生成与读取接口

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM 输出 JSON 失真 | H | H | `parse_llm_json` + 严格校验 + 可选修复调用 |
| 提示词过长导致注意力下降 | M | H | 保持 60-80 行，输出格式置顶 |
| 题目质量不稳 | M | M | prompt registry 切换版本 + 后续 A/B |
| 上下文缺失 | M | M | 明确错误提示 |

### Comparison: Three Proposals → Consensus

| 方面 | Bold (~150 LOC) | Critique | Reducer (~35 LOC) | **Consensus (~80 LOC)** |
|------|-----------------|----------|-------------------|------------------------|
| Prompt 长度 | 150 行 | 太长 | 35 行 | **60-80 行** |
| 难度参数 | 包含 | 移除 | 简化 | **移除 (v1)** |
| 分类指导 | 6 类详细 | 冗余 | 不需要 | **简化为 hints** |
| 干扰项策略 | 详细 | 保留核心 | 依赖 LLM | **误解多样性** |
| JSON 校验 | 无 | 必须加 | 简单 | **严格校验** |
| Token 成本 | ~3200/quiz | 太贵 | ~900/quiz | **~1200/quiz** |

## Related PR

TBD - will be updated when PR is created
