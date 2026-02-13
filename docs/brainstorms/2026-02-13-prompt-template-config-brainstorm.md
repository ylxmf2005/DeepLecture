---
date: 2026-02-13
topic: prompt-template-config
---

# Prompt Templates Configuration (Global Library + Video Selection)

## What We're Building
将当前硬编码在 Python 的 prompt 文本迁移为“文件化模板库”，并允许在前端进行“全局新增模板”。

约束为：
- 模板新增/编辑只在全局维度发生。
- 视频维度不允许创建模板，只允许从全局模板库中选择 `impl_id`。
- 运行时仍按 `func_id -> impl_id` 解析，保持现有任务接口基本不变。

第一期目标是把 prompt 当作配置资产管理（类似 model/task model），同时保留默认模板作为安全回退。

## Why This Approach
我们考虑了三种方式：

1. 保持 Python 硬编码，仅修 UI 文案
2. 全局模板库 + 视频只选择（本次选择）
3. 视频级也可新增模板

选择方式 2 的原因：
- 满足“prompt 是配置”的核心诉求。
- 治理简单，避免视频级模板爆炸和重复。
- 对现有接口改动最小：视频仍只存 `ai.prompts` 映射。
- 可在后续增量支持模板版本、审计、回滚。

## Key Decisions
- 决策 1：模板文件化存储到 `data/config`。
  理由：与现有配置资产一致，便于热更新与备份。

- 决策 2：模板库采用“全局单一事实源”，视频只引用。
  理由：减少配置分叉，便于团队协作与可观测性。

- 决策 3：默认模板从现有 Python prompt 搬迁生成，并标记为 `source=default`。
  理由：保持现有行为兼容，迁移风险低。

- 决策 4：新增模板必须经过占位符校验。
  理由：防止运行时缺变量导致任务失败。

- 决策 5：运行时保留 fallback 机制。
  理由：当自定义模板缺失/损坏时，自动回退默认模板，保证服务可用。

## Proposed Data Model (Draft)
模板库文件（示例）：`data/config/prompt_templates.json`

每个模板条目建议包含：
- `func_id`: 例如 `ask_video`
- `impl_id`: 例如 `concise_v1`
- `name`: UI 展示名
- `description`: 可选描述
- `system_template`: 字符串模板
- `user_template`: 字符串模板
- `required_placeholders`: 必填占位符列表
- `source`: `default | custom`
- `created_at`, `updated_at`: 审计字段

## Placeholder Validation Rules (Draft)
新增/更新模板时校验：
- `impl_id` 在同一 `func_id` 下唯一。
- 至少包含该 `func_id` 的必填占位符集合。
- 禁止未知占位符（或仅告警，作为可配置策略）。
- 模板长度与字段非空校验。

占位符规则来源：
- 每个 `func_id` 对应一个 schema（后端维护），定义 allowed/required placeholders。

## API & UI Direction (Draft)
后端：
- 新增模板管理 API（全局）：列表、创建、更新、删除。
- `/api/config` 的 `prompts` 返回改为来源于模板库（附带默认 impl）。

前端：
- Prompt Tab 新增“创建模板”入口（仅 Global scope 可见）。
- Video scope 仅展示选择器，不提供创建/编辑入口。
- 创建表单按 `func_id` 动态提示占位符。

## Migration Strategy
- 步骤 1：导出现有 Python 默认模板到 `data/config/prompt_templates.json`。
- 步骤 2：注册器改为“文件模板优先”，Python 硬编码作为兜底。
- 步骤 3：验证通过后，逐步下线硬编码文本。

## Non-Goals (Phase 1)
- 不做视频级模板创建。
- 不做 provider 插件系统的动态注册。
- 不做跨环境模板同步平台（先本地文件 + Git 管理）。

## Open Questions
- 删除“被引用模板”时的策略：禁止删除、软删除、或自动重映射？
- 占位符策略是“严格拒绝未知”还是“允许未知并警告”？
- 是否需要模板版本字段（`version`）在第一期就引入？

## Next Steps
1. 进入 `/prompts:workflows-plan`，输出分阶段实施计划（后端存储、迁移、API、前端表单、测试）。
2. 先做最小可用版本：只支持新增与选择，不做编辑删除。
3. 完成后补充一次端到端回归：默认模板回退、视频覆盖选择、任务运行一致性。
