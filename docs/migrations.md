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
    └── {description}.py  # id = "vX.Y.Z_{description}"
```

## Creating a Migration

1. Create file in version folder matching `pyproject.toml` version
2. Implement `Migration` class with:
   - `id`: Unique identifier (e.g., `"v0.1.0_json_to_sqlite"`)
   - `description`: Short description
   - `run(data_dir: str) -> int`: Execute migration, return count of affected items

Example:
```python
class Migration:
    id = "v0.2.0_add_new_field"
    description = "Add new_field to all content"

    @staticmethod
    def run(data_dir: str) -> int:
        # Migration is fully self-contained
        # Access database, files, whatever you need
        from deeplecture.storage.database import get_session
        from deeplecture.storage.models import ContentMetadataModel

        count = 0
        with get_session() as session:
            for model in session.query(ContentMetadataModel).all():
                model.new_field = "default_value"
                count += 1
        return count
```

## Rules

- **Self-contained**: Each migration handles its own data access
- **One-way**: No rollback support, design carefully
- **Sequential**: Migrations run in version order
- **Idempotent**: Safe to run multiple times (engine tracks completed migrations)
- **No legacy code**: After migration exists, remove all backward-compatible code from main codebase
