# 笔记

## 生成流程

笔记生成采用 **Outline → Parallel Parts** 两阶段流水线：

1. **Outline 生成**（单次 LLM 调用, temperature=0.2）
   - 输入：完整的字幕/幻灯片上下文
   - 输出：JSON 格式的大纲，每个 Part 包含 `id`, `title`, `summary`, `focus_points`

2. **Part 并行生成**（N 次 LLM 调用, temperature=0.4）
   - 输入：上下文 + 当前 Part 信息 + **完整 outline 摘要**
   - 输出：Markdown 格式的笔记内容

## 去重规则

### Outline 边界约束
- `focus_points` 是每个 Part 的**唯一归属表**
- 每个概念/知识点只能出现在一个 Part 的 `focus_points` 中
- Outline prompt 明确要求 LLM 不允许跨 Part 重复分配概念

### Part 生成约束
- 每个 Part 生成时，会收到完整的 outline 摘要（所有兄弟 Part 的标题和 focus_points）
- Part prompt 明确指示：**只解释自己的 focus_points，不展开其他 Part 的内容**
- 允许 1–2 句必要的前置引用（如"正如前面提到的 X"），但不得完整重复讲解

## 上下文模式

支持四种 `context_mode`：
- `auto`（默认）：使用所有可用的上下文源
- `subtitle`：仅使用字幕
- `slide`：仅使用幻灯片
- `both`：等同于 `auto`
