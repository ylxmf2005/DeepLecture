"""Integration tests for FsFileStorage."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from deeplecture.infrastructure.repositories.fs_file_storage import FsFileStorage


class TestFsFileStorage:
    """Integration tests for FsFileStorage."""

    @pytest.fixture
    def storage(self, test_data_dir: Path) -> FsFileStorage:
        """Create FsFileStorage with test directory as allowed root."""
        return FsFileStorage(allowed_roots=frozenset([test_data_dir]))

    @pytest.fixture
    def unrestricted_storage(self) -> FsFileStorage:
        """Create FsFileStorage without root restrictions (dev mode)."""
        return FsFileStorage(allowed_roots=None)

    @pytest.mark.integration
    def test_save_file_from_bytes(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """save_file() should save bytes to file."""
        dest_path = str(test_data_dir / "test.bin")
        content = b"test binary content"

        storage.save_file(content, dest_path)

        assert Path(dest_path).exists()
        assert Path(dest_path).read_bytes() == content

    @pytest.mark.integration
    def test_save_file_from_file_object(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """save_file() should save file-like object."""
        dest_path = str(test_data_dir / "uploaded.bin")
        content = b"uploaded content"
        file_obj = BytesIO(content)

        storage.save_file(file_obj, dest_path)

        assert Path(dest_path).exists()
        assert Path(dest_path).read_bytes() == content

    @pytest.mark.integration
    def test_read_write_text(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """write_text() and read_text() should handle text files."""
        file_path = str(test_data_dir / "test.txt")
        content = "Hello, 世界!"

        storage.write_text(file_path, content)
        read_content = storage.read_text(file_path)

        assert read_content == content

    @pytest.mark.integration
    def test_read_write_bytes(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """write_bytes() and read_bytes() should handle binary files."""
        file_path = str(test_data_dir / "test.bin")
        content = b"\x00\x01\x02\xff"

        storage.write_bytes(file_path, content)
        read_content = storage.read_bytes(file_path)

        assert read_content == content

    @pytest.mark.integration
    def test_file_exists(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """file_exists() should correctly detect file existence."""
        file_path = str(test_data_dir / "exists.txt")

        assert storage.file_exists(file_path) is False

        storage.write_text(file_path, "content")

        assert storage.file_exists(file_path) is True

    @pytest.mark.integration
    def test_remove_file(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """remove_file() should delete file."""
        file_path = str(test_data_dir / "to_delete.txt")
        storage.write_text(file_path, "content")

        storage.remove_file(file_path)

        assert storage.file_exists(file_path) is False

    @pytest.mark.integration
    def test_makedirs(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """makedirs() should create nested directories."""
        dir_path = str(test_data_dir / "a" / "b" / "c")

        storage.makedirs(dir_path)

        assert Path(dir_path).exists()
        assert Path(dir_path).is_dir()

    @pytest.mark.integration
    def test_copy_file(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """copy_file() should duplicate file."""
        src_path = str(test_data_dir / "source.txt")
        dest_path = str(test_data_dir / "copy.txt")

        storage.write_text(src_path, "original content")
        storage.copy_file(src_path, dest_path)

        assert storage.read_text(dest_path) == "original content"
        assert storage.file_exists(src_path)  # Source still exists

    @pytest.mark.integration
    def test_move_file(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """move_file() should relocate file."""
        src_path = str(test_data_dir / "to_move.txt")
        dest_path = str(test_data_dir / "moved.txt")

        storage.write_text(src_path, "content")
        storage.move_file(src_path, dest_path)

        assert storage.file_exists(dest_path) is True
        assert storage.file_exists(src_path) is False

    @pytest.mark.integration
    def test_remove_dir(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """remove_dir() should delete directory and contents."""
        dir_path = test_data_dir / "to_remove"
        dir_path.mkdir()
        (dir_path / "file1.txt").write_text("content1")
        (dir_path / "subdir").mkdir()
        (dir_path / "subdir" / "file2.txt").write_text("content2")

        storage.remove_dir(str(dir_path))

        assert not dir_path.exists()

    @pytest.mark.integration
    def test_path_traversal_protection(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """Storage should reject path traversal attempts."""
        with pytest.raises(ValueError, match="traversal"):
            storage.write_text("../../../etc/passwd", "malicious")

    @pytest.mark.integration
    def test_allowed_roots_enforcement(self, storage: FsFileStorage) -> None:
        """Storage should reject paths outside allowed roots."""
        with pytest.raises(ValueError, match="not in allowed"):
            storage.write_text("/tmp/outside/test.txt", "content")

    @pytest.mark.integration
    def test_creates_parent_directories(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """File operations should create parent directories."""
        file_path = str(test_data_dir / "nested" / "deep" / "file.txt")

        storage.write_text(file_path, "content")

        assert Path(file_path).exists()

    @pytest.mark.integration
    def test_is_regular_file(self, storage: FsFileStorage, test_data_dir: Path) -> None:
        """is_regular_file() should distinguish files from directories."""
        file_path = str(test_data_dir / "regular.txt")
        dir_path = str(test_data_dir / "directory")

        storage.write_text(file_path, "content")
        storage.makedirs(dir_path)

        assert storage.is_regular_file(file_path) is True
        assert storage.is_regular_file(dir_path) is False
        assert storage.is_regular_file(str(test_data_dir / "nonexistent")) is False
