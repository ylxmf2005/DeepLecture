from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Generic, Iterable, Optional, Tuple, TypeVar

R = TypeVar("R")  # Shared resource type (e.g. LLM client, TTS engine)
K = TypeVar("K")  # Task key used to index results
T = TypeVar("T")  # Task payload
V = TypeVar("V")  # Task result

logger = logging.getLogger(__name__)


class ResourceWorkerPool(Generic[R, K, T, V]):
    """
    Small helper for running tasks in parallel while reusing one resource
    instance per worker thread (LLM client, TTS engine, etc.).
    """

    def __init__(
        self,
        name: str,
        max_workers: int,
        resource_factory: Callable[[], R],
    ) -> None:
        self.name = name
        self.max_workers = max(1, int(max_workers or 1))
        self._resource_factory = resource_factory
        self._local = threading.local()

    def _get_resource(self) -> R:
        """Lazy-create one resource instance per worker thread."""
        res = getattr(self._local, "resource", None)
        if res is None:
            res = self._resource_factory()
            self._local.resource = res
        return res

    def map(
        self,
        tasks: Iterable[Tuple[K, T]],
        handler: Callable[[R, K, T], V],
        *,
        on_error: Optional[Callable[[BaseException, K], Optional[V]]] = None,
    ) -> Dict[K, V]:
        """
        Run tasks concurrently and return a mapping from task key to result.

        If on_error is provided, exceptions are passed to it and normal
        execution continues; otherwise the first exception is raised.
        """
        task_list = list(tasks)
        results: Dict[K, V] = {}

        if not task_list:
            return results

        if self.max_workers <= 1 or len(task_list) == 1:
            resource = self._get_resource()
            for key, payload in task_list:
                try:
                    results[key] = handler(resource, key, payload)
                except BaseException as exc:
                    if on_error:
                        fallback = on_error(exc, key)
                        if fallback is not None:
                            results[key] = fallback
                        continue
                    raise
            return results

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(task_list))) as executor:
            future_map = {
                executor.submit(self._run_task, handler, key, payload): key
                for key, payload in task_list
            }

            for future in as_completed(future_map):
                key = future_map[future]
                try:
                    results[key] = future.result()
                except BaseException as exc:
                    if on_error:
                        fallback = on_error(exc, key)
                        if fallback is not None:
                            results[key] = fallback
                        continue
                    raise

        return results

    def _run_task(
        self,
        handler: Callable[[R, K, T], V],
        key: K,
        payload: T,
    ) -> V:
        resource = self._get_resource()
        return handler(resource, key, payload)
