"""
DEPRECATED: This module has moved to use_cases.shared.prompt_safety.

Import from the new location instead:
    from deeplecture.use_cases.shared.prompt_safety import sanitize_user_input
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

_warned = False


def __getattr__(name: str) -> Any:
    """Lazy attribute access with deprecation warning."""
    global _warned
    if not _warned:
        warnings.warn(
            "deeplecture.infrastructure.shared.prompt_safety is deprecated. "
            "Import from deeplecture.use_cases.shared.prompt_safety instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        _warned = True

    from deeplecture.use_cases.shared import prompt_safety

    if hasattr(prompt_safety, name):
        return getattr(prompt_safety, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
