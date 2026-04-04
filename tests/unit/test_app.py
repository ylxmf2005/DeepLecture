"""Unit tests for the CLI app entrypoint."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from deeplecture import app as app_module

pytestmark = pytest.mark.unit


def _make_settings(*, debug: bool, run_worker: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(debug=debug),
        server=SimpleNamespace(run_worker=run_worker),
    )


def test_main_starts_frontend_and_backend_on_normal_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """`deeplecture` should auto-start the frontend on a normal CLI launch."""
    settings = _make_settings(debug=False)
    fake_app = MagicMock()
    fake_proc = object()
    create_app = MagicMock(return_value=fake_app)
    start_frontend = MagicMock(return_value=fake_proc)
    register = MagicMock()

    monkeypatch.setattr(app_module, "_configure_logging", lambda: None)
    monkeypatch.setattr(app_module, "get_settings", lambda: settings)
    monkeypatch.setattr(app_module, "create_app", create_app)
    monkeypatch.setattr(app_module, "_start_frontend", start_frontend)
    monkeypatch.setattr(app_module.atexit, "register", register)
    monkeypatch.setattr(app_module, "_frontend_process", None)
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.delenv("DEEPLECTURE_HOST", raising=False)
    monkeypatch.delenv("DEEPLECTURE_PORT", raising=False)

    app_module.main()

    start_frontend.assert_called_once_with()
    register.assert_called_once_with(app_module._stop_frontend)
    create_app.assert_called_once_with(start_workers=True)
    fake_app.run.assert_called_once_with(
        host="0.0.0.0",
        port=11393,
        debug=False,
        use_reloader=False,
    )
    assert app_module._frontend_process is fake_proc


def test_main_skips_duplicate_frontend_start_in_reloader_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flask's reloader child must not spawn a second frontend process."""
    settings = _make_settings(debug=True)
    fake_app = MagicMock()
    create_app = MagicMock(return_value=fake_app)
    start_frontend = MagicMock()
    register = MagicMock()

    monkeypatch.setattr(app_module, "_configure_logging", lambda: None)
    monkeypatch.setattr(app_module, "get_settings", lambda: settings)
    monkeypatch.setattr(app_module, "create_app", create_app)
    monkeypatch.setattr(app_module, "_start_frontend", start_frontend)
    monkeypatch.setattr(app_module.atexit, "register", register)
    monkeypatch.setattr(app_module, "_frontend_process", None)
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    monkeypatch.delenv("DEEPLECTURE_HOST", raising=False)
    monkeypatch.delenv("DEEPLECTURE_PORT", raising=False)

    app_module.main()

    start_frontend.assert_not_called()
    register.assert_not_called()
    create_app.assert_called_once_with(start_workers=True)
    fake_app.run.assert_called_once_with(
        host="0.0.0.0",
        port=11393,
        debug=True,
        use_reloader=True,
    )
