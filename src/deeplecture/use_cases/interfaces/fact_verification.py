"""Fact verification protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.fact_verification import VerificationReport


class FactVerificationStorageProtocol(Protocol):
    """Contract for fact verification report storage."""

    def load(self, content_id: str, language: str) -> VerificationReport | None:
        """
        Load the latest verification report.

        Args:
            content_id: Content identifier
            language: Language code

        Returns:
            VerificationReport if exists, None otherwise
        """
        ...

    def save(self, report: VerificationReport) -> None:
        """
        Save verification report (overwrites existing).

        Args:
            report: Report to save
        """
        ...

    def exists(self, content_id: str, language: str) -> bool:
        """
        Check if verification report exists.

        Args:
            content_id: Content identifier
            language: Language code

        Returns:
            True if report exists
        """
        ...


class ClaudeCodeProtocol(Protocol):
    """Contract for Claude Code CLI interaction."""

    def run_verification(
        self,
        prompt: str,
        *,
        timeout: int = 600,
        max_turns: int = 15,
    ) -> dict:
        """
        Run fact verification using Claude Code CLI.

        Args:
            prompt: The verification prompt with subtitle context
            timeout: Maximum execution time in seconds
            max_turns: Maximum agentic turns for subagents

        Returns:
            Parsed JSON report from Claude Code

        Raises:
            RuntimeError: If Claude Code execution fails
            TimeoutError: If execution exceeds timeout
        """
        ...
