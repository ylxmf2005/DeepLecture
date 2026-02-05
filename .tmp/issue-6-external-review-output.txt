思考前提 - Linus的三个问题
```text
1. "这是个真问题还是臆想出来的？" - 拒绝过度设计
2. "有更简单的方法吗？" - 永远寻找最简方案
3. "会破坏什么吗？" - 向后兼容是铁律
```

基于现有信息，我理解您的需求是：在 DRY 的前提下复用现有 AI 生成与存储/路由模式，实现“Quiz 小测验”功能，生成 MCQ 题并提供最小可用的生成/保存/获取接口，避免过度工程化。

Linus式问题分解思考
第一层：数据结构分析
"Bad programmers worry about the code. Good programmers worry about data structures."
- 核心数据：字幕文本 → 知识点列表 → 题目列表
- 数据流向：字幕存储读取 → LLM 生成 → 文件存储 → API 返回
- 需要避免：把“知识点”绑死在 cheatsheet 内部、重复 JSON 解析逻辑

第二层：特殊情况识别
"好代码没有特殊情况"
- 分支来自：空字幕、题目数不足、LLM 输出非 JSON
- 真正业务逻辑：从内容生成可用题目
- 消除方式：统一 JSON 解析 + 最小 fallback + 题目数量截断

第三层：复杂度审查
"如果实现需要超过3层缩进，重新设计它"
- 本质一句话：从内容生成一组 MCQ 并落盘
- 概念越少越好：两阶段足够（抽取 + 生成含干扰项）
- Bloom/三阶段/复习调度先砍掉

第四层：破坏性分析
"Never break userspace"
- 受影响功能：cheatsheet 抽取逻辑
- 依赖风险：抽取逻辑移动或改名
- 处理：引入共享抽取器并在 cheatsheet 中调用，保留旧接口行为

第五层：实用性验证
"Theory and practice sometimes clash. Theory loses. Every single time."
- 这是实际需求：路线图已明确 Quiz 功能
- 真用户痛点：快速自测
- 复杂度与收益匹配：两次 LLM 调用能控制成本

决策输出模式
【核心判断】
✅ 值得做：需求真实且高优先级，能以两阶段方案满足 DRY 与成本约束

【关键洞察】
- 数据结构：KnowledgeItem 作为共享中间态足够
- 复杂度：三阶段与 Bloom 校准是冗余
- 风险点：抽取逻辑重构可能影响 cheatsheet 结果

【Linus式方案】
1. 第一步永远是简化数据结构：共享 KnowledgeItem
2. 消除所有特殊情况：统一 JSON 解析与题数截断
3. 用最笨但最清晰的方式实现：两阶段、单次生成题目
4. 确保零破坏性：cheatsheet 行为不变

代码审查输出
【品味评分】
🟡 凑合

【致命问题】
- 试图调用私有抽取方法，实际不可复用
- 并行组常量未扩展却被引用，类型不一致

**Implementation Plan: Unknown Feature**

**Consensus Summary**
采用两阶段 LLM：共享知识抽取 + 单次生成含干扰项的 MCQ，保留 DRY 和已有架构模式。避免 Bloom 六级、三阶段管线、间隔重复与双模型评审等过度复杂，控制成本与维护面。

**Goal**
从课程字幕生成 MCQ 小测验并支持生成/保存/获取 API，复用现有 LLM、存储与路由模式。

**Success criteria:**
- 生成接口返回指定数量的 MCQ，包含选项、正确答案与简短解析
- 生成结果可持久化并通过 GET 接口读取
- Cheatsheet 功能行为不变，抽取逻辑由共享组件驱动

**Out of scope:**
- Bloom 六级难度标注与分层评估
- 间隔重复/自适应会话跟踪
- 多题型（填空、判断、主观题）
✅ Good to have in the future: 在用户反馈基础上引入难度分级与题型扩展
❌ Not needed: 双 LLM 评审与误区建模，当前缺乏真实收益证据

**Bug Reproduction**
Skip reason: 新功能规划，无可复现缺陷

**Codebase Analysis**
**Files verified (docs/code checked by agents):**
- `README.md`: 路线图已包含 Quiz
- `docs/README.md`: 功能文档入口
- `docs/demo/*.md`: 现有 demo 文档模式
- `src/deeplecture/use_cases/cheatsheet.py`: 两阶段抽取/渲染流程与私有抽取方法
- `src/deeplecture/use_cases/dto/cheatsheet.py`: KnowledgeItem 结构
- `src/deeplecture/use_cases/prompts/cheatsheet.py`: 抽取提示词
- `src/deeplecture/use_cases/shared/llm_json.py`: JSON 解析工具
- `src/deeplecture/use_cases/interfaces/parallel.py`: ParallelGroup 固定值
- `src/deeplecture/infrastructure/repositories/fs_cheatsheet_storage.py`: 文件存储模式
- `src/deeplecture/infrastructure/repositories/fs_timeline_storage.py`: JSON 存储模式
- `src/deeplecture/presentation/api/routes/cheatsheet.py`: API 模式
- `src/deeplecture/presentation/api/app.py`: blueprint 注册
- `src/deeplecture/di/container.py`: 依赖注入模式
- `tests/unit/use_cases/test_note.py`: UseCase 单测风格

**File changes:**

| File | Level | Purpose |
|------|-------|---------|
| `src/deeplecture/use_cases/dto/knowledge.py` (new) | major | 共享 KnowledgeItem（Est: 40 LOC） |
| `src/deeplecture/use_cases/shared/knowledge_extractor.py` (new) | major | 共享知识抽取器（Est: 90 LOC） |
| `src/deeplecture/use_cases/dto/quiz.py` (new) | major | Quiz DTO 定义（Est: 90 LOC） |
| `src/deeplecture/use_cases/prompts/quiz.py` (new) | major | Quiz 生成提示词（Est: 90 LOC） |
| `src/deeplecture/use_cases/interfaces/quiz.py` (new) | major | QuizStorageProtocol（Est: 40 LOC） |
| `src/deeplecture/use_cases/quiz.py` (new) | major | QuizUseCase（Est: 200 LOC） |
| `src/deeplecture/infrastructure/repositories/fs_quiz_storage.py` (new) | major | Quiz 文件存储（Est: 110 LOC） |
| `src/deeplecture/presentation/api/routes/quiz.py` (new) | major | Quiz API 路由（Est: 130 LOC） |
| `docs/demo/quiz.md` (new) | minor | Quiz 使用说明（Est: 40 LOC） |
| `tests/unit/use_cases/test_quiz.py` (new) | major | QuizUseCase 单测（Est: 140 LOC） |
| `tests/unit/use_cases/shared/test_knowledge_extractor.py` (new) | medium | 抽取器单测（Est: 80 LOC） |
| `tests/unit/infrastructure/test_fs_quiz_storage.py` (new) | medium | Quiz 存储单测（Est: 90 LOC） |
| `src/deeplecture/use_cases/cheatsheet.py` | medium | 调用共享抽取器 |
| `src/deeplecture/use_cases/dto/cheatsheet.py` | minor | 重导出 KnowledgeItem |
| `src/deeplecture/use_cases/shared/__init__.py` | minor | 导出抽取器 |
| `src/deeplecture/use_cases/interfaces/__init__.py` | minor | 导出 QuizStorageProtocol |
| `src/deeplecture/infrastructure/repositories/__init__.py` | minor | 导出 FsQuizStorage |
| `src/deeplecture/infrastructure/__init__.py` | minor | 导出 FsQuizStorage |
| `src/deeplecture/di/container.py` | medium | 注入 quiz storage/usecase |
| `src/deeplecture/presentation/api/routes/__init__.py` | minor | 导出 quiz blueprint |
| `src/deeplecture/presentation/api/app.py` | minor | 注册 quiz blueprint |
| `docs/README.md` | minor | 增加 Quiz 文档入口 |

**Modification level definitions:**
- minor: Cosmetic or trivial changes (<10 LOC)
- medium: Moderate changes (10–50 LOC, no interface break)
- major: Significant structural changes (>50 LOC or new files)
- remove: File deletion

**Current architecture notes:**
- UseCase 层有两阶段 LLM 模式与明确的 Storage Protocol
- 统一 JSON 解析工具 `parse_llm_json` 已存在，可复用

**Interface Design**
**New interfaces:**
- `QuizStorageProtocol`
  - `load(content_id: str) -> tuple[dict[str, Any], datetime | None] | None`
  - `save(content_id: str, payload: dict[str, Any]) -> datetime`
  - `exists(content_id: str) -> bool`
  - 数据结构：payload 至少包含 `questions` 数组与 `language`、`used_sources`

- `extract_knowledge_items(llm, context, language, subject_type, user_instruction) -> list[KnowledgeItem]`
  - Step 1: 构建抽取提示词并调用 LLM
  - Step 2: 使用 `parse_llm_json` 解析结果并归一化为 list
  - Step 3: 过滤空内容，返回 `KnowledgeItem` 列表

**Data structures:**
- `KnowledgeItem`: `category`, `content`, `criticality`, `tags`
- `QuizQuestion`: `stem`, `options`, `answer_index`, `explanation`, `difficulty`(可选)
- `GenerateQuizRequest`: `content_id`, `language`, `context_mode`, `question_count`, `difficulty`, `min_criticality`, `subject_type`, `user_instruction`
- `QuizResult`: `content_id`, `questions`, `updated_at`
- `GeneratedQuizResult`: `content_id`, `questions`, `updated_at`, `used_sources`, `stats`
- `QuizStats`: `total_questions`

**QuizUseCase.generate**
- Step 1: 加载字幕上下文（沿用 cheatsheet 的 context_mode 语义）
- Step 2: 调用共享抽取器获得 KnowledgeItem 并按 criticality 过滤
- Step 3: 生成提示词，单次 LLM 输出 N 道 MCQ（含干扰项与解析）
- Step 4: JSON 解析与截断，保存并返回统计信息

**Modified interfaces:**
```diff
- @dataclass
- class KnowledgeItem:
-     ...
+ from deeplecture.use_cases.dto.knowledge import KnowledgeItem
```

**Documentation changes:**
- `docs/README.md` — 增加 Quiz 文档入口
- `docs/demo/quiz.md` — 新增 Quiz 使用说明

**Documentation Planning**
### High-level design docs (docs/)
- `docs/README.md` — update 入口列表，添加 Quiz 链接
```diff
- ### 笔记与学习
- - **[笔记](features/notes.md)** - WYSIWYG + KaTeX，自动关联视频时间点
+ ### 笔记与学习
+ - **[笔记](features/notes.md)** - WYSIWYG + KaTeX，自动关联视频时间点
+ - **[Quiz 小测验](demo/quiz.md)** - AI 根据视频内容生成测验题
```

### Folder READMEs
- None — 该路径下无模块 README，暂不新增

### Interface docs
- None — 现有接口无对应 .md，v1 不新增接口文档

新文档草案
```diff
+ # Quiz 小测验
+
+ 生成并保存 MCQ 小测验，支持按内容获取与再生成。
+
+ ## API
+ - POST /api/quiz/generate
+ - GET /api/quiz?content_id=...
+ - POST /api/quiz
```

**Test Strategy**
**Test modifications:**
- `tests/unit/use_cases/test_quiz.py` — cases: get 空返回; save 落盘; generate 缺内容抛错; generate 题数截断; JSON fallback
- `tests/unit/use_cases/shared/test_knowledge_extractor.py` — cases: 正常 JSON; 非法 JSON fallback; 空响应返回空列表
- `tests/unit/infrastructure/test_fs_quiz_storage.py` — cases: save/load/exists; JSON 解析失败处理

**Test data required:**
- 伪字幕片段与固定 LLM 输出 JSON 字符串

**Implementation Steps**
- Step 1: Documentation change (Est: 80 LOC). Files: `docs/README.md`, `docs/demo/quiz.md`. Dependencies: None. Correspondence: Docs: 新增 Quiz 文档入口与说明; Tests: N/A.
- Step 2: Test case changes (Est: 310 LOC). Files: `tests/unit/use_cases/test_quiz.py`, `tests/unit/use_cases/shared/test_knowledge_extractor.py`, `tests/unit/infrastructure/test_fs_quiz_storage.py`. Dependencies: Step 1. Correspondence: Docs: 约束输出结构与 API 参数; Tests: 定义生成/解析/存储行为。
- Step 3: Shared extraction refactor (Est: 130 LOC). Files: `src/deeplecture/use_cases/dto/knowledge.py`, `src/deeplecture/use_cases/shared/knowledge_extractor.py`, `src/deeplecture/use_cases/cheatsheet.py`, `src/deeplecture/use_cases/dto/cheatsheet.py`, `src/deeplecture/use_cases/shared/__init__.py`. Dependencies: Step 2. Correspondence: Docs: 抽取作为共用组件; Tests: 抽取器与 cheatsheet 不回归。
- Step 4: Quiz DTOs + prompts (Est: 180 LOC). Files: `src/deeplecture/use_cases/dto/quiz.py`, `src/deeplecture/use_cases/prompts/quiz.py`. Dependencies: Step 3. Correspondence: Docs: 题目 JSON 结构; Tests: DTO 序列化与 prompt 输出约束。
- Step 5: Storage protocol + FS storage + exports (Est: 170 LOC). Files: `src/deeplecture/use_cases/interfaces/quiz.py`, `src/deeplecture/infrastructure/repositories/fs_quiz_storage.py`, `src/deeplecture/use_cases/interfaces/__init__.py`, `src/deeplecture/infrastructure/repositories/__init__.py`, `src/deeplecture/infrastructure/__init__.py`. Dependencies: Step 4. Correspondence: Docs: 持久化格式; Tests: 存储读写用例。
- Step 6: QuizUseCase (Est: 200 LOC). Files: `src/deeplecture/use_cases/quiz.py`. Dependencies: Step 5. Correspondence: Docs: 生成流程; Tests: 生成/保存/获取逻辑。
- Step 7: API + DI wiring (Est: 210 LOC). Files: `src/deeplecture/presentation/api/routes/quiz.py`, `src/deeplecture/presentation/api/routes/__init__.py`, `src/deeplecture/presentation/api/app.py`, `src/deeplecture/di/container.py`. Dependencies: Step 6. Correspondence: Docs: API 路由; Tests: 用例可通过调用 usecase 验证。

**Total estimated complexity:** 880 LOC (Medium)
**Recommended approach:** Milestone commits
**Milestone strategy:**
- **M1**: 文档与测试落地
- **M2**: 共享抽取 + DTO + prompt
- **M3**: 存储 + UseCase
- **Delivery**: API 路由与 DI 注入完成

**Success Criteria**
- [ ] 生成接口返回结构化 MCQ 且数量可控
- [ ] 生成结果可保存与读取
- [ ] Cheatsheet 抽取逻辑未回归

**Risks and Mitigations**

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 抽取重构影响 cheatsheet 结果 | M | M | 使用相同 prompt + JSON 解析; 增加回归测试 |
| LLM 输出非 JSON | H | M | 统一 `parse_llm_json` + fallback |
| 题量过大导致 token 超限 | M | M | 题数上限与知识点截断 |
| 知识点结构不适配题目 | M | M | prompt 中要求基于 `content` 生成，后续再扩展字段 |

**Dependencies**
- 无新增外部依赖；复用现有 LLMProvider、json_repair、存储与路由结构
