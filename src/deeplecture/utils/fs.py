from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def ensure_directory(*path_parts: str) -> str:
    """
    Ensure that the joined path exists as a directory and return it.

    This is intentionally tiny so it can be used from low-level services
    without dragging in application-level context or configuration.
    """
    path = os.path.join(*path_parts)
    os.makedirs(path, exist_ok=True)
    return path


def iter_files_recursive(root: str) -> Iterable[str]:
    """
    Yield absolute file paths under the given root directory.

    Currently unused, but kept small and generic for potential future use
    in storage/services that need a safe directory walk.
    """
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            yield os.path.join(dirpath, filename)


def safe_join(base: str, *paths: str) -> str:
    """
    Join paths and ensure the result stays under the base directory.

    Raises:
        ValueError: if the resolved path escapes the base.
    """
    base_path = Path(base).resolve()
    target = base_path.joinpath(*paths).resolve()

    try:
        target.relative_to(base_path)
    except ValueError:
        raise ValueError("Path traversal detected")

    return str(target)
