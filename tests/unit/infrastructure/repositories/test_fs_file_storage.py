"""Unit tests for FsFileStorage."""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING

import pytest

from deeplecture.infrastructure.repositories.fs_file_storage import FsFileStorage

if TYPE_CHECKING:
    from pathlib import Path


class TestFsFileStorageGetPdfPageCount:
    """Tests for get_pdf_page_count()."""

    @pytest.mark.unit
    def test_get_pdf_page_count_closes_pdf_document(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_pdf_page_count() should close PdfDocument after reading length."""
        calls: dict[str, object] = {"closed": False}

        class FakePdfDocument:
            def __init__(self, path: str) -> None:
                calls["path"] = path

            def __len__(self) -> int:
                return 7

            def close(self) -> None:
                calls["closed"] = True

        fake_pdfium = types.SimpleNamespace(PdfDocument=FakePdfDocument)
        monkeypatch.setitem(sys.modules, "pypdfium2", fake_pdfium)

        storage = FsFileStorage(allowed_roots=None)
        pdf_path = tmp_path / "sample.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        result = storage.get_pdf_page_count(str(pdf_path))

        assert result == 7
        assert calls["path"] == str(pdf_path)
        assert calls["closed"] is True
