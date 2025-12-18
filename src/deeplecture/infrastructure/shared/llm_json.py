"""
DEPRECATED: This module has moved to use_cases.shared.llm_json.

Import from the new location instead:
    from deeplecture.use_cases.shared.llm_json import parse_llm_json
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Lazy re-export with deprecation warning on access
_warned = False


def __getattr__(name: str) -> Any:
    """Lazy attribute access with deprecation warning."""
    global _warned
    if not _warned:
        warnings.warn(
            "deeplecture.infrastructure.shared.llm_json is deprecated. "
            "Import from deeplecture.use_cases.shared.llm_json instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        _warned = True

    from deeplecture.use_cases.shared import llm_json

    if hasattr(llm_json, name):
        return getattr(llm_json, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
