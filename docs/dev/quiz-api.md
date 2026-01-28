# Quiz API

Quiz API 用于从课程内容生成 MCQ（选择题）小测验。

## 概述

Quiz 功能采用两阶段 LLM 管道：
1. **知识抽取**：复用 Cheatsheet 的知识抽取逻辑，生成结构化 `KnowledgeItem`
2. **题目生成**：从知识点生成带干扰项的选择题

## API 端点

### POST /api/quiz/{content_id}/generate

异步生成 Quiz。

**请求体：**
```json
{
  "language": "zh-CN",           // 必填：输出语言
  "question_count": 5,           // 可选：生成题目数量，默认 5
  "context_mode": "subtitle",    // 可选：上下文来源 (auto|subtitle|slide|both)
  "user_instruction": "",        // 可选：额外指令
  "min_criticality": "medium",   // 可选：最低重要性 (high|medium|low)
  "subject_type": "auto"         // 可选：学科类型 (stem|humanities|auto)
}
```

**响应：**
```json
{
  "content_id": "abc123",
  "task_id": "task-uuid",
  "status": "pending",
  "message": "Quiz generation started"
}
```

### GET /api/quiz/{content_id}

获取已生成的 Quiz。

**查询参数：**
- `language`: 可选，筛选特定语言版本

**响应：**
```json
{
  "content_id": "abc123",
  "language": "zh-CN",
  "items": [
    {
      "stem": "根据公式 E=mc²，质量与能量的关系是？",
      "options": [
        "A. 能量与质量成正比",
        "B. 能量与质量成反比",
        "C. 能量与质量无关",
        "D. 能量与质量的平方成正比"
      ],
      "answer_index": 0,
      "explanation": "正确答案是 A。E=mc² 表明能量与质量成正比，比例常数为光速的平方。B 错误是因为混淆了正比与反比关系；C 错误忽略了公式本身；D 错误将质量的关系错误地表述为平方关系。",
      "source_category": "formula",
      "source_tags": ["physics", "relativity"]
    }
  ],
  "count": 5,
  "updated_at": "2025-01-28T10:30:00Z"
}
```

## 数据结构

### QuizItem

| 字段 | 类型 | 说明 |
|------|------|------|
| `stem` | string | 题目文本 |
| `options` | string[] | 4 个选项 (必须正好 4 个) |
| `answer_index` | int | 正确答案索引 (0-3) |
| `explanation` | string | 解析（含每个干扰项错误原因）|
| `source_category` | string | 知识点类别 |
| `source_tags` | string[] | 知识点标签 |

### 干扰项生成策略

每个干扰项针对不同的误解类型：

| 误解类型 | 说明 | 示例 |
|---------|------|------|
| 计算错误 | 符号、运算符、边界值错误 | 正负号混淆 |
| 概念混淆 | 相似但不同的术语 | 因果颠倒 |
| 部分理解 | 缺少关键限定条件 | 必要非充分条件 |
| 过度泛化 | 超出规则适用范围 | 特例当通则 |

## 错误处理

| 状态码 | 说明 |
|--------|------|
| 400 | 缺少必填参数 (language) |
| 404 | 内容不存在或无上下文 |
| 500 | LLM 生成失败 |

## 校验规则

生成的每道题目必须通过以下校验：
1. `options` 必须恰好包含 4 个选项
2. `answer_index` 必须在 0-3 范围内
3. 4 个选项不能重复
4. 必填字段不能为空

未通过校验的题目会被自动过滤。
