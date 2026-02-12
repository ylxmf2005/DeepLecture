"""Unit tests for Flask global error handlers."""

from __future__ import annotations

import pytest
from flask import request

from deeplecture.presentation.api.app import create_app


class TestGlobalErrorHandlers:
    """Covers global Flask error mappings."""

    @pytest.mark.unit
    def test_request_entity_too_large_returns_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """413 should be returned as API JSON envelope, not HTML."""
        from deeplecture.presentation.api import app as app_module

        monkeypatch.setattr(app_module, "init_rate_limiter", lambda _app: None)
        monkeypatch.setattr(app_module, "_register_blueprints", lambda _app: None)

        app = create_app(start_workers=False)
        app.config["TESTING"] = True
        app.config["MAX_CONTENT_LENGTH"] = 1

        @app.route("/unit/upload", methods=["POST"])
        def upload_endpoint() -> dict[str, bool]:
            request.get_data(cache=False)
            return {"ok": True}

        client = app.test_client()
        resp = client.post("/unit/upload", data=b"ab", content_type="application/octet-stream")

        assert resp.status_code == 413
        body = resp.get_json()
        assert body["success"] is False
        assert body["code"] == "PAYLOAD_TOO_LARGE"
