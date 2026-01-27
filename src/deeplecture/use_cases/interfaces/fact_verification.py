"""Fact verification protocols."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class FactVerificationStorageProtocol(Protocol):
    """Protocol for fact verification results persistence."""

    def load(self, content_id: str) -> dict | None:
        """Load verification results.

        Args:
            content_id: Content identifier.

        Returns:
            Verification results if exists, None otherwise.
        """
        ...

    def save(self, content_id: str, results: dict) -> datetime:
        """Save verification results.

        Args:
            content_id: Content identifier.
            results: Verification results.

        Returns:
            Timestamp when saved.
        """
        ...


class ClaudeCodeProtocol(Protocol):
    """Protocol for Claude Code external process execution."""

    def run(
        self,
        prompt: str,
        *,
        working_dir: str | None = None,
        timeout: float = 300.0,
    ) -> str:
        """Run Claude Code with a prompt.

        Args:
            prompt: Prompt to execute.
            working_dir: Optional working directory.
            timeout: Timeout in seconds.

        Returns:
            Claude Code output.
        """
        ...
