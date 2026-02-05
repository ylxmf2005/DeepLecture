## Description

笔记生成算法存在两个核心问题：
1. **内容重复**：每个 Part 独立生成且不知道兄弟 Part 的存在，导致 Kerckhoffs 原则、CIA 三要素等概念在 3-4 个 Part 中重复讲解
2. **Token 浪费**：每个 Part 都接收完整的 context_block（字幕/幻灯片全文），N 个 Part × 完整上下文 = 巨大的 token 开销

**相关模块**：`use_cases/note.py`, `use_cases/prompts/note.py`, `dto/note.py`

## Proposed Solution

### Linus 式核心判断

> "Bad programmers worry about the code. Good programmers worry about data structures."

- 核心数据是 `NotePart`（id/title/summary/focus_points）和 `context_block`
- 真正的问题是"没有边界"：`focus_points` 没被当作"唯一归属"
- 通过 outline 约束可消除重复，不需要新 DTO 或 line-range 切片

### 共识方案：Outline-Aware Prompt（最小改动）

选择最小改动的"outline-aware prompt"作为主线：
- 用已有 `focus_points` 作为唯一归属
- 加入同级 outline 约束来减少重复
- 保持并行生成与现有 API 不变
- **明确不做**：LLM 行号切片、激进上下文裁剪（可靠性风险太高）

### Success Criteria

- [ ] Outline prompt 强制 focus_points 互斥且不重复
- [ ] Part prompt 包含完整 outline 摘要并排除其他 parts
- [ ] API 请求/响应结构保持不变
- [ ] 新增单元测试全部通过

### File Changes

| File | Level | Purpose |
|------|-------|---------|
| `docs/demo/notes.md` | medium | 记录 outline 边界与去重规则 |
| `docs/architecture/note-generation.md` (new) | major | 高层设计与边界约束说明 (~60 LOC) |
| `src/deeplecture/use_cases/prompts/note.py` | medium | outline 互斥规则 + part prompt 兄弟感知 |
| `src/deeplecture/use_cases/prompts/registry.py` | minor | 传递 outline 参数 |
| `src/deeplecture/use_cases/note.py` | medium | 将 outline 传入 part prompt |
| `tests/unit/use_cases/prompts/test_note_prompts.py` (new) | major | prompt 规则单测 (~80 LOC) |
| `tests/unit/use_cases/test_note.py` | medium | use case 传参单测 |

### Interface Changes

```diff
- def build_note_part_prompt(..., part: NotePart) -> tuple[str, str]:
+ def build_note_part_prompt(..., part: NotePart, outline: list[NotePart] | None = None) -> tuple[str, str]:
```

### Implementation Steps

**Step 1: Documentation** (Est: 100 LOC)
- `docs/demo/notes.md` — outline 互斥与 part 边界说明
- `docs/architecture/note-generation.md` — 生成流程与边界规则

**Step 2: Tests** (Est: 120 LOC)
- `tests/unit/use_cases/prompts/test_note_prompts.py` — prompt 规则单测
- `tests/unit/use_cases/test_note.py` — use case 传参单测

**Step 3: Implementation** (Est: 90 LOC)
- `src/deeplecture/use_cases/prompts/note.py` — outline 互斥 + 兄弟感知
- `src/deeplecture/use_cases/prompts/registry.py` — 透传 outline
- `src/deeplecture/use_cases/note.py` — 传入 outline 到 part prompt

**Total: ~310 LOC (Medium complexity, Single session)**

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM 仍出现跨 part 重复 | M | M | outline 互斥规则 + 兄弟感知 prompt 强约束 |
| 过度约束导致解释不完整 | M | M | 允许 1–2 句前置，不展开他人内容 |
| doc 与实现漂移 | L | M | 文档先行 + prompt 单测覆盖 |

### Out of Scope (Future Work)

- ✅ Good to have: 基于 `focus_points` 的确定性检索（可回退到全量上下文）与 token 计量
- ❌ Not needed: 依赖 LLM 产出行号/区间的切片方案，可靠性太差

## Related PR

TBD - will be updated when PR is created
