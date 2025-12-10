# Data Migrations

## Philosophy

**Code should NOT handle backward compatibility.** Migration scripts handle all data format changes automatically on startup.

When changing data structures:
1. Write a migration script
2. Update code to use new format only
3. Delete legacy handling code

## Structure

```
scripts/migrations/
├── __init__.py          # Engine
└── v{major}_{minor}_{patch}/
    ├── __init__.py
    └── {seq}_{description}.py  # id = "v{M}_{m}_{p}_{seq}_{description}"
```

## Creating a Migration

1. Create file in version folder matching `pyproject.toml` version
2. Use numeric prefix for execution order (001_, 002_, ...)
3. Implement `Migration` class with:
   - `id`: Unique identifier (e.g., `"v0_1_0_001_json_to_sqlite"`)
   - `description`: Short description
   - `run() -> int`: Execute migration, return count of affected items

Example:
```python
from pathlib import Path

class Migration:
    id = "v0_1_0_001_rename_config_key"
    description = "Rename foo to bar in config"

    @staticmethod
    def run() -> int:
        # Migration is fully self-contained - no parameters
        # Determine paths, access resources as needed
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

## Rules

- **Self-contained**: Each migration handles everything itself - no parameters passed in
- **One-way**: No rollback support, design carefully
- **Sequential**: Migrations run in version order, then by numeric prefix within each version
- **Idempotent**: Safe to run multiple times (engine tracks completed migrations)
- **No legacy code**: After migration exists, remove all backward-compatible code from main codebase
- **Numeric prefix reset**: Each new version folder starts from 001_
