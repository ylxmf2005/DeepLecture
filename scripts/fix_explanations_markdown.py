#!/usr/bin/env python3
"""
One-off fix: normalize LLM-generated Markdown in explanations.json files.

This script scans data/content/*/explanations.json and fixes common Markdown issues
that break renderers (notably whitespace inside **bold** markers).
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path so this can be run from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deeplecture.use_cases.shared.prompt_safety import normalize_llm_markdown  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _iter_explanations_files(content_root: Path) -> list[Path]:
    paths: list[Path] = []
    if not content_root.exists():
        return paths
    for child in content_root.iterdir():
        if not child.is_dir():
            continue
        path = child / "explanations.json"
        if path.is_file():
            paths.append(path)
    return sorted(paths)


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Markdown in explanations.json files (fixes broken **bold** markers)."
    )
    parser.add_argument(
        "--content-root",
        type=Path,
        default=Path("data") / "content",
        help="Content directory containing per-content folders (default: data/content)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes back to disk (default: dry-run).",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a timestamped .bak copy before writing.",
    )
    args = parser.parse_args()

    content_root: Path = args.content_root
    files = _iter_explanations_files(content_root)
    if not files:
        logger.info("No explanations.json files found under %s", content_root)
        return 0

    files_changed = 0
    entries_changed = 0
    for path in files:
        try:
            data = _load_json(path)
        except Exception as e:
            logger.warning("Skip unreadable %s (%s)", path, e)
            continue

        explanations = data.get("explanations")
        if not isinstance(explanations, list):
            continue

        changed_here = 0
        for entry in explanations:
            if not isinstance(entry, dict):
                continue
            old = entry.get("explanation")
            if not isinstance(old, str) or not old:
                continue
            new = normalize_llm_markdown(old)
            if new != old:
                entry["explanation"] = new
                changed_here += 1

        if changed_here == 0:
            continue

        files_changed += 1
        entries_changed += changed_here

        if not args.write:
            logger.info("[dry-run] %s: %d entries would change", path, changed_here)
            continue

        if args.backup:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = path.with_suffix(path.suffix + f".bak.{ts}")
            shutil.copy2(path, backup_path)
            logger.info("Backup written: %s", backup_path)

        try:
            _write_json(path, data)
        except Exception as e:
            logger.error("Failed to write %s (%s)", path, e)
            continue

        logger.info("%s: fixed %d entries", path, changed_here)

    if args.write:
        logger.info("Done. Changed %d files, %d entries.", files_changed, entries_changed)
    else:
        logger.info("Dry-run done. %d files, %d entries would change. Re-run with --write to apply.", files_changed, entries_changed)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

