"""File system implementation of explanation storage."""

from __future__ import annotations

import json
from pathlib import Path

from deeplecture.infrastructure.repositories.path_resolver import safe_join, validate_segment


class FsExplanationStorage:
    """
    File system based explanation storage.

    Stores explanations as JSON files in content directories.
    """

    def __init__(self, content_dir: Path | str) -> None:
        self._content_dir = Path(content_dir).expanduser().resolve(strict=False)

    def _get_path(self, content_id: str) -> Path:
        validate_segment(content_id, "content_id")
        return safe_join(self._content_dir, content_id, "explanations.json")

    def load(self, content_id: str) -> list[dict]:
        """Load explanation history from file."""
        path = self._get_path(content_id)

        if not path.is_file():
            return []

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("explanations", [])
        except (OSError, json.JSONDecodeError):
            return []

    def save(self, content_id: str, explanation: dict) -> None:
        """Append an explanation to history file."""
        path = self._get_path(content_id)
        history = self.load(content_id)

        history.append(explanation)
        history = history[-100:]  # Keep only last 100

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"explanations": history}, f, ensure_ascii=False, indent=2)

    def delete(self, content_id: str, explanation_id: str) -> bool:
        """Delete an explanation from history by ID."""
        path = self._get_path(content_id)
        history = self.load(content_id)

        original_len = len(history)
        history = [e for e in history if e.get("id") != explanation_id]

        if len(history) == original_len:
            return False

        with open(path, "w", encoding="utf-8") as f:
            json.dump({"explanations": history}, f, ensure_ascii=False, indent=2)

        return True

    def update(self, content_id: str, explanation_id: str, updates: dict) -> bool:
        """Update an existing explanation entry by ID."""
        path = self._get_path(content_id)
        history = self.load(content_id)

        updated = False
        for entry in history:
            if entry.get("id") == explanation_id:
                entry.update(updates)
                updated = True
                break

        if not updated:
            return False

        with open(path, "w", encoding="utf-8") as f:
            json.dump({"explanations": history}, f, ensure_ascii=False, indent=2)

        return True
