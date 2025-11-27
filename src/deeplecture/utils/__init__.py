"""
Common utilities shared across service and feature modules.

Keep this package free of heavy dependencies so it can be imported
from low-level layers without creating cycles.
"""

__all__ = ["streaming", "fs"]
