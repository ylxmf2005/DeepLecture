"""Parallel execution protocol for the Use Cases layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

T = TypeVar("T")
R = TypeVar("R")

ParallelGroup = Literal[
    "subtitle_batches",
    "timeline_units",
    "note_parts",
    "voiceover_tts",
]


class ParallelRunnerProtocol(Protocol):
    """
    Contract for parallel execution.

    Use Cases depend on this protocol to run CPU/IO-bound fan-out work
    without directly owning concurrency configuration.
    """

    def map_ordered(
        self,
        items: Sequence[T],
        fn: Callable[[T], R],
        *,
        group: ParallelGroup,
        on_error: Callable[[Exception, T], R] | None = None,
    ) -> list[R]:
        """
        Apply `fn` to each item, preserving input order.

        Args:
            items: Input items.
            fn: Function applied to each item.
            group: Named execution group (maps to infra parallelism limits).
            on_error: Optional fallback for per-item failures. If omitted,
                the first exception aborts the whole call.

        Returns:
            List of results in the same order as `items`.
        """
        ...
