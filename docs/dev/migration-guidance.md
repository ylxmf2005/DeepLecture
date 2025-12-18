# 迁移指南

## 理念

**代码不处理向后兼容性。** 迁移脚本在启动时自动处理所有数据变更。

当数据结构变更时：
1. 编写迁移脚本
2. 更新代码只使用新格式
3. 删除旧格式处理代码

## 目录结构

```
scripts/migrations/
├── __init__.py                    # 迁移引擎
└── v{major}_{minor}_{patch}/      # 版本文件夹
    ├── __init__.py
    └── {seq}_{description}.py     # id = "v{M}_{m}_{p}_{seq}_{description}"
```

## 运行机制

- **状态追踪**：已完成的迁移 ID 记录在 `data/.migration_state.json`
- **版本控制**：只运行 `<= pyproject.toml 版本` 的迁移
- **调用时机**：在 `app.py` 的 `create_app()` 之前调用

```python
from scripts.migrations import run_migrations
run_migrations()  # 应用启动前调用
```

## 创建迁移

1. 在版本文件夹中创建文件（版本号与 `pyproject.toml` 一致）
2. 使用数字前缀确定执行顺序（001_, 002_, ...）
3. 实现 `Migration` 类

示例：
```python
from pathlib import Path

class Migration:
    id = "v0_1_0_001_rename_config_key"
    description = "将配置中的 foo 重命名为 bar"

    @staticmethod
    def run() -> int:
        # 迁移完全自包含 - 无参数传入
        # 自行确定路径、访问资源
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "conf.yaml"

        if not config_path.exists():
            return 0

        content = config_path.read_text()
        if "foo:" not in content:
            return 0

        new_content = content.replace("foo:", "bar:")
        config_path.write_text(new_content)
        return 1
```

## 规则

| 规则 | 说明 |
|------|------|
| **自包含** | 每个迁移自行处理一切 - 无参数传入 |
| **单向** | 不支持回滚，设计时需谨慎 |
| **顺序执行** | 先按版本排序，再按数字前缀排序 |
| **幂等** | 可安全多次运行（引擎追踪已完成的迁移） |
| **无遗留代码** | 迁移存在后，从主代码库删除所有向后兼容代码 |
| **前缀重置** | 每个新版本文件夹从 001_ 开始 |
