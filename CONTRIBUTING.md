# 贡献指南

感谢你对 DeepLecture 的关注！本文档说明如何参与贡献，帮助你提交高质量的 Pull Request。

## 目录

- [贡献指南](#贡献指南)
  - [目录](#目录)
  - [1. 介绍](#1-介绍)
  - [2. 行为准则](#2-行为准则)
  - [3. 开发环境](#3-开发环境)
  - [4. 如何贡献](#4-如何贡献)
  - [5. 分支命名](#5-分支命名)
  - [6. 提交格式](#6-提交格式)
  - [7. 代码风格](#7-代码风格)
  - [8. 测试](#8-测试)
  - [9. PR 流程](#9-pr-流程)
  - [10. 问题反馈](#10-问题反馈)

## 1. 介绍

DeepLecture 是一个 AI 原生的视频学习平台，提供双语字幕、截图解释、智能时间线等功能。技术栈为 Flask (Python) + Next.js (TypeScript)。

## 2. 行为准则

- 遵循友好、尊重和包容的沟通方式，参考 [Contributor Covenant 2.1](https://www.contributor-covenant.org/) 精神。
- 社区渠道：[GitHub Issues](https://github.com/ylxmf2005/DeepLecture/issues) / [Discussions](https://github.com/ylxmf2005/DeepLecture/discussions)

## 3. 开发环境

按 [README - 快速开始](README.md#快速开始) 完成基础环境搭建后，安装开发依赖：

```bash
uv sync --extra dev  # 包含 ruff, pytest
```

## 4. 如何贡献

1. 在开始前同步最新 `master`：
   ```bash
   git checkout master
   git pull origin master
   ```
2. 根据需求创建功能或修复分支：
   ```bash
   git checkout -b feature/subtitle-search
   ```
3. 开发过程中保持变更粒度小，提交前运行必要的检查（见 [测试](#8-测试)）。
4. 提交并推送：
   ```bash
   git add .
   git commit -m "feat: add subtitle search"
   git push origin feature/subtitle-search
   ```
5. 在 GitHub 上创建 PR，详细填写描述、截图与验证步骤。

## 5. 分支命名

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能或较大改动 | `feature/subtitle-search` |
| `fix/` | 缺陷修复 | `fix/tts-timeout` |
| `docs/` | 文档更新 | `docs/api-reference` |
| `refactor/` | 重构，不引入新功能 | `refactor/storage-layer` |
| `chore/` | 依赖更新、脚本等 | `chore/update-deps` |

## 6. 提交格式

遵循 [Conventional Commits](https://www.conventionalcommits.org/)，使用英文动词简述改动。

| 类型 | 用途 |
|------|------|
| `feat` | 新功能或重大增强 |
| `fix` | 缺陷修复 |
| `docs` | 文档更新 |
| `refactor` | 重构，不引入新功能 |
| `test` | 新增或更新测试 |
| `chore` | 构建、配置或依赖 |

**示例**：`feat: add subtitle global search`

## 7. 代码风格

**后端 (Python)**：
- 遵循 [Ruff](https://docs.astral.sh/ruff/) 默认配置
- 使用类型注解

**前端 (TypeScript/React)**：
- 遵循项目 ESLint 配置
- 函数式组件 + Hooks
- Tailwind CSS 样式
- 新增文件前参考 `frontend/` 下相同模块的实现，保持命名一致

## 8. 测试

在每次提交前务必运行：

```bash
# 后端
uv run ruff check src/ && uv run ruff format --check src/ && uv run pytest

# 前端
cd frontend && npm run check
```

## 9. PR 流程

1. 按 PR 模板填写变更摘要、测试方法等信息。
2. 确保所有 CI 检查通过，与 `master` 无冲突。
3. 合并策略：Squash and merge。

## 10. 问题反馈

在 [GitHub Issues](https://github.com/ylxmf2005/DeepLecture/issues) 中按模板提交 Bug 报告或功能建议，提交前请搜索是否已有类似讨论。

---

感谢你的贡献！
