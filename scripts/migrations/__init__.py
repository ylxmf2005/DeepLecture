"""
Migration engine for DeepLecture.

Design:
- Version-based: Migrations organized in folders by app version (v0_1_0/, v0_2_0/, ...)
- Sequential: Only migrations for versions <= current app version are executed
- Tracked: Each migration has a unique `id`, executed ids are stored in .migration_state.json
- Self-contained: Each migration is fully autonomous - no parameters, no constraints

Folder structure:
    scripts/migrations/
    ├── __init__.py
    ├── v0_1_0/
    │   ├── __init__.py
    │   ├── 001_json_to_sqlite.py
    │   ├── 002_tts_providers_to_models.py
    │   └── 003_remove_reencode_flags.py
    └── v0_2_0/
        └── 001_some_migration.py

Usage:
    from scripts.migrations import run_migrations
    run_migrations()  # Called in app.py before create_app
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

# tomllib is Python 3.11+, fallback to tomli for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logger = logging.getLogger(__name__)

# Project root for state file
PROJECT_ROOT = Path(__file__).parent.parent.parent
MIGRATION_STATE_FILE = PROJECT_ROOT / "data" / ".migration_state.json"
VERSION_PATTERN = re.compile(r"^v(\d+)_(\d+)_(\d+)$")


class Migration(Protocol):
    """
    Protocol for migration scripts.

    Each migration must have:
    - id: Unique identifier (e.g., "v0_1_0_001_json_to_sqlite")
    - description: Short description of what the migration does
    - run() -> int: Execute migration, return count of affected items

    Migrations are fully self-contained - they can do anything:
    database migrations, config file changes, file system operations, etc.
    """

    id: str
    description: str

    @staticmethod
    def run() -> int:
        """
        Execute the migration.

        Returns:
            Count of affected items (for logging purposes)
        """
        ...


def _parse_version(version_str: str) -> tuple[int, int, int] | None:
    """Parse version string like 'v0.1.0', '0.1.0', or 'v0_1_0' into tuple."""
    v = version_str.lstrip("v")
    parts = v.replace("_", ".").split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _get_app_version() -> tuple[int, int, int]:
    """Get current app version from pyproject.toml."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"

    if not pyproject_path.exists():
        logger.warning("pyproject.toml not found, using version 0.0.0")
        return (0, 0, 0)

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        version_str = data.get("project", {}).get("version", "0.0.0")
        parsed = _parse_version(version_str)
        return parsed if parsed else (0, 0, 0)
    except Exception as e:
        logger.warning("Failed to read version from pyproject.toml: %s", e)
        return (0, 0, 0)


def _load_migration_state() -> dict[str, Any]:
    """Load migration state from data/.migration_state.json"""
    if not MIGRATION_STATE_FILE.exists():
        return {"completed": [], "last_run": None}

    try:
        with open(MIGRATION_STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load migration state: %s", e)
        return {"completed": [], "last_run": None}


def _save_migration_state(state: dict[str, Any]) -> None:
    """Save migration state to data/.migration_state.json atomically."""
    import shutil
    import tempfile

    # Ensure data directory exists
    MIGRATION_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    state["last_run"] = datetime.now(timezone.utc).isoformat()

    try:
        # Write to temp file first, then atomic rename
        fd, temp_path = tempfile.mkstemp(
            dir=MIGRATION_STATE_FILE.parent, prefix=".migration_state_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            shutil.move(temp_path, MIGRATION_STATE_FILE)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.error("Failed to save migration state: %s", e)
        raise


def _discover_version_folders() -> list[tuple[tuple[int, int, int], Path]]:
    """Discover all version folders (vX_Y_Z/) and return sorted by version."""
    package_dir = Path(__file__).parent
    version_folders: list[tuple[tuple[int, int, int], Path]] = []

    for item in package_dir.iterdir():
        if not item.is_dir():
            continue
        if not VERSION_PATTERN.match(item.name):
            continue

        parsed = _parse_version(item.name)
        if parsed:
            version_folders.append((parsed, item))

    version_folders.sort(key=lambda x: x[0])
    return version_folders


def _discover_migrations_in_folder(folder: Path) -> list[Migration]:
    """Discover all migration classes in a version folder."""
    migrations: list[Migration] = []
    version_name = folder.name

    py_files = sorted(f for f in folder.glob("*.py") if f.name != "__init__.py")

    for py_file in py_files:
        module_name = py_file.stem
        try:
            module = importlib.import_module(f"scripts.migrations.{version_name}.{module_name}")
            if hasattr(module, "Migration"):
                migrations.append(module.Migration)
        except Exception as e:
            logger.error("Failed to load migration %s/%s: %s", version_name, module_name, e)

    return migrations


def run_migrations() -> dict[str, int]:
    """
    Run all pending migrations for versions <= current app version.

    Returns:
        Dict mapping migration_id -> count of affected items
    """
    state = _load_migration_state()
    completed = set(state.get("completed", []))

    app_version = _get_app_version()
    logger.debug("App version: %s", ".".join(map(str, app_version)))

    version_folders = _discover_version_folders()
    applicable_folders = [(v, p) for v, p in version_folders if v <= app_version]

    if not applicable_folders:
        logger.debug("No applicable migration folders")
        return {}

    results: dict[str, int] = {}

    for _, folder in applicable_folders:
        migrations = _discover_migrations_in_folder(folder)
        pending = [m for m in migrations if m.id not in completed]

        for migration in pending:
            logger.info("Running migration: %s - %s", migration.id, migration.description)

            try:
                count = migration.run()
                results[migration.id] = count

                completed.add(migration.id)
                state["completed"] = sorted(completed)
                _save_migration_state(state)

                if count > 0:
                    logger.info("Migration %s: completed (%d items)", migration.id, count)
                else:
                    logger.info("Migration %s: completed (no items needed migration)", migration.id)

            except Exception as e:
                logger.error("Migration %s failed: %s", migration.id, e)
                raise

    return results
