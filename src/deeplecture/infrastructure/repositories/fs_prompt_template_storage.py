"""Filesystem-backed prompt template library storage."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path

from deeplecture.use_cases.prompts.template_definitions import PromptTemplateDefinition

logger = logging.getLogger(__name__)


class FsPromptTemplateStorage:
    """Store global prompt templates at data/config/prompt_templates.json."""

    REL_PATH = ("config", "prompt_templates.json")

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir).expanduser().resolve(strict=False)

    def _path(self) -> Path:
        return self._data_dir.joinpath(*self.REL_PATH)

    def list_templates(self) -> list[PromptTemplateDefinition]:
        """List active custom templates."""
        payload = self._load_payload()
        raw_templates = payload.get("templates")
        if not isinstance(raw_templates, list):
            return []

        result: list[PromptTemplateDefinition] = []
        for item in raw_templates:
            if not isinstance(item, dict):
                continue
            template = PromptTemplateDefinition.from_dict(item)
            if template and template.active:
                result.append(template)
        return result

    def get_template(self, func_id: str, impl_id: str) -> PromptTemplateDefinition | None:
        """Get template by (func_id, impl_id)."""
        for template in self.list_templates():
            if template.func_id == func_id and template.impl_id == impl_id:
                return template
        return None

    def delete_template(self, func_id: str, impl_id: str) -> bool:
        """Delete a template by (func_id, impl_id). Returns True if found and removed."""
        payload = self._load_payload()
        raw_templates = payload.get("templates")
        if not isinstance(raw_templates, list):
            return False

        next_templates: list[dict[str, object]] = []
        found = False
        for item in raw_templates:
            if not isinstance(item, dict):
                continue
            existing = PromptTemplateDefinition.from_dict(item)
            if existing and existing.func_id == func_id and existing.impl_id == impl_id:
                found = True
            else:
                next_templates.append(item)

        if not found:
            return False

        self._write_payload({"version": 1, "templates": next_templates})
        return True

    def upsert_template(self, template: PromptTemplateDefinition) -> PromptTemplateDefinition:
        """Insert or replace a template."""
        payload = self._load_payload()
        raw_templates = payload.get("templates")
        if not isinstance(raw_templates, list):
            raw_templates = []

        updated = False
        next_templates: list[dict[str, object]] = []
        for item in raw_templates:
            if not isinstance(item, dict):
                continue
            existing = PromptTemplateDefinition.from_dict(item)
            if existing and existing.func_id == template.func_id and existing.impl_id == template.impl_id:
                next_templates.append(template.to_dict())
                updated = True
            else:
                next_templates.append(item)

        if not updated:
            next_templates.append(template.to_dict())

        payload_out = {
            "version": 1,
            "templates": next_templates,
        }
        self._write_payload(payload_out)
        return template

    def _load_payload(self) -> dict[str, object]:
        path = self._path()
        if not path.exists():
            return {"version": 1, "templates": []}

        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read prompt template library %s: %s", path, exc)
            return {"version": 1, "templates": []}

        if isinstance(data, dict):
            return data
        return {"version": 1, "templates": []}

    def _write_payload(self, payload: dict[str, object]) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                delete=False,
            ) as f:
                tmp_path = f.name
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
        finally:
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)
