"""Fixtures for API route tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from flask import Flask
    from flask.testing import FlaskClient


@pytest.fixture
def mock_container() -> MagicMock:
    """Create a mock DI container with all required services."""
    container = MagicMock()

    # Mock use cases
    container.content_usecase = MagicMock()
    container.subtitle_usecase = MagicMock()
    container.note_usecase = MagicMock()
    container.ask_usecase = MagicMock()
    container.task_manager = MagicMock()
    container.voiceover_usecase = MagicMock()
    container.timeline_usecase = MagicMock()

    # Mock storage
    container.metadata_storage = MagicMock()
    container.subtitle_storage = MagicMock()

    # Mock settings
    container.settings = MagicMock()

    return container


@pytest.fixture
def app(mock_container: MagicMock) -> Generator[Flask, None, None]:
    """Create Flask app for testing without worker pool."""
    import deeplecture.di

    # Store original and replace
    original_get_container = deeplecture.di.get_container

    def mock_get_container():
        return mock_container

    deeplecture.di.get_container = mock_get_container

    try:
        # Force re-import of routes to pick up the mock
        import sys

        # Clear cached route modules
        modules_to_reload = [
            name
            for name in sys.modules
            if name.startswith("deeplecture.presentation.api.") and name != "deeplecture.presentation.api"
        ]
        for name in modules_to_reload:
            del sys.modules[name]

        # Import and create app
        from deeplecture.presentation.api.app import create_app

        app = create_app(start_workers=False)
        app.config["TESTING"] = True
        yield app

    finally:
        deeplecture.di.get_container = original_get_container


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create test client."""
    return app.test_client()
