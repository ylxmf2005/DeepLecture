"""Unit tests for conversation route screenshot path helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from deeplecture.presentation.api.routes.conversation import (
    _resolve_context_screenshot_paths,
    _resolve_screenshot_path,
)
from deeplecture.use_cases.dto.ask import ContextItem


def _container_for(content_root) -> SimpleNamespace:
    path_resolver = SimpleNamespace(get_content_dir=lambda content_id: str(content_root / content_id))
    return SimpleNamespace(path_resolver=path_resolver)


@pytest.mark.unit
def test_resolve_screenshot_api_path_to_local_file(tmp_path) -> None:
    """API screenshot URL resolves to local content screenshot path."""
    content_id = "d8c26680-338f-48ff-90cd-0ccafd480063"
    screenshots = tmp_path / content_id / "screenshots"
    screenshots.mkdir(parents=True)
    image_file = screenshots / "frame_7890705.png"
    image_file.write_bytes(b"png")

    container = _container_for(tmp_path)
    resolved, error = _resolve_screenshot_path(
        container,
        content_id,
        f"/api/content/{content_id}/screenshots/frame_7890705.png",
    )

    assert error is None
    assert resolved == str(image_file)


@pytest.mark.unit
def test_resolve_screenshot_api_url_with_host_to_local_file(tmp_path) -> None:
    """Absolute API URL with host resolves using its path component."""
    content_id = "d8c26680-338f-48ff-90cd-0ccafd480063"
    screenshots = tmp_path / content_id / "screenshots"
    screenshots.mkdir(parents=True)
    image_file = screenshots / "frame_7890705.png"
    image_file.write_bytes(b"png")

    container = _container_for(tmp_path)
    resolved, error = _resolve_screenshot_path(
        container,
        content_id,
        f"http://127.0.0.1:8080/api/content/{content_id}/screenshots/frame_7890705.png",
    )

    assert error is None
    assert resolved == str(image_file)


@pytest.mark.unit
def test_resolve_screenshot_rejects_other_content_id(tmp_path) -> None:
    """Screenshot URL must belong to the same content item."""
    content_id = "d8c26680-338f-48ff-90cd-0ccafd480063"
    other_id = "11111111-2222-3333-4444-555555555555"

    container = _container_for(tmp_path)
    resolved, error = _resolve_screenshot_path(
        container,
        content_id,
        f"/api/content/{other_id}/screenshots/frame_7890705.png",
    )

    assert resolved is None
    assert error == "screenshot context must reference this content's captured screenshot"


@pytest.mark.unit
def test_resolve_context_screenshot_paths_updates_item_data(tmp_path) -> None:
    """Context screenshot item imagePath is normalized to local file path."""
    content_id = "d8c26680-338f-48ff-90cd-0ccafd480063"
    screenshots = tmp_path / content_id / "screenshots"
    screenshots.mkdir(parents=True)
    image_file = screenshots / "frame_7890705.png"
    image_file.write_bytes(b"png")

    item = ContextItem(
        type="screenshot",
        data={
            "timestamp": 12.3,
            "imagePath": f"/api/content/{content_id}/screenshots/frame_7890705.png",
        },
    )

    container = _container_for(tmp_path)
    error = _resolve_context_screenshot_paths(container, content_id, [item])

    assert error is None
    assert item.data["imagePath"] == str(image_file)
