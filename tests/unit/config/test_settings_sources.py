"""Unit tests for layered settings source loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from deeplecture.config import settings as settings_module

if TYPE_CHECKING:
    from pathlib import Path


def _write_yaml(path: Path, *, max_upload_bytes: int, max_note_image_bytes: int) -> None:
    path.write_text(
        "\n".join(
            [
                "server:",
                f"  max_upload_bytes: {max_upload_bytes}",
                f"  max_note_image_bytes: {max_note_image_bytes}",
                "",
            ]
        ),
        encoding="utf-8",
    )


class TestSettingsSources:
    """Settings source precedence checks."""

    @pytest.mark.unit
    def test_conf_overrides_default_for_upload_limits(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """`conf.yaml` should override `conf.default.yaml` values when present."""
        default_path = tmp_path / "conf.default.yaml"
        conf_path = tmp_path / "conf.yaml"
        _write_yaml(default_path, max_upload_bytes=1024, max_note_image_bytes=512)
        _write_yaml(conf_path, max_upload_bytes=2048, max_note_image_bytes=1536)

        monkeypatch.setattr(settings_module, "CONFIG_DEFAULT_FILE", default_path)
        monkeypatch.setattr(settings_module, "CONFIG_FILE", conf_path)

        loaded = settings_module.Settings()

        assert loaded.server.max_upload_bytes == 2048
        assert loaded.server.max_note_image_bytes == 1536

    @pytest.mark.unit
    def test_default_used_when_conf_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """`conf.default.yaml` should be used even when `conf.yaml` is missing."""
        default_path = tmp_path / "conf.default.yaml"
        missing_conf = tmp_path / "missing-conf.yaml"
        _write_yaml(default_path, max_upload_bytes=4096, max_note_image_bytes=3072)

        monkeypatch.setattr(settings_module, "CONFIG_DEFAULT_FILE", default_path)
        monkeypatch.setattr(settings_module, "CONFIG_FILE", missing_conf)

        loaded = settings_module.Settings()

        assert loaded.server.max_upload_bytes == 4096
        assert loaded.server.max_note_image_bytes == 3072
