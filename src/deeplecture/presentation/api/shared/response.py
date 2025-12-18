"""
Unified API Response Envelope.

All API responses follow a consistent JSON structure:
- Success: { "success": true, "data": <payload> }
- Error: { "success": false, "error": "<message>", "code": "<STABLE_CODE>" }
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from flask import jsonify

if TYPE_CHECKING:
    from flask import Response


def success(data: Any, status: int = 200) -> Response:
    """Build success response envelope."""
    payload = _serialize(data)
    resp = jsonify({"success": True, "data": payload})
    resp.status_code = status
    return resp


def created(data: Any) -> Response:
    """201 Created response."""
    return success(data, status=201)


def accepted(data: Any) -> Response:
    """202 Accepted response (async task started)."""
    return success(data, status=202)


def error(
    message: str,
    code: str = "INTERNAL_ERROR",
    status: int = 500,
    details: Any | None = None,
) -> Response:
    """Build error response envelope."""
    payload: dict[str, Any] = {
        "success": False,
        "error": message,
        "code": code,
    }
    if details is not None:
        payload["details"] = _serialize(details)

    resp = jsonify(payload)
    resp.status_code = status
    return resp


def not_found(message: str = "Resource not found") -> Response:
    """404 Not Found."""
    return error(message, code="NOT_FOUND", status=404)


def bad_request(message: str, code: str = "INVALID_REQUEST") -> Response:
    """400 Bad Request."""
    return error(message, code=code, status=400)


def unauthorized(message: str = "Unauthorized") -> Response:
    """401 Unauthorized."""
    return error(message, code="UNAUTHORIZED", status=401)


def rate_limited(message: str = "Rate limit exceeded") -> Response:
    """429 Too Many Requests."""
    return error(message, code="RATE_LIMITED", status=429)


def _serialize(obj: Any) -> Any:
    """Serialize object for JSON response."""
    if obj is None:
        return None
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if isinstance(obj, list | tuple):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj
