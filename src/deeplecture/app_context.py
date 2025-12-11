"""
Shared application context and helpers for the Flask backend.

Unified storage architecture:
    data/
    ├── db/           - All SQLite databases
    ├── content/      - Per-content-id organized storage
    ├── temp/         - Temporary files
    └── logs/         - Application logs
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, Optional

try:
    import json_repair
except ImportError:

    class _JsonRepair:
        @staticmethod
        def load(file_obj):
            return json.load(file_obj)

    json_repair = _JsonRepair()

from deeplecture.infra.rate_limiter import RateLimiter
from deeplecture.llm.llm_factory import LLM, LLMFactory, ModelRegistry, RateLimitedLLM
from deeplecture.tts.tts_factory import TTSFactory
from deeplecture.config.config import load_config


class RateLimitedLLMFactory(LLMFactory):
    """LLMFactory variant that wraps created LLM instances with a RateLimiter."""

    def __init__(self, limiter: RateLimiter, registry: Optional[ModelRegistry] = None) -> None:
        super().__init__(registry=registry)
        self._limiter = limiter

    def get_llm(
        self,
        config: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> LLM:
        base = super().get_llm(config=config, model_name=model_name)
        return RateLimitedLLM(base, self._limiter)

    def get_llm_for_task(self, task_name: str) -> LLM:
        base = super().get_llm_for_task(task_name)
        return RateLimitedLLM(base, self._limiter)


class AppContext:
    """
    Lazily-initialized application context with unified storage paths.

    All data lives under a single `data/` directory:
        data/db/        - SQLite databases (tasks.db, config.db)
        data/content/   - Per-content organized storage
        data/temp/      - Temporary files
        data/logs/      - Application logs
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        # Project root is 2 levels up from this file (src/deeplecture/app_context.py -> project root)
        default_base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.base_dir = base_dir or default_base
        self._config: Optional[Dict[str, Any]] = None
        self._app_cfg: Dict[str, Any] = {}

        # Unified data root
        self._data_dir: Optional[str] = None
        self._db_dir: Optional[str] = None
        self._content_dir: Optional[str] = None
        self._temp_dir: Optional[str] = None
        self._log_dir: Optional[str] = None

        self._logger: Optional[logging.Logger] = None
        self._llm_rate_limiter: Optional[RateLimiter] = None
        self._tts_rate_limiter: Optional[RateLimiter] = None
        self._llm_factory: Optional[RateLimitedLLMFactory] = None
        self._tts_factory: Optional[TTSFactory] = None

        self._initialized: bool = False
        self._init_lock = threading.RLock()

    def load_config(self, config: Optional[Dict[str, Any]] = None, *, reload: bool = False) -> Dict[str, Any]:
        with self._init_lock:
            if self._config is not None and not reload and config is None:
                return self._config

            if config is not None:
                self._config = config
            else:
                self._config = load_config()
            self._app_cfg = self._config.get("app", {}) if isinstance(self._config, dict) else {}
            return self._config

    def init_paths(self) -> None:
        with self._init_lock:
            if self._data_dir:
                return

            if self._config is None:
                self.load_config()

            # Single data root - configurable but defaults to "data"
            data_root = self._app_cfg.get("data_dir", "data")
            self._data_dir = os.path.join(self.base_dir, data_root)

            # All subdirectories under data/
            self._db_dir = os.path.join(self._data_dir, "db")
            self._content_dir = os.path.join(self._data_dir, "content")
            self._temp_dir = os.path.join(self._data_dir, "temp")
            self._log_dir = os.path.join(self._data_dir, "logs")

            for path in (self._db_dir, self._content_dir, self._temp_dir, self._log_dir):
                os.makedirs(path, exist_ok=True)

    def init_logging(self, *, level: int = logging.INFO, force: bool = False) -> logging.Logger:
        with self._init_lock:
            if self._logger is not None and not force:
                return self._logger

            self.init_paths()

            root = logging.getLogger()
            if force or not root.handlers:
                root.handlers.clear()
                root.setLevel(level)

                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )

                console_handler = logging.StreamHandler()
                console_handler.setLevel(level)
                console_handler.setFormatter(formatter)

                file_handler = logging.FileHandler(
                    os.path.join(self._log_dir, "server.log"),
                    encoding="utf-8",
                )
                file_handler.setLevel(level)
                file_handler.setFormatter(formatter)

                root.addHandler(console_handler)
                root.addHandler(file_handler)

            logger_name = self._app_cfg.get("logger_name", "app")
            self._logger = logging.getLogger(logger_name)
            return self._logger

    def init_factories(self) -> None:
        with self._init_lock:
            if self._llm_factory is not None and self._tts_factory is not None:
                return

            if self._config is None:
                self.load_config()
            self.init_paths()

            llm_cfg = {}
            tts_cfg = {}
            if isinstance(self._config, dict):
                llm_cfg = self._config.get("llm") or {}
                tts_cfg = self._config.get("tts") or {}

            # Global LLM rate limiter
            llm_max_rpm = int(llm_cfg.get("max_rpm", 60) or 60)
            llm_limiter = RateLimiter(max_rpm=llm_max_rpm)
            self._llm_rate_limiter = llm_limiter

            # Global TTS rate limiter
            tts_max_rpm = int(tts_cfg.get("max_rpm", 60) or 60)
            tts_limiter = RateLimiter(max_rpm=tts_max_rpm)
            self._tts_rate_limiter = tts_limiter

            registry = ModelRegistry(llm_cfg)
            self._llm_factory = RateLimitedLLMFactory(llm_limiter, registry=registry)
            self._tts_factory = TTSFactory(limiter=tts_limiter)

    def init_all(self, *, reload: bool = False) -> None:
        with self._init_lock:
            if self._initialized and not reload:
                return

            self.load_config(reload=reload)
            self.init_paths()
            self.init_logging(force=reload)
            self.init_factories()
            self._initialized = True

    # ------------------------------------------------------------------
    # Path accessors
    # ------------------------------------------------------------------
    @property
    def data_dir(self) -> str:
        if self._data_dir is None:
            self.init_paths()
        return self._data_dir  # type: ignore[return-value]

    @property
    def db_dir(self) -> str:
        if self._db_dir is None:
            self.init_paths()
        return self._db_dir  # type: ignore[return-value]

    @property
    def content_dir(self) -> str:
        if self._content_dir is None:
            self.init_paths()
        return self._content_dir  # type: ignore[return-value]

    @property
    def temp_dir(self) -> str:
        if self._temp_dir is None:
            self.init_paths()
        return self._temp_dir  # type: ignore[return-value]

    @property
    def log_dir(self) -> str:
        if self._log_dir is None:
            self.init_paths()
        return self._log_dir  # type: ignore[return-value]

    # Convenience methods for content paths
    def content_path(self, content_id: str, *subpaths: str) -> str:
        """Get path for a content item: data/content/{content_id}/[subpaths]"""
        path = os.path.join(self.content_dir, content_id, *subpaths)
        os.makedirs(os.path.dirname(path) if subpaths else path, exist_ok=True)
        return path

    def db_path(self, db_name: str) -> str:
        """Get path for a database file: data/db/{db_name}"""
        return os.path.join(self.db_dir, db_name)

    # ------------------------------------------------------------------
    # Other accessors
    # ------------------------------------------------------------------
    @property
    def config(self) -> Dict[str, Any]:
        if self._config is None:
            self.load_config()
        return self._config or {}

    @property
    def app_config(self) -> Dict[str, Any]:
        if not self._app_cfg:
            self.load_config()
        return self._app_cfg

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self.init_logging()
        return self._logger

    @property
    def llm_rate_limiter(self) -> RateLimiter:
        if self._llm_rate_limiter is None:
            self.init_factories()
        return self._llm_rate_limiter  # type: ignore[return-value]

    @property
    def tts_rate_limiter(self) -> RateLimiter:
        if self._tts_rate_limiter is None:
            self.init_factories()
        return self._tts_rate_limiter  # type: ignore[return-value]

    @property
    def llm_factory(self) -> RateLimitedLLMFactory:
        if self._llm_factory is None:
            self.init_factories()
        return self._llm_factory  # type: ignore[return-value]

    @property
    def tts_factory(self) -> TTSFactory:
        if self._tts_factory is None:
            self.init_factories()
        return self._tts_factory  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def ensure_initialized(self) -> None:
        if not self._initialized:
            self.init_all()

    def cleanup(self) -> None:
        """Release file handlers and reset factories so tests or reloads don't duplicate output."""
        with self._init_lock:
            if self._logger:
                for handler in list(self._logger.handlers):
                    self._logger.removeHandler(handler)
                    try:
                        handler.close()
                    except Exception:
                        pass
            self._logger = None
            self._llm_factory = None
            self._tts_factory = None
            self._llm_rate_limiter = None
            self._tts_rate_limiter = None
            self._initialized = False


_default_context = AppContext()


def get_app_context() -> AppContext:
    """Return the process-wide default AppContext (uninitialized)."""
    return _default_context


def initialize_default_context(*, reload: bool = False) -> AppContext:
    """Initialize and return the default context."""
    ctx = get_app_context()
    ctx.init_all(reload=reload)
    return ctx


__all__ = [
    "AppContext",
    "RateLimitedLLMFactory",
    "get_app_context",
    "initialize_default_context",
]
