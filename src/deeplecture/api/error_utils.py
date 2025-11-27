from __future__ import annotations

import logging
from typing import Any, TypeAlias

from flask import Response, jsonify

FlaskResponse: TypeAlias = Response | tuple[Response, int]


def api_success(data: Any) -> FlaskResponse:
    """Standardize JSON success responses."""
    return jsonify({"success": True, "data": data})


def api_error(
    status: int,
    message: str,
    *,
    logger: logging.Logger | None = None,
    exc: BaseException | None = None,
) -> FlaskResponse:
    """Standardize JSON error responses and optional logging."""
    if logger:
        if exc:
            logger.error("%s: %s", message, exc, exc_info=True)
        else:
            logger.error("%s", message)
    return jsonify({"success": False, "error": message}), status
