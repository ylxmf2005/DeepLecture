"""Unit tests for FsPromptTemplateStorage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from deeplecture.infrastructure.repositories.fs_prompt_template_storage import FsPromptTemplateStorage
from deeplecture.use_cases.prompts.template_definitions import PromptTemplateDefinition

if TYPE_CHECKING:
    from pathlib import Path


def _make_storage(tmp_path: Path) -> FsPromptTemplateStorage:
    return FsPromptTemplateStorage(tmp_path)


class TestFsPromptTemplateStorage:
    @pytest.mark.unit
    def test_list_templates_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        storage = _make_storage(tmp_path)

        assert storage.list_templates() == []

    @pytest.mark.unit
    def test_upsert_and_get_template(self, tmp_path: Path) -> None:
        storage = _make_storage(tmp_path)
        template = PromptTemplateDefinition(
            func_id="ask_video",
            impl_id="concise_v1",
            name="Concise",
            description=None,
            system_template="System {language}",
            user_template="User {question}",
        )

        storage.upsert_template(template)

        loaded = storage.get_template("ask_video", "concise_v1")
        assert loaded is not None
        assert loaded.impl_id == "concise_v1"
        assert loaded.name == "Concise"

    @pytest.mark.unit
    def test_upsert_replaces_existing_template(self, tmp_path: Path) -> None:
        storage = _make_storage(tmp_path)
        first = PromptTemplateDefinition(
            func_id="ask_video",
            impl_id="concise_v1",
            name="First",
            description=None,
            system_template="System {language}",
            user_template="User {question}",
        )
        second = PromptTemplateDefinition(
            func_id="ask_video",
            impl_id="concise_v1",
            name="Second",
            description="updated",
            system_template="System {language}",
            user_template="User {question}",
        )

        storage.upsert_template(first)
        storage.upsert_template(second)

        all_templates = storage.list_templates()
        assert len(all_templates) == 1
        assert all_templates[0].name == "Second"
        assert all_templates[0].description == "updated"
