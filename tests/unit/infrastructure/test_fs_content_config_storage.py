"""Unit tests for FsContentConfigStorage."""

import json

import pytest

from deeplecture.domain.entities.config import ContentConfig
from deeplecture.infrastructure.repositories.fs_content_config_storage import FsContentConfigStorage
from deeplecture.infrastructure.repositories.path_resolver import PathResolver


class TestFsContentConfigStorage:
    """Tests for filesystem-backed content config storage."""

    @pytest.fixture
    def storage(self, test_data_dir) -> FsContentConfigStorage:
        """Create storage with test data directory."""
        resolver = PathResolver(
            content_dir=test_data_dir / "content",
            temp_dir=test_data_dir / "temp",
            upload_dir=test_data_dir / "uploads",
        )
        return FsContentConfigStorage(resolver)

    @pytest.mark.unit
    def test_load_nonexistent_returns_none(self, storage: FsContentConfigStorage) -> None:
        """load should return None when config does not exist."""
        result = storage.load("nonexistent-content-id")
        assert result is None

    @pytest.mark.unit
    def test_save_and_load_roundtrip(self, storage: FsContentConfigStorage) -> None:
        """save + load should roundtrip correctly."""
        config = ContentConfig(
            source_language="ja",
            target_language="en",
            llm_model="claude-3-5-sonnet",
        )
        storage.save("test-content-id", config)

        loaded = storage.load("test-content-id")
        assert loaded is not None
        assert loaded.source_language == "ja"
        assert loaded.target_language == "en"
        assert loaded.llm_model == "claude-3-5-sonnet"
        assert loaded.tts_model is None

    @pytest.mark.unit
    def test_save_overwrites(self, storage: FsContentConfigStorage) -> None:
        """save should fully replace existing config."""
        storage.save("test-id", ContentConfig(source_language="ja"))
        storage.save("test-id", ContentConfig(llm_model="gpt-4o"))

        loaded = storage.load("test-id")
        assert loaded is not None
        assert loaded.source_language is None  # overwritten (PUT semantics)
        assert loaded.llm_model == "gpt-4o"

    @pytest.mark.unit
    def test_delete_removes_file(self, storage: FsContentConfigStorage) -> None:
        """delete should remove the config file."""
        storage.save("test-id", ContentConfig(source_language="en"))
        assert storage.load("test-id") is not None

        storage.delete("test-id")
        assert storage.load("test-id") is None

    @pytest.mark.unit
    def test_delete_nonexistent_no_error(self, storage: FsContentConfigStorage) -> None:
        """delete should not raise on nonexistent config."""
        storage.delete("does-not-exist")  # Should not raise

    @pytest.mark.unit
    def test_save_empty_config(self, storage: FsContentConfigStorage) -> None:
        """save with empty config should create a file with empty JSON object."""
        storage.save("test-id", ContentConfig())

        loaded = storage.load("test-id")
        assert loaded is not None
        assert loaded.to_sparse_dict() == {}

    @pytest.mark.unit
    def test_save_with_prompts(self, storage: FsContentConfigStorage) -> None:
        """save should persist prompts dict correctly."""
        config = ContentConfig(prompts={"timeline": "concise_v2", "quiz": "detailed_v1"})
        storage.save("test-id", config)

        loaded = storage.load("test-id")
        assert loaded is not None
        assert loaded.prompts == {"timeline": "concise_v2", "quiz": "detailed_v1"}

    @pytest.mark.unit
    def test_load_corrupt_json_returns_none(self, storage: FsContentConfigStorage, test_data_dir) -> None:
        """load should return None on corrupt JSON."""
        config_dir = test_data_dir / "content" / "corrupt-id" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text("not valid json{{{", encoding="utf-8")

        result = storage.load("corrupt-id")
        assert result is None

    @pytest.mark.unit
    def test_load_ignores_unknown_json_keys(self, storage: FsContentConfigStorage, test_data_dir) -> None:
        """load should ignore unknown keys in the JSON file."""
        config_dir = test_data_dir / "content" / "future-id" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(
            json.dumps({"source_language": "en", "future_field": "ignored"}),
            encoding="utf-8",
        )

        result = storage.load("future-id")
        assert result is not None
        assert result.source_language == "en"
        assert result.to_sparse_dict() == {"source_language": "en"}
