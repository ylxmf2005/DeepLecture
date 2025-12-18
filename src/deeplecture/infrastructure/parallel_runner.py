"""Infrastructure implementation for parallel execution."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, TypeVar

from deeplecture.use_cases.interfaces.parallel import ParallelRunnerProtocol

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from deeplecture.config.settings import TaskParallelismConfig
    from deeplecture.use_cases.interfaces.parallel import ParallelGroup

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class ThreadPoolParallelRunner(ParallelRunnerProtocol):
    """ThreadPool-based ParallelRunnerProtocol implementation."""

    def __init__(self, config: TaskParallelismConfig) -> None:
        self._cfg = config

    def _max_workers(self, group: ParallelGroup) -> int:
        # Unified concurrency for all task types
        del group  # group preserved for future per-task tuning if needed
        return int(self._cfg.default)

    def map_ordered(
        self,
        items: Sequence[T],
        fn: Callable[[T], R],
        *,
        group: ParallelGroup,
        on_error: Callable[[Exception, T], R] | None = None,
    ) -> list[R]:
        if not items:
            return []

        max_workers = max(1, self._max_workers(group))
        if max_workers <= 1 or len(items) == 1:
            results: list[R] = []
            for item in items:
                try:
                    results.append(fn(item))
                except Exception as exc:
                    if on_error is None:
                        raise
                    results.append(on_error(exc, item))
            return results

        worker_count = min(max_workers, len(items))
        logger.debug("ParallelRunner group=%s workers=%d items=%d", group, worker_count, len(items))

        results: list[R] = [None] * len(items)  # type: ignore[list-item]

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_idx = {executor.submit(fn, item): idx for idx, item in enumerate(items)}

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                item = items[idx]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    if on_error is None:
                        raise
                    results[idx] = on_error(exc, item)

        return results
