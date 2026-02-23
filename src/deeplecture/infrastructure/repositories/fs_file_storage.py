"""Filesystem-based file storage implementation."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Any


def _validate_path(file_path: str, allowed_roots: frozenset[Path] | None = None) -> Path:
    """
    Validate file path for security.

    Args:
        file_path: Path to validate
        allowed_roots: Optional set of allowed root directories

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path is invalid or not allowed
    """
    if not file_path:
        raise ValueError("Empty file path")

    # Check for path traversal attempts
    if ".." in file_path:
        raise ValueError(f"Path traversal not allowed: {file_path}")

    resolved = Path(file_path).resolve()

    # Validate against allowed roots if specified
    if allowed_roots and not any(_is_under(resolved, root) for root in allowed_roots):
        raise ValueError(f"Path not in allowed directories: {file_path}")

    return resolved


def _is_under(path: Path, root: Path) -> bool:
    """Check if path is under root directory."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class FsFileStorage:
    """
    Filesystem-based file storage implementation.

    Implements FileStorageProtocol for basic file operations.
    Thread-safe for independent file operations.

    Args:
        allowed_roots: Optional set of allowed root directories for path validation.
                      If None, path validation is relaxed (development mode only).
    """

    def __init__(self, allowed_roots: frozenset[Path] | None = None) -> None:
        if allowed_roots:
            self._allowed_roots = frozenset(p.resolve() for p in allowed_roots)
        else:
            self._allowed_roots = None

    def _validate(self, file_path: str) -> Path:
        """Validate file path and return resolved Path."""
        return _validate_path(file_path, self._allowed_roots)

    def save_file(self, file_obj: Any, destination_path: str) -> None:
        """Save file-like object or bytes to destination."""
        p = self._validate(destination_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        if hasattr(file_obj, "read"):
            # Stream to disk to avoid loading large uploads into memory.
            with open(p, "wb") as out:
                shutil.copyfileobj(file_obj, out, length=1024 * 1024)
        elif isinstance(file_obj, bytes | bytearray):
            p.write_bytes(bytes(file_obj))
        else:
            raise TypeError(f"Unsupported file_obj type: {type(file_obj)}")

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """Get page count from PDF using pypdfium2."""
        self._validate(pdf_path)
        try:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(pdf_path)
            try:
                return len(pdf)
            finally:
                pdf.close()
        except ImportError:
            return 0

    def move_file(self, src_path: str, dest_path: str) -> None:
        """Move file from source to destination."""
        self._validate(src_path)
        self._validate(dest_path)
        shutil.move(src_path, dest_path)

    def remove_file(self, file_path: str) -> None:
        """Remove a file."""
        self._validate(file_path)
        os.remove(file_path)

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
        try:
            self._validate(file_path)
            return os.path.exists(file_path)
        except ValueError:
            return False

    def is_regular_file(self, file_path: str) -> bool:
        """Check if path is a regular file (not directory/symlink)."""
        try:
            self._validate(file_path)
            return stat.S_ISREG(os.lstat(file_path).st_mode)
        except (OSError, ValueError):
            return False

    def remove_dir(self, dir_path: str) -> None:
        """Remove a directory and all its contents."""
        resolved = self._validate(dir_path)
        if resolved.exists():
            shutil.rmtree(str(resolved))

    def copy_file(self, src_path: str, dest_path: str) -> None:
        """Copy file preserving metadata."""
        self._validate(src_path)
        self._validate(dest_path)
        shutil.copy2(src_path, dest_path)

    def makedirs(self, dir_path: str, exist_ok: bool = True) -> None:
        """Create directory and all parent directories."""
        self._validate(dir_path)
        os.makedirs(dir_path, exist_ok=exist_ok)

    def read_text(self, file_path: str, encoding: str = "utf-8") -> str:
        """Read file contents as text."""
        self._validate(file_path)
        with open(file_path, encoding=encoding) as f:
            return f.read()

    def write_text(self, file_path: str, content: str, encoding: str = "utf-8") -> None:
        """Write text content to file."""
        p = self._validate(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)

    def read_bytes(self, file_path: str) -> bytes:
        """Read file contents as bytes."""
        self._validate(file_path)
        with open(file_path, "rb") as f:
            return f.read()

    def write_bytes(self, file_path: str, data: bytes) -> None:
        """Write bytes to file."""
        p = self._validate(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(data)

    def replace_file(self, src_path: str, dest_path: str) -> None:
        """Atomically replace destination file with source file."""
        self._validate(src_path)
        self._validate(dest_path)
        os.replace(src_path, dest_path)
