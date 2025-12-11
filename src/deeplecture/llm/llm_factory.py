"""
Factory for creating LLM instances.
Supports OpenAI‑compatible chat APIs and Gemini (auth API) via google‑genai.
"""

import io
import logging
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union

from openai import OpenAI

from deeplecture.infra.rate_limiter import RateLimiter
from deeplecture.infra.retry import RetryConfig, with_retry
from deeplecture.config.config import load_config

logger = logging.getLogger(__name__)


class LLM(ABC):
    """Abstract base class for LLM services."""

    @abstractmethod
    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        image_path: Optional[Union[str, List[str]]] = None,
    ) -> str:
        """
        Generate a response from the LLM based on the given prompt.

        Args:
            prompt: The prompt to send to the LLM.
            system_prompt: Optional system prompt for context.
            temperature: Optional temperature parameter.
            image_path: Optional path or URL to an image for vision models.

        Returns:
            The LLM's response as a string.
        """
        raise NotImplementedError


class RateLimitedLLM(LLM):
    """
    LLM decorator that enforces a RateLimiter around generate_response calls.

    This keeps the underlying LLM implementation unchanged while ensuring
    that all outbound requests respect a shared max RPM configuration.
    """

    def __init__(self, inner: LLM, limiter: RateLimiter) -> None:
        self._inner = inner
        self._limiter = limiter

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        image_path: Optional[Union[str, List[str]]] = None,
    ) -> str:
        self._limiter.acquire()
        return self._inner.generate_response(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            image_path=image_path,
        )


class RetryableLLM(LLM):
    """
    LLM decorator that adds retry logic with exponential backoff.

    Wraps generate_response calls with tenacity-based retry, respecting
    the configured max_retries and wait times.
    """

    def __init__(self, inner: LLM, retry_config: RetryConfig) -> None:
        self._inner = inner
        self._retry_config = retry_config

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        image_path: Optional[Union[str, List[str]]] = None,
    ) -> str:
        # Create a wrapped function with retry logic
        retryable_call = with_retry(
            self._inner.generate_response,
            max_retries=self._retry_config.max_retries,
            min_wait=self._retry_config.min_wait,
            max_wait=self._retry_config.max_wait,
            logger_name="deeplecture.llm",
        )
        return retryable_call(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            image_path=image_path,
        )


class ModelRegistry:
    """
    Registry for configured LLM models and task-to-model mappings.

    Supports both single-model config and multi-model config (models/task_models structure).
    """

    def __init__(self, llm_config: Optional[Dict[str, Any]] = None) -> None:
        if llm_config is None:
            cfg = load_config()
            llm_config = cfg.get("llm") or {} if isinstance(cfg, dict) else {}

        self._llm_config: Dict[str, Any] = llm_config
        self._models: Dict[str, Dict[str, Any]] = {}
        self._task_models: Dict[str, str] = {}
        self._default_model_name = "default"
        self._build_registry()

    def _build_registry(self) -> None:
        cfg = self._llm_config or {}

        # Base fields shared across all models (exclude models/task_models)
        base: Dict[str, Any] = {}
        for key, value in cfg.items():
            if key in ("models", "task_models"):
                continue
            base[key] = value

        raw_models = cfg.get("models")
        if isinstance(raw_models, list):
            for item in raw_models:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                model_cfg: Dict[str, Any] = dict(base)
                model_cfg.update(item)
                self._models[name] = model_cfg

        # If no models list provided, treat entire config as single "default" model
        if not self._models:
            self._models["default"] = dict(base)
            self._default_model_name = "default"
        else:
            task_cfg = cfg.get("task_models")
            default_from_task: Optional[str] = None
            if isinstance(task_cfg, dict):
                raw_default = task_cfg.get("default")
                default_from_task = str(raw_default or "").strip() or None

            if default_from_task and default_from_task in self._models:
                self._default_model_name = default_from_task
            else:
                self._default_model_name = next(iter(self._models))

        raw_task_models = cfg.get("task_models")
        if isinstance(raw_task_models, dict):
            for task, model in raw_task_models.items():
                model_name = str(model or "").strip()
                if not model_name or model_name not in self._models:
                    continue
                task_name = str(task or "").strip()
                if not task_name:
                    continue
                self._task_models[task_name] = model_name

    def get_model_config(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Resolve model config by name, fallback to default."""
        if not self._models:
            return {}
        target = name or self._default_model_name
        cfg = self._models.get(target)
        if cfg is not None:
            return cfg
        return self._models[self._default_model_name]

    def get_task_model_config(self, task: str) -> Dict[str, Any]:
        """Resolve model config for a task, fallback to default."""
        if not self._models:
            return {}
        task_name = str(task or "").strip()
        model_name = self._task_models.get(task_name) or self._default_model_name
        cfg = self._models.get(model_name)
        if cfg is not None:
            return cfg
        return self._models[self._default_model_name]

    def list_models(self) -> List[Dict[str, Any]]:
        """Return list of configured models with their metadata."""
        return [
            {"name": name, "model": cfg.get("model", ""), "provider": cfg.get("provider", "")}
            for name, cfg in self._models.items()
        ]

    def get_task_models(self) -> Dict[str, str]:
        """Return task-to-model mapping."""
        return dict(self._task_models)

    def get_default_model_name(self) -> str:
        """Return the default model name."""
        return self._default_model_name

    def update_task_models(self, new_mappings: Dict[str, str]) -> None:
        """Hot-update task-to-model mappings without full reload."""
        for task, model in new_mappings.items():
            task_name = str(task or "").strip()
            model_name = str(model or "").strip()
            if not task_name or not model_name:
                continue
            if model_name in self._models:
                self._task_models[task_name] = model_name


class OpenAICompatibleLLM(LLM):
    """LLM implementation for OpenAI and compatible APIs."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the OpenAI compatible LLM service.

        Args:
            config: Optional configuration dictionary.
        """
        if config is None:
            # Load from global config
            global_config = load_config()
            config = global_config.get("llm", {})

        # Get API key from config
        api_key = config.get("api_key", "")
        if not api_key:
            logger.warning("No API key found in conf.yaml (llm.api_key)")

        # Get base URL from config
        base_url = config.get("base_url", "")

        # Create client
        client_kwargs: Dict[str, Any] = {}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(api_key=api_key, **client_kwargs)

        # Set model and temperature
        self.model = config.get("model", "gpt-5.1")
        self.default_temperature = float(config.get("temperature", 0.7))

        logger.debug("Initialized OpenAI-compatible LLM with model: %s", self.model)

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        image_path: Optional[Union[str, List[str]]] = None,
    ) -> str:
        """
        Generate a response using the OpenAI chat completions API.

        Args:
            prompt: The prompt to send to the API.
            system_prompt: Optional system prompt for context.
            temperature: Optional temperature parameter.
            image_path: Optional path or URL to an image.

        Returns:
            The API's response as a string.
        """
        try:
            # Use provided temperature or default
            actual_temperature = temperature if temperature is not None else self.default_temperature

            # Prepare messages
            messages: list[dict[str, Any]] = []

            # Add system message if provided
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # Add user message
            user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

            # Add one or more images if provided. We accept either a single
            # string path/URL or a list of paths/URLs for multi-image prompts.
            image_paths: List[str] = []
            if isinstance(image_path, str):
                image_paths = [image_path]
            elif isinstance(image_path, (list, tuple)):
                image_paths = [p for p in image_path if isinstance(p, str)]

            if image_paths:
                import base64

                for path in image_paths:
                    # Check if it's a URL or local path
                    if path.startswith(("http://", "https://")):
                        image_url = path
                    else:
                        # Read and encode local image
                        try:
                            with open(path, "rb") as image_file:
                                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                                image_url = f"data:image/jpeg;base64,{encoded_string}"
                        except Exception as exc:
                            logger.error("Failed to read image file: %s", exc)
                            raise

                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        }
                    )

            messages.append({"role": "user", "content": user_content})

            # Call API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=actual_temperature,
            )

            # Extract and return the response text
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("Error generating response: %s", exc)
            raise


class GeminiLLM(LLM):
    """LLM implementation for Gemini auth API via google-genai."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        if config is None:
            global_config = load_config()
            config = global_config.get("llm", {})

        self.model = config.get("model", "gemini-1.5-pro")
        self.default_temperature = float(config.get("temperature", 0.7))

        api_key = config.get("api_key", "")
        if not api_key:
            logger.warning("No API key found in conf.yaml (llm.api_key) for Gemini provider")

        base_url = config.get("base_url", "")

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise RuntimeError(
                "Gemini provider requires the google-genai package; please install project dependencies."
            ) from exc

        client_kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            try:
                client_kwargs["http_options"] = genai_types.HttpOptions(base_url=base_url)
            except Exception as exc:
                logger.warning("Failed to apply Gemini base_url override (%s): %s", base_url, exc)

        self._genai = genai
        self._genai_types = genai_types
        self.client = genai.Client(**client_kwargs)

    def _load_image(self, path: str):
        """Load an image from local path or URL into a PIL Image."""
        try:
            from PIL import Image
        except ImportError as exc:
            logger.error("Pillow is required for image prompts: %s", exc)
            return None

        try:
            if path.startswith(("http://", "https://")):
                with urllib.request.urlopen(path) as resp:
                    data = resp.read()
                img = Image.open(io.BytesIO(data))
            else:
                img = Image.open(path)
            img.load()
            return img
        except Exception as exc:
            logger.warning("Failed to load image for Gemini prompt (%s): %s", path, exc)
            return None

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        image_path: Optional[Union[str, List[str]]] = None,
    ) -> str:
        try:
            actual_temperature = temperature if temperature is not None else self.default_temperature

            prompt_parts: List[Any] = [prompt]

            image_paths: List[str] = []
            if isinstance(image_path, str):
                image_paths = [image_path]
            elif isinstance(image_path, (list, tuple)):
                image_paths = [p for p in image_path if isinstance(p, str)]

            if image_paths:
                for path in image_paths:
                    img = self._load_image(path)
                    if img is not None:
                        prompt_parts.append(img)

            if system_prompt:
                config = self._genai_types.GenerateContentConfig(
                    temperature=actual_temperature,
                    system_instruction=system_prompt,
                )
            else:
                config = self._genai_types.GenerateContentConfig(
                    temperature=actual_temperature,
                )

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt_parts,
                config=config,
            )

            if getattr(response, "text", None):
                return response.text

            # Fallback: extract first candidate text if .text missing
            candidates = getattr(response, "candidates", None)
            if candidates:
                try:
                    content = candidates[0].content
                    if content and getattr(content, "parts", None):
                        return content.parts[0].text
                except Exception:
                    pass

            return ""
        except Exception as exc:
            logger.error("Error generating response from Gemini: %s", exc)
            raise


class LLMFactory:
    """Factory for creating LLM services."""

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        retry_config: Optional[RetryConfig] = None,
    ) -> None:
        # Keep a local view of the model registry so that all factory
        # instances share a single source of truth for model configs.
        self._registry = registry or ModelRegistry()

        # Load retry config from llm section if not provided
        if retry_config is None:
            cfg = load_config()
            llm_cfg = cfg.get("llm") or {} if isinstance(cfg, dict) else {}
            retry_config = RetryConfig.from_config(llm_cfg)
        self._retry_config = retry_config

    def _build_llm_from_config(self, config: Dict[str, Any]) -> LLM:
        provider = str(config.get("provider") or "").lower()
        if provider == "gemini":
            llm = GeminiLLM(config)
        else:
            llm = OpenAICompatibleLLM(config)

        # Wrap with retry logic if max_retries > 0
        if self._retry_config.max_retries > 0:
            llm = RetryableLLM(llm, self._retry_config)

        return llm

    def get_llm(
        self,
        config: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> LLM:
        """
        Get an LLM service instance.

        Args:
            config: Optional configuration dictionary override. When provided,
                it bypasses the registry and is used as‑is.
            model_name: Optional logical model name from the registry. Ignored
                when ``config`` is provided.

        Returns:
            An LLM service instance.
        """
        if config is not None:
            return self._build_llm_from_config(config)

        resolved_config = self._registry.get_model_config(model_name)
        return self._build_llm_from_config(resolved_config)

    def get_llm_for_task(self, task_name: str) -> LLM:
        """
        Get an LLM instance bound to a logical task name.

        This uses the ``llm.task_models`` mapping from configuration and
        falls back to the default model when no explicit mapping exists.
        """
        resolved_config = self._registry.get_task_model_config(task_name)
        return self._build_llm_from_config(resolved_config)

    def get_registry(self) -> ModelRegistry:
        """Expose the underlying registry for inspection or testing."""
        return self._registry

    def update_task_models(self, new_mappings: Dict[str, str]) -> None:
        """Hot-update task-to-model mappings in the registry."""
        self._registry.update_task_models(new_mappings)
