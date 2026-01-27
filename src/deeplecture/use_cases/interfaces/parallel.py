"""Parallel execution protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, TypeVar

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class ParallelGroup:
    """Configuration for a parallel execution group."""

    name: str
    max_workers: int = 4
    timeout: float | None = None


class ParallelRunnerProtocol(Protocol):
    """Protocol for parallel execution."""

    def map_ordered(
        self,
        items: list[T],
        func: Callable[[T], R],
        *,
        group: str = "default",
        on_error: Callable[[Exception, T], R] | None = None,
    ) -> list[R]:
        """Map a function over items in parallel, preserving order.

        Args:
            items: Items to process.
            func: Function to apply to each item.
            group: Parallel group name for configuration.
            on_error: Optional error handler.

        Returns:
            Results in the same order as input items.
        """
        ...

    def configure_group(self, group: ParallelGroup) -> None:
        """Configure a parallel execution group.

        Args:
            group: Group configuration.
        """
        ...
