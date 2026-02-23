"""
CLI entrypoint for running the DeepLecture backend.

This exists because the project exposes a console script:
`deeplecture = deeplecture.app:main` (see pyproject.toml).
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

from deeplecture.config import get_settings
from deeplecture.presentation.api.app import create_app


def _configure_logging() -> None:
    """Configure logging based on settings."""
    settings = get_settings()
    log_config = settings.app.logging

    # Determine effective log level
    level_name = os.environ.get("DEEPLECTURE_LOG_LEVEL", log_config.level).upper()
    level = getattr(logging, level_name, logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_config.format,
        force=True,
    )

    # Apply specific logger levels from config
    for logger_name, logger_level in log_config.loggers.items():
        logging.getLogger(logger_name).setLevel(getattr(logging, logger_level.upper(), level))

    # Always enable Claude Code trace logger if log level is DEBUG or user explicitly enables
    if level <= logging.DEBUG or os.environ.get("DEEPLECTURE_CLAUDE_TRACE", "").lower() == "true":
        logging.getLogger("deeplecture.claude_code.trace").setLevel(logging.DEBUG)

    logging.getLogger(__name__).info("Logging configured: level=%s", level_name)


_frontend_process: subprocess.Popen | None = None


def _start_frontend() -> subprocess.Popen | None:
    """Start the Next.js frontend dev server in a new process group."""
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if not frontend_dir.exists():
        print(f"[deeplecture] Frontend directory not found: {frontend_dir}", file=sys.stderr)
        return None

    print(f"[deeplecture] Starting frontend at {frontend_dir}...")
    try:
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            start_new_session=True,  # Create new process group for clean termination
        )
        return proc
    except FileNotFoundError:
        print("[deeplecture] npm not found, skipping frontend", file=sys.stderr)
        return None


def _stop_frontend() -> None:
    """Terminate the frontend process group on exit."""
    global _frontend_process
    if _frontend_process and _frontend_process.poll() is None:
        print("[deeplecture] Stopping frontend...")
        try:
            os.killpg(os.getpgid(_frontend_process.pid), signal.SIGTERM)
            _frontend_process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(_frontend_process.pid), signal.SIGKILL)


def main() -> None:
    global _frontend_process

    # Initialize logging first
    _configure_logging()

    settings = get_settings()

    host = os.environ.get("DEEPLECTURE_HOST", "0.0.0.0")
    port = int(os.environ.get("DEEPLECTURE_PORT", "11393"))

    debug = bool(settings.app.debug)
    use_reloader = debug

    # When the reloader is enabled, Flask starts a parent process that imports
    # the app too. Start workers only in the reloader child.
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    start_workers = bool(settings.server.run_worker) and (not use_reloader or is_reloader_child)

    # Start frontend in parent process (survives reloader restarts) or if no reloader
    if not use_reloader or not is_reloader_child:
        _frontend_process = _start_frontend()
        if _frontend_process:
            atexit.register(_stop_frontend)

    app = create_app(start_workers=start_workers)
    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
