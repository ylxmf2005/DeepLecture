"""Integration tests for filesystem-based repositories."""

from pathlib import Path

import pytest

from deeplecture.infrastructure.repositories import PathResolver


class TestPathResolver:
    """Integration tests for PathResolver."""

    @pytest.fixture
    def path_resolver(self, test_data_dir: Path) -> PathResolver:
        """Create PathResolver with test directories."""
        return PathResolver(
            content_dir=test_data_dir / "content",
            temp_dir=test_data_dir / "temp",
            upload_dir=test_data_dir / "uploads",
        )

    @pytest.mark.integration
    def test_content_dir_creation(self, path_resolver: PathResolver) -> None:
        """ensure_content_root should create content directory."""
        # Note: get_content_dir returns path but doesn't create it
        # Use ensure_content_root to actually create the directory
        content_dir_str = path_resolver.ensure_content_root("test-123")
        content_dir = Path(content_dir_str)

        assert content_dir.exists()
        assert content_dir.is_dir()

    @pytest.mark.integration
    def test_temp_dir_creation(self, path_resolver: PathResolver) -> None:
        """ensure_temp_dir should create temp directory."""
        temp_dir_str = path_resolver.ensure_temp_dir("test-task")
        temp_dir = Path(temp_dir_str)

        assert temp_dir.exists()
        assert temp_dir.is_dir()

    @pytest.mark.integration
    def test_path_resolution_isolation(self, path_resolver: PathResolver, test_data_dir: Path) -> None:
        """Paths should be isolated to test data directory."""
        content_dir_str = path_resolver.get_content_dir("test-123")

        assert content_dir_str.startswith(str(test_data_dir))

    @pytest.mark.integration
    def test_multiple_content_dirs(self, path_resolver: PathResolver) -> None:
        """Multiple content directories should be independent."""
        dir1_str = path_resolver.ensure_content_root("content-1")
        dir2_str = path_resolver.ensure_content_root("content-2")

        dir1 = Path(dir1_str)
        dir2 = Path(dir2_str)

        assert dir1 != dir2
        assert dir1.exists()
        assert dir2.exists()

    @pytest.mark.integration
    def test_path_traversal_protection(self, path_resolver: PathResolver) -> None:
        """PathResolver should reject path traversal attempts."""
        with pytest.raises(ValueError):
            path_resolver.get_content_dir("../evil")

    @pytest.mark.integration
    def test_namespace_directory_creation(self, path_resolver: PathResolver) -> None:
        """ensure_content_dir should create namespace subdirectory."""
        subtitle_dir_str = path_resolver.ensure_content_dir("test-123", "subtitle")
        subtitle_dir = Path(subtitle_dir_str)

        assert subtitle_dir.exists()
        assert subtitle_dir.is_dir()
        assert "test-123" in str(subtitle_dir)
        assert "subtitle" in str(subtitle_dir)
