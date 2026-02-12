"""Unit tests for CheatsheetUseCase."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from deeplecture.domain import Segment
from deeplecture.use_cases.cheatsheet import CheatsheetUseCase
from deeplecture.use_cases.dto.cheatsheet import GenerateCheatsheetRequest
from deeplecture.use_cases.interfaces.prompt_registry import PromptSpec


@pytest.fixture
def mock_cheatsheet_storage() -> MagicMock:
    """Create mock cheatsheet storage."""
    storage = MagicMock()
    storage.load.return_value = None
    storage.save.return_value = datetime.now(timezone.utc)
    return storage


@pytest.fixture
def mock_subtitle_storage() -> MagicMock:
    """Create mock subtitle storage."""
    storage = MagicMock()
    segments = [
        Segment(start=0.0, end=1.0, text="Hello world."),
        Segment(start=1.0, end=2.0, text="Second line."),
    ]

    def load_side_effect(content_id: str, language: str) -> list[Segment] | None:
        if content_id == "test-content-id" and language == "en_enhanced":
            return segments
        return None

    storage.load.side_effect = load_side_effect
    storage.list_languages.return_value = ["en_enhanced", "en"]
    return storage


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create mock LLM instance."""
    llm = MagicMock()

    extraction_response = json.dumps(
        [
            {
                "category": "definition",
                "content": "Test definition",
                "criticality": "high",
                "tags": ["t1"],
            }
        ]
    )
    render_response = "# Cheatsheet\n\n- Item"
    llm.complete.side_effect = [extraction_response, render_response]
    return llm


@pytest.fixture
def mock_llm_provider(mock_llm: MagicMock) -> MagicMock:
    """Create mock LLM provider."""
    provider = MagicMock()
    provider.get.return_value = mock_llm
    return provider


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    """Create mock path resolver."""
    return MagicMock()


@pytest.fixture
def mock_prompt_registry() -> MagicMock:
    """Create mock prompt registry."""
    registry = MagicMock()
    builder = MagicMock()
    builder.build.return_value = PromptSpec(
        user_prompt="test user prompt",
        system_prompt="test system prompt",
    )
    registry.get.return_value = builder
    return registry


@pytest.fixture
def usecase(
    mock_cheatsheet_storage: MagicMock,
    mock_subtitle_storage: MagicMock,
    mock_path_resolver: MagicMock,
    mock_llm_provider: MagicMock,
    mock_prompt_registry: MagicMock,
) -> CheatsheetUseCase:
    """Create CheatsheetUseCase with mocked dependencies."""
    return CheatsheetUseCase(
        cheatsheet_storage=mock_cheatsheet_storage,
        subtitle_storage=mock_subtitle_storage,
        path_resolver=mock_path_resolver,
        llm_provider=mock_llm_provider,
        prompt_registry=mock_prompt_registry,
    )


class TestCheatsheetUseCaseGenerate:
    """Tests for CheatsheetUseCase.generate()."""

    @pytest.mark.unit
    def test_generate_saves_cheatsheet(
        self,
        usecase: CheatsheetUseCase,
        mock_cheatsheet_storage: MagicMock,
        mock_subtitle_storage: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        request = GenerateCheatsheetRequest(
            content_id="test-content-id",
            language="en",
            target_pages=2,
        )

        result = usecase.generate(request)

        assert result.content_id == "test-content-id"
        assert result.used_sources == ["subtitle"]
        assert result.stats.total_items == 1

        mock_llm_provider.get.assert_called_once()
        mock_subtitle_storage.load.assert_called_once_with("test-content-id", "en_enhanced")
        mock_cheatsheet_storage.save.assert_called_once()
