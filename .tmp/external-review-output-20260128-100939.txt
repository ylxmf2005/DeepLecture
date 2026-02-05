思考前提（Linus 三问）
1. 这是个真问题还是臆想出来的？这是产品 Roadmap 明确写了“Quiz 小测验”，是现实需求。
2. 有更简单的方法吗？有，复用现有知识抽取，保持提示词短小。
3. 会破坏什么吗？不该破坏现有接口；新增为主，避免改旧 API 语义。

基于现有信息，我理解您的需求是：综合三份报告的优缺点，给出一份能在本仓库落地的 Quiz 生成方案，既保留“知识注入、误区干扰项”的关键想法，又砍掉冗长提示词与不可靠的难度控制，并补上 JSON 校验与文档/测试顺序。

第一层：数据结构分析
- 核心数据：`KnowledgeItem`（已有）→ `QuizItem`（新增）。
- 数据流：字幕/幻灯 → 知识抽取 → 题目生成 → JSON 校验 → 存储/返回。
- 不必要复制：避免把全文塞进生成阶段，改用结构化 KnowledgeItems。

第二层：特殊情况识别
- 空字幕/无上下文：直接失败，别“胡编”。
- LLM 输出非 JSON：必须修复或丢弃，不能默默吞掉。
- 选项重复/答案越界：必须过滤或修复，不允许带病保存。

第三层：复杂度审查
- 功能本质：从内容生成可用的 MCQ JSON。
- 当前方案概念太多：难度分级、分类细则、链式推理都不是必需品。
- 目标：两阶段（抽取+生成）就够，提示词压到 ~60–80 行。

第四层：破坏性分析
- 新增接口与存储，不动现有接口；旧功能无回归。
- 不引入新依赖，减少环境破坏面。

第五层：实用性验证
- Quiz 是真实痛点（Roadmap 已列）。
- 用户真实会用（复习/测验）。
- 解决方案复杂度与价值匹配。

【核心判断】
✅ 值得做：功能真实、实现可控、能复用现有抽取管线。

【关键洞察】
- 数据结构：`KnowledgeItem` 是最好的“知识注入”载体，别再喂一遍原文。
- 复杂度：砍掉难度控制与冗长分类说明，保留最关键的“输出格式 + 干扰项多样性”。
- 风险点：LLM JSON 失真与选项重复，需要硬校验。

【Linus式方案】
1. 第一步永远是简化数据结构：输入结构化 items，而不是长文本。
2. 消除所有特殊情况：严格 JSON 校验与修复/过滤。
3. 用最笨但最清晰的方式实现：两阶段、一个提示词、一个校验函数。
4. 确保零破坏性：新接口、新存储，旧接口不动。

【品味评分】
🟡 凑合（现有 prompts 结构清晰，但 cheatsheet 使用 async + LLMProvider 方式不一致，属于技术债）

【致命问题】
- LLM 输出缺少统一校验层：不加校验就是在写脆弱软件。

**实施计划：Unknown Feature（Quiz 生成）**

**Consensus Summary**
折中方案：复用已有知识抽取做“知识注入”（大胆派），但把 quiz 生成提示词压缩为中等长度、并把输出格式前置（批评派），去掉不可靠的难度控制并单阶段生成题目（简化派）。新增 JSON 校验与最小化修复逻辑，保证可用性。

**Goal**
从已有课程内容生成结构化 MCQ 小测验，并提供稳定的 JSON 输出与存储接口。

**Success criteria:**
- 生成结果为 JSON 数组，每题 4 选项、1 个正确答案、含简短解释。
- API 能异步生成、读取、保存 Quiz，且失败场景给出明确错误。

**Out of scope:**
- 前端 Quiz/测验 UI（保持占位）。
- 难度等级控制与标注（v1 不做）。
- 多轮审稿/双模型校验（成本过高）。
- ✅ 未来可做：可选难度与题目审校开关，基于真实质量数据再加。
- ❌ 不需要：长篇分类说明与链式推理提示词，投入产出太差。

**Bug Reproduction**
**Skip reason**：新功能规划，不是缺陷修复。

**Codebase Analysis**
**Files verified (docs/code checked by agents):**
- `docs/README.md`：当前仅有功能演示索引，无接口说明。
- `README.md`：Roadmap 含 Quiz 需求。
- `src/deeplecture/use_cases/cheatsheet.py`：两阶段抽取与渲染模式。
- `src/deeplecture/use_cases/prompts/cheatsheet.py`：KnowledgeItem 抽取提示词。
- `src/deeplecture/use_cases/prompts/registry.py`：prompt 注册与选择机制。
- `src/deeplecture/use_cases/shared/llm_json.py`：json_repair 解析工具。
- `src/deeplecture/infrastructure/repositories/fs_timeline_storage.py`：JSON 存储与隔离坏文件模式。
- `src/deeplecture/presentation/api/routes/cheatsheet.py`：生成/保存/读取 API 模式。
- `src/deeplecture/di/container.py`：依赖注册模式。
- `src/deeplecture/presentation/api/app.py`：蓝图注册。

**File changes:**

| File | Level | Purpose |
|------|-------|---------|
| `src/deeplecture/use_cases/prompts/quiz.py` | major | 新增 quiz 生成提示词（Est: 80 LOC） |
| `src/deeplecture/use_cases/quiz.py` | major | 新增 QuizUseCase（Est: 240 LOC） |
| `src/deeplecture/use_cases/dto/quiz.py` | major | Quiz DTOs（Est: 120 LOC） |
| `src/deeplecture/use_cases/interfaces/quiz.py` | medium | Quiz 存储协议（Est: 40 LOC） |
| `src/deeplecture/infrastructure/repositories/fs_quiz_storage.py` | major | 文件系统存储（Est: 160 LOC） |
| `src/deeplecture/use_cases/prompts/registry.py` | medium | 注册 quiz prompt builder（Est: 30 LOC） |
| `src/deeplecture/di/container.py` | medium | 注入 quiz storage/usecase（Est: 40 LOC） |
| `src/deeplecture/presentation/api/routes/quiz.py` | major | Quiz API（Est: 170 LOC） |
| `src/deeplecture/presentation/api/routes/__init__.py` | minor | 导出 quiz blueprint（Est: 5 LOC） |
| `src/deeplecture/presentation/api/app.py` | minor | 注册 quiz blueprint（Est: 5 LOC） |
| `src/deeplecture/use_cases/interfaces/__init__.py` | minor | 导出 QuizStorageProtocol（Est: 5 LOC） |
| `src/deeplecture/use_cases/dto/__init__.py` | minor | 导出 Quiz DTOs（Est: 5 LOC） |
| `src/deeplecture/infrastructure/repositories/__init__.py` | minor | 导出 FsQuizStorage（Est: 5 LOC） |
| `tests/unit/use_cases/test_quiz.py` | medium | Quiz 用例与校验测试（Est: 200 LOC） |
| `tests/integration/presentation/api/test_route_smoke.py` | minor | Quiz 路由冒烟测试（Est: 20 LOC） |
| `docs/dev/quiz-api.md` (new) | medium | Quiz API 文档（Est: 80 LOC） |
| `docs/demo/quiz.md` (new) | minor | 功能演示文档（Est: 20 LOC） |
| `docs/README.md` | minor | 文档索引新增 Quiz（Est: 10 LOC） |

**Current architecture notes**
- Prompts 通过 `use_cases/prompts/*` 定义，注册到 `PromptRegistry`。
- JSON 类输出使用 `parse_llm_json` 修复与兜底。
- 存储统一落地在 `content/{content_id}/...` 目录。
- 长任务通过 TaskManager 异步执行。

**Interface Design**

**New interfaces:**
- `GenerateQuizRequest`（`src/deeplecture/use_cases/dto/quiz.py`）
  - `content_id`, `language`, `context_mode`, `question_count`, `user_instruction`, `min_criticality`, `subject_type`, `llm_model`, `prompts`
- `QuizItem`
  - `stem`, `options`, `answer_index`, `explanation`, `source_category`, `source_tags`
- `QuizResult` / `GeneratedQuizResult`
  - `content_id`, `language`, `items`, `updated_at`, `used_sources`, `stats`
- `QuizStorageProtocol`（`src/deeplecture/use_cases/interfaces/quiz.py`）
  - `load(content_id, language)`, `save(report)`, `exists(content_id, language)`

**Internal algorithm steps (QuizUseCase.generate):**
- Step 1: 加载上下文（字幕为主）。
- Step 2: 复用知识抽取提示词生成 `KnowledgeItem`。
- Step 3: 按 criticality 过滤。
- Step 4: 调用 quiz 生成提示词，输入结构化 items。
- Step 5: `parse_llm_json` + 规则校验（选项长度、重复、答案越界）。
- Step 6: 失败时可选一次“格式修复”调用，否则丢弃非法题。
- Step 7: 存储 JSON 并返回结果。

**Modified interfaces:**
`src/deeplecture/use_cases/prompts/registry.py`
```diff
+class QuizGenerationBuilder(BasePromptBuilder):
+    """Builder for quiz generation prompts."""
+    def build(self, **kwargs) -> PromptSpec:
+        from deeplecture.use_cases.prompts.quiz import build_quiz_generation_prompts
+        user_prompt, system_prompt = build_quiz_generation_prompts(
+            knowledge_items_json=kwargs["knowledge_items_json"],
+            language=kwargs["language"],
+            question_count=kwargs.get("question_count", 5),
+            user_instruction=kwargs.get("user_instruction", ""),
+        )
+        return PromptSpec(user_prompt=user_prompt, system_prompt=system_prompt)
```

**Documentation changes:**
- `docs/dev/quiz-api.md`：新增 API 接口与请求/响应结构。
- `docs/demo/quiz.md`：新增功能演示文档。
- `docs/README.md`：索引加入 Quiz。

**Documentation Planning**
### High-level design docs (docs/)
- `docs/dev/quiz-api.md` — 新增 Quiz API 说明（当前 docs/ 无接口文档，仅功能演示，见 `docs/README.md`）
```diff
+ # Quiz API
+ ## POST /api/quiz/generate
+ Request: content_id, language, question_count, context_mode, user_instruction, subject_type, min_criticality
+ Response: task_id, status, message
+ ## GET /api/quiz
+ Query: content_id, language
+ Response: items[], updatedAt
```

### Folder READMEs
- `docs/README.md` — 新增 Quiz 演示入口
```diff
+### 笔记与学习
+- **[Quiz 小测验](demo/quiz.md)** - AI 根据课程内容生成选择题
```

### Interface docs
- `docs/demo/quiz.md` — 功能演示说明
```diff
+ # Quiz 小测验
+ 生成基于课程内容的 4 选项选择题，用于复习与自测。
```

**Test Strategy**

**Test modifications:**
- `tests/unit/use_cases/test_quiz.py` — 覆盖 QuizUseCase 的抽取、生成、校验、过滤
- `Test case: JSON 修复成功解析`
- `Test case: answer_index 越界题被剔除`
- `Test case: options 重复被剔除`

**New test files:**
- `tests/unit/use_cases/test_quiz.py` — Quiz 逻辑与校验（Estimated: 200 LOC）

**Test data required:**
- 内联样例 JSON（无需额外 fixture 文件）

**Implementation Steps**

**Step 1: 文档更新** (Estimated: 110 LOC)
- File changes: `docs/dev/quiz-api.md`, `docs/demo/quiz.md`, `docs/README.md`
- Dependencies: None
- Correspondence: Docs: 新增接口与演示说明；Tests: N/A

**Step 2: 测试用例** (Estimated: 220 LOC)
- File changes: `tests/unit/use_cases/test_quiz.py`, `tests/integration/presentation/api/test_route_smoke.py`
- Dependencies: Step 1
- Correspondence: Docs: `docs/dev/quiz-api.md`；Tests: Quiz 校验与路由存在性

**Step 3: 功能实现** (Estimated: 900 LOC)
- File changes: `src/deeplecture/use_cases/quiz.py`, `src/deeplecture/use_cases/prompts/quiz.py`, `src/deeplecture/use_cases/dto/quiz.py`, `src/deeplecture/use_cases/interfaces/quiz.py`, `src/deeplecture/infrastructure/repositories/fs_quiz_storage.py`, `src/deeplecture/use_cases/prompts/registry.py`, `src/deeplecture/di/container.py`, `src/deeplecture/presentation/api/routes/quiz.py`, `src/deeplecture/presentation/api/app.py`, `src/deeplecture/presentation/api/routes/__init__.py`, `src/deeplecture/use_cases/interfaces/__init__.py`, `src/deeplecture/use_cases/dto/__init__.py`, `src/deeplecture/infrastructure/repositories/__init__.py`
- Dependencies: Step 2
- Correspondence: Docs: `docs/dev/quiz-api.md`；Tests: `tests/unit/use_cases/test_quiz.py`, `tests/integration/presentation/api/test_route_smoke.py`

**Total estimated complexity:** ~1,230 LOC (Medium-High)
**Recommended approach:** Milestone commits
**Milestone strategy**
- **M1**: 文档 + 测试基线
- **M2**: Quiz use case + 存储 + API
- **Delivery**: 后端可用的 Quiz 生成与读取接口

**Success Criteria**
- [ ] `/api/quiz/generate` 可提交任务并落盘结果
- [ ] 生成结果通过 JSON 校验（4 选项、答案索引正确）
- [ ] 无字幕/无上下文时返回明确错误

**Risks and Mitigations**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM 输出 JSON 失真 | H | H | `parse_llm_json` + 严格校验 + 可选一次修复调用 |
| 提示词过长导致注意力下降 | M | H | 保持 60–80 行，输出格式置顶 |
| 题目质量不稳 | M | M | 允许 prompt registry 切换版本 + 后续 A/B |
| 上下文缺失 | M | M | 明确错误提示 + 未来加入 slide context |

**Dependencies**
- 无新增第三方依赖（复用现有 `json_repair` 与 LLM provider）
- 依赖已存在字幕/内容存储体系

如果你希望把前端 Quiz UI 也纳入范围，或者想直接沿用 cheatsheet 的 async 模式，我会先砍掉不必要的复杂度再给你一份更小的实现路径。
