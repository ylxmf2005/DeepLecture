# Git Message Tags

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

## Tags

| Tag | 用途 | 示例 |
|-----|------|------|
| `feat` | 新功能或重大增强 | `feat: add subtitle global search` |
| `fix` | 缺陷修复 | `fix: resolve TTS timeout issue` |
| `docs` | 文档更新 | `docs: update API reference` |
| `refactor` | 重构，不引入新功能 | `refactor: simplify storage layer` |
| `test` | 新增或更新测试 | `test: add unit tests for timeline` |
| `chore` | 构建、配置或依赖 | `chore: update dependencies` |
| `ci` | CI/CD 相关 | `ci: add PR review workflow` |
| `perf` | 性能优化 | `perf: optimize video processing` |
| `style` | 代码格式（不影响功能） | `style: format with ruff` |

## Scope (可选)

可以在 tag 后添加 scope 来指定模块：

- `feat(frontend)`: 前端相关
- `feat(voiceover)`: 语音合成相关
- `feat(subtitle)`: 字幕相关
- `feat(timeline)`: 时间线相关
- `feat(cheatsheet)`: 知识速查相关
- `feat(quiz)`: 测验相关
- `fix(slide-lecture)`: 幻灯片讲解相关
