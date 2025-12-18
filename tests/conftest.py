"""
Global pytest configuration and fixtures.

Provides worker-isolated resources for parallel execution (pytest-xdist).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from pytest import FixtureRequest, TempPathFactory

# =============================================================================
# WORKER ISOLATION (pytest-xdist compatible)
# =============================================================================


@pytest.fixture(scope="session")
def worker_id(request: FixtureRequest) -> str:
    """Get xdist worker id or 'master' for single-process runs."""
    if hasattr(request.config, "workerinput"):
        return request.config.workerinput["workerid"]
    return "master"


@pytest.fixture(scope="session")
def worker_tmp_dir(tmp_path_factory: TempPathFactory, worker_id: str) -> Path:
    """
    Session-scoped temporary directory isolated per xdist worker.

    All tests in a worker share this directory for efficiency,
    but each worker gets its own to prevent conflicts.
    """
    return tmp_path_factory.mktemp(f"deeplecture-{worker_id}")


@pytest.fixture(scope="function")
def test_data_dir(worker_tmp_dir: Path, request: FixtureRequest) -> Path:
    """
    Function-scoped data directory for test isolation.

    Creates a unique subdirectory per test function.
    """
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    data_dir = worker_tmp_dir / test_name / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


# =============================================================================
# SETTINGS OVERRIDE
# =============================================================================


@pytest.fixture
def test_settings(test_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    """
    Override settings to use test data directory.

    Monkeypatches get_settings() to return test-safe configuration.
    """
    from deeplecture.config.settings import Settings

    mock_settings = MagicMock(spec=Settings)
    mock_settings.get_data_dir.return_value = test_data_dir
    mock_settings.app.data_dir = str(test_data_dir)
    mock_settings.app.debug = True

    # Task settings
    mock_settings.tasks.enabled = False
    mock_settings.tasks.workers = 1
    mock_settings.tasks.queue_max_size = 10
    mock_settings.tasks.sse_subscriber_queue_size = 10
    mock_settings.tasks.parallelism.default = 2

    # LLM settings (disabled by default)
    mock_settings.llm.models = []
    mock_settings.llm.max_rpm = 100
    mock_settings.llm.get_model_for_task.return_value = None

    # TTS settings (disabled by default)
    mock_settings.tts.models = []
    mock_settings.tts.max_rpm = 100
    mock_settings.tts.get_model_for_task.return_value = None

    # Subtitle settings
    mock_settings.subtitle.engine = "whisper_cpp"
    mock_settings.subtitle.use_mock = True

    monkeypatch.setattr("deeplecture.config.settings.get_settings", lambda: mock_settings)

    yield mock_settings


# =============================================================================
# CONTAINER OVERRIDE
# =============================================================================


@pytest.fixture
def reset_container() -> Iterator[None]:
    """Reset the global container after each test."""
    yield
    from deeplecture.di.container import reset_container as _reset

    _reset()


# =============================================================================
# CONTENT SETUP HELPERS
# =============================================================================


@pytest.fixture
def sample_content_dir(test_data_dir: Path) -> Path:
    """Create sample content directory structure."""
    content_dir = test_data_dir / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    return content_dir


@pytest.fixture
def sample_temp_dir(test_data_dir: Path) -> Path:
    """Create sample temp directory structure."""
    temp_dir = test_data_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


# =============================================================================
# AUTO-USE FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate environment variables for each test."""
    # Prevent accidental use of real API keys
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FISH_AUDIO_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
