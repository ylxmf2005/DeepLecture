思考前提 - Linus的三个问题
1. 这是个真问题还是臆想出来的？
2. 有更简单的方法吗？
3. 会破坏什么吗？

基于现有信息，我理解您的需求是：用 Linus 的思考与沟通方式，综合三份报告，为“笔记生成去重复/降噪”给出平衡、可实施、文档先行、测试先行的实施计划，并明确具体文件与 LOC 估算。

Linus式问题分解思考
"Bad programmers worry about the code. Good programmers worry about data structures."
- 核心数据是 `NotePart`（id/title/summary/focus_points）和 `context_block`，两者关系是“边界 + 内容源”。
- 数据流是：context → outline(parts) → parallel part expansion，当前 part 不知道兄弟 part。
- 不必要的数据复制：每个 part 重复拿全量 `context_block`，且没有边界约束。

"好代码没有特殊情况"
- 主要 if/else 在 context_mode 选择，非核心问题。
- 真正的问题是“没有边界”：focus_points 没被当作“唯一归属”。
- 通过 outline 约束可消除重复，不需要新 DTO 或 line-range。

"如果实现需要超过3层缩进，重新设计它"
- 本质：让每个 part 只讲自己负责的概念。
- 现在方案引入的概念多（概念图、行号切片）；能砍掉。
- 简化到：outline 规则 + part prompt 认边界。

"Never break userspace"
- 受影响：`/notes/generate` 行为、前端对 `GenerateNoteRequest` 的依赖。
- 破坏风险：新增字段或改变 API。
- 方案：不改请求/响应结构，只改 prompt 和内部传参。

"Theory and practice sometimes clash. Theory loses. Every single time."
- 重复是用户真实感知的问题。
- 复杂切片是“理论优化”，但可靠性差。
- 简单 prompt 约束的收益/风险比最好。

【核心判断】
✅ 值得做：重复是用户体验问题，现有 `focus_points` 已是边界数据，最小改动即可改善，不必引入不可靠的切片。

【关键洞察】
- 数据结构：`NotePart.focus_points` 就是“概念归属表”，应被当作唯一边界。
- 复杂度：不要新增 DTO 或 line-range；让 outline 与 part prompt 承担边界职责。
- 风险点：LLM 生成行号/切片易幻觉，硬切上下文易伤质量。

【Linus式方案】
1. 第一步永远是简化数据结构：沿用 `NotePart`，不新增字段。
2. 消除所有特殊情况：每个 part 明确“只负责自己的 focus_points”。
3. 用最笨但最清晰的方式实现：把完整 outline 写进每个 part prompt。
4. 确保零破坏性：API 不变，并行流程不变。

【品味评分】
🟡 凑合

【致命问题】
- 目前 part prompt 不知道兄弟部分，重复几乎必然。
- 全量 `context_block` 被重复使用且无边界，导致内容漂移与 token 浪费。

# Implementation Plan: Unknown Feature

## Consensus Summary
选择最小改动的“outline-aware prompt”作为主线：用已有 `focus_points` 作为唯一归属，加入同级 outline 约束来减少重复，同时保持并行生成。明确不做 LLM 行号切片和激进上下文裁剪，规避可靠性风险；token 优化作为未来可选项。

## Goal
降低笔记各部分内容重复，维持并行生成与现有 API 不变。

**Success criteria:**
- Outline prompt 明确要求 focus_points 互斥且不重复。
- Part prompt 包含完整 outline 摘要并明确“不得解释其他 parts 的概念”。
- 现有 `GenerateNoteRequest` 与 API 响应结构不变。
- 单元测试覆盖新 prompt 约束与 use case 传参。

**Out of scope:**
- 概念图抽取、LLM 行号/切片、顺序生成流程。
- 激进上下文裁剪与 token 预算调度。
However, it it a good idea for future work?
✅ Good to have in the future: 基于 `focus_points` 的确定性检索（可回退到全量上下文）与 token 计量。
❌ Not needed: 依赖 LLM 产出行号/区间的切片方案，可靠性太差。

## Bug Reproduction
**Skip reason**: 这不是 bug 修复，是质量改进。

## Codebase Analysis

**Files verified (docs/code checked by agents):**
- `src/deeplecture/use_cases/note.py`: context 加载、outline 构建、并行 part 生成流程。
- `src/deeplecture/use_cases/prompts/note.py`: note outline 与 part 的 prompt 结构。
- `src/deeplecture/use_cases/prompts/registry.py`: prompt builder 注册与参数传递。
- `src/deeplecture/config/settings.py`: LLM 配置存在但未用于 max_tokens。
- `src/deeplecture/infrastructure/gateways/openai.py`: LLM 调用未接收 max_tokens。
- `tests/unit/use_cases/test_note.py`: note use case 单元测试现状。
- `docs/README.md`, `docs/demo/notes.md`: 笔记文档几乎空白。

**File changes:**

| File | Level | Purpose |
|------|-------|---------|
| `docs/demo/notes.md` | medium | 记录 outline 边界与去重规则 |
| `docs/README.md` | minor | 更新笔记文档链接与说明 |
| `docs/architecture/note-generation.md` (new) | major | 高层设计与边界约束说明 (Est: 60 LOC) |
| `src/deeplecture/use_cases/prompts/note.py` | medium | outline 互斥规则 + part prompt 兄弟感知 |
| `src/deeplecture/use_cases/prompts/registry.py` | minor | 传递 outline 参数 |
| `src/deeplecture/use_cases/note.py` | medium | 将 outline 传入 part prompt |
| `tests/unit/use_cases/prompts/test_note_prompts.py` (new) | major | prompt 规则单测 (Est: 80 LOC) |
| `tests/unit/use_cases/test_note.py` | medium | use case 传参单测 |

**Modification level definitions:**
- **minor**: Cosmetic or trivial changes (comments, formatting, <10 LOC changed)
- **medium**: Moderate changes to existing logic (10-50 LOC, no interface changes)
- **major**: Significant structural changes (>50 LOC, interface changes, or new files)
- **remove**: File deletion

**Current architecture notes:**
`NoteUseCase` 构建全量 `context_block`，outline 与每个 part 都使用同一上下文，part prompt 未感知兄弟 part，重复不可避免；`focus_points` 已存在但未被当作强约束。

## Interface Design

**New interfaces:**
无。

**Modified interfaces:**
`build_note_part_prompt` 新增 `outline` 参数，用于生成“兄弟部分摘要”并加入排他规则。

```diff
- def build_note_part_prompt(..., part: NotePart) -> tuple[str, str]:
+ def build_note_part_prompt(..., part: NotePart, outline: list[NotePart] | None = None) -> tuple[str, str]:
```

`NotePartBuilder.build` 透传 `outline`：

```diff
- part=kwargs["part"],
+ part=kwargs["part"],
+ outline=kwargs.get("outline"),
```

`NoteUseCase._generate_parts_parallel` 传入 outline：

```diff
- part=part,
+ part=part,
+ outline=outline,
```

**Documentation changes:**
- `docs/demo/notes.md` — 添加“outline 互斥与 part 边界”说明
- `docs/README.md` — 更新笔记文档链接
- `docs/architecture/note-generation.md` — 新增生成流程与边界规则

## Documentation Planning

### High-level design docs (docs/)
- `docs/architecture/note-generation.md` — create/update 说明 outline 边界与并行生成策略

```diff
+ # Note Generation Architecture
+ ## Data model
+ - NotePart(id/title/summary/focus_points) 是唯一边界表
+ ## Generation flow
+ - context_block -> outline(parts) -> parallel part expansion
+ ## Boundary rules
+ - focus_points 必须互斥
+ - 每个 part 只解释自己的 focus_points
```

### Folder READMEs
- `docs/README.md` — update 笔记文档链接与说明

```diff
- - **[笔记](features/notes.md)** - WYSIWYG + KaTeX，自动关联视频时间点
+ - **[笔记](demo/notes.md)** - Outline 驱动的笔记生成，减少重复内容
```

### Interface docs
- 无（当前无 `.md` 接口伴随文档）

### Demo docs
- `docs/demo/notes.md` — update 说明 outline 互斥与 part 边界

```diff
- # 笔记
+ # 笔记
+ ## 生成规则
+ - Outline 的 focus_points 必须互斥，不允许重复概念
+ - 每个 Part 只解释自己的 focus_points
+ - 允许 1–2 句必要前置，但不得展开兄弟部分内容
```

## Test Strategy

**Test modifications:**
- `tests/unit/use_cases/test_note.py` — 新增用例：`_generate_parts_parallel` 调用 prompt builder 时包含 `outline`。

**New test files:**
- `tests/unit/use_cases/prompts/test_note_prompts.py` — 用例：outline prompt 包含“互斥/不重复”规则；part prompt 包含 outline 摘要与“不得解释其他部分”规则。

**Test data required:**
- 无（使用最小 `NotePart` 构造即可）。

## Implementation Steps

**Step 1: Documentation change** (Estimated: 100 LOC)
File changes: `docs/demo/notes.md`, `docs/README.md`, `docs/architecture/note-generation.md`
Dependencies: None
Correspondence: Docs: 记录 outline 互斥规则与并行生成流程；Tests: 提供可验证的行为描述。

**Step 2: Test case changes** (Estimated: 120 LOC)
File changes: `tests/unit/use_cases/prompts/test_note_prompts.py`, `tests/unit/use_cases/test_note.py`
Dependencies: Step 1
Correspondence: Docs: 对齐“互斥 focus_points”“兄弟感知”描述；Tests: 覆盖 prompt 文本与 use case 传参。

**Step 3: Implementation change** (Estimated: 90 LOC)
File changes: `src/deeplecture/use_cases/prompts/note.py`, `src/deeplecture/use_cases/prompts/registry.py`, `src/deeplecture/use_cases/note.py`
Dependencies: Step 2
Correspondence: Docs: 实现 outline 互斥与 part 边界规则；Tests: 满足新 prompt 与传参断言。

**Total estimated complexity:** 310 LOC (medium)
**Recommended approach:** Single session

## Success Criteria

- [ ] Outline prompt 强制 focus_points 互斥且不重复
- [ ] Part prompt 包含完整 outline 摘要并排除其他 parts
- [ ] API 请求/响应结构保持不变
- [ ] 新增单元测试全部通过

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM 仍出现跨 part 重复 | M | M | outline 互斥规则 + 兄弟感知 prompt 强约束 |
| 过度约束导致解释不完整 | M | M | 允许 1–2 句前置，不展开他人内容 |
| doc 与实现漂移 | L | M | 文档先行 + prompt 单测覆盖 |

## Dependencies

无新增外部依赖；继续使用现有 LLM provider 与 pytest。
