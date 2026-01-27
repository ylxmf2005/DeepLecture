"""Claude Code CLI gateway for fact verification.

Uses `claude -p` (print mode) to run non-interactive verification
with subagent WebSearch capabilities.

Logging: Claude Code execution logs are written to the standard Python
logging system under the 'deeplecture.claude_code' logger. Set log level
to DEBUG to see detailed step-by-step execution traces.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import threading
from typing import Any

logger = logging.getLogger(__name__)

# Separate logger for Claude Code execution traces (can be configured independently)
claude_trace_logger = logging.getLogger("deeplecture.claude_code.trace")


class ClaudeCodeError(Exception):
    """Error during Claude Code execution."""

    def __init__(self, message: str, stderr: str = "", exit_code: int = -1) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.exit_code = exit_code


class ClaudeCodeGateway:
    """Gateway for Claude Code CLI interaction.

    Executes `claude -p` in non-interactive mode with streaming JSON output,
    allowing subagents to perform WebSearch for fact verification.

    Execution logs are streamed to the 'deeplecture.claude_code.trace' logger.
    """

    def __init__(
        self,
        *,
        claude_path: str = "claude",
        default_timeout: int = 600,
        default_max_turns: int = 15,
        enable_trace_logging: bool = True,
    ) -> None:
        """
        Initialize ClaudeCodeGateway.

        Args:
            claude_path: Path to claude CLI binary
            default_timeout: Default timeout in seconds
            default_max_turns: Default max agentic turns
            enable_trace_logging: Whether to log execution traces
        """
        self._claude_path = claude_path
        self._default_timeout = default_timeout
        self._default_max_turns = default_max_turns
        self._enable_trace_logging = enable_trace_logging

    def run_verification(
        self,
        prompt: str,
        *,
        timeout: int | None = None,
        max_turns: int | None = None,
    ) -> dict[str, Any]:
        """
        Run fact verification using Claude Code CLI.

        Args:
            prompt: The verification prompt with subtitle context
            timeout: Maximum execution time in seconds
            max_turns: Maximum agentic turns for subagents

        Returns:
            Parsed JSON report from Claude Code

        Raises:
            ClaudeCodeError: If execution fails
            TimeoutError: If execution exceeds timeout
        """
        timeout = timeout or self._default_timeout
        max_turns = max_turns or self._default_max_turns

        # Use stream-json for real-time logging, fall back to json for parsing
        cmd = [
            self._claude_path,
            "-p",  # Print mode (non-interactive)
            "--verbose",  # Required for stream-json with --print
            "--output-format",
            "stream-json",  # Stream for logging
            "--max-turns",
            str(max_turns),
            "--allowedTools",
            "WebSearch,Task,Read,Bash",  # Enable tools in -p mode
            "--dangerously-skip-permissions",  # Skip permission prompts
            "-",  # Read prompt from stdin (avoids argv length limits)
        ]

        logger.info("Starting Claude Code verification (timeout=%ds, max_turns=%d)", timeout, max_turns)
        claude_trace_logger.info("=== Claude Code Verification Started ===")

        try:
            # Use start_new_session to enable killing entire process group
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )

            # Send prompt to stdin and close
            if proc.stdin:
                proc.stdin.write(prompt)
                proc.stdin.close()

            # Collect output while logging stream events
            stdout_lines: list[str] = []
            stderr_lines: list[str] = []

            # Read stderr in background thread
            def read_stderr():
                if proc.stderr:
                    for line in proc.stderr:
                        stderr_lines.append(line)
                        if line.strip():
                            claude_trace_logger.warning("[stderr] %s", line.rstrip())

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Read stdout line by line (stream-json outputs one JSON per line)
            try:
                if proc.stdout:
                    import select
                    import time

                    start_time = time.monotonic()
                    while True:
                        # Check timeout
                        elapsed = time.monotonic() - start_time
                        if elapsed > timeout:
                            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                            proc.wait(timeout=5)
                            raise TimeoutError(f"Claude Code verification timed out after {timeout}s")

                        # Non-blocking read with select
                        ready, _, _ = select.select([proc.stdout], [], [], 1.0)
                        if ready:
                            line = proc.stdout.readline()
                            if not line:
                                break  # EOF
                            stdout_lines.append(line)
                            self._log_stream_event(line)
                        elif proc.poll() is not None:
                            # Process ended, read remaining
                            for line in proc.stdout:
                                stdout_lines.append(line)
                                self._log_stream_event(line)
                            break

            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=5)
                raise TimeoutError(f"Claude Code verification timed out after {timeout}s") from None

            # Wait for process and stderr thread
            proc.wait()
            stderr_thread.join(timeout=2)

            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            if proc.returncode != 0:
                logger.error("Claude Code failed (exit=%d): %s", proc.returncode, stderr[:500])
                claude_trace_logger.error("=== Claude Code Failed (exit=%d) ===", proc.returncode)
                raise ClaudeCodeError(
                    f"Claude Code exited with code {proc.returncode}",
                    stderr=stderr,
                    exit_code=proc.returncode,
                )

            claude_trace_logger.info("=== Claude Code Verification Completed ===")
            return self._parse_stream_output(stdout)

        except FileNotFoundError as exc:
            raise ClaudeCodeError(
                f"Claude CLI not found at '{self._claude_path}'. Is it installed?",
                exit_code=-1,
            ) from exc

    def _log_stream_event(self, line: str) -> None:
        """Log a single stream-json event."""
        if not self._enable_trace_logging:
            return

        line = line.strip()
        if not line:
            return

        try:
            event = json.loads(line)
            event_type = event.get("type", "unknown")

            if event_type == "assistant":
                # Claude's response text
                message = event.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "")[:200]  # Truncate for logging
                        claude_trace_logger.debug("[assistant] %s...", text)
                    elif block.get("type") == "tool_use":
                        tool_name = block.get("name", "unknown")
                        claude_trace_logger.info("[tool_call] %s", tool_name)

            elif event_type == "user":
                # Tool results
                message = event.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id", "?")[:8]
                        is_error = block.get("is_error", False)
                        if is_error:
                            claude_trace_logger.warning("[tool_error] %s", tool_id)
                        else:
                            claude_trace_logger.debug("[tool_result] %s", tool_id)

            elif event_type == "result":
                # Final result
                cost = event.get("cost_usd", 0)
                duration = event.get("duration_ms", 0) / 1000
                claude_trace_logger.info("[complete] cost=$%.4f, duration=%.1fs", cost, duration)

            elif event_type == "error":
                error_msg = event.get("error", {}).get("message", "unknown error")
                claude_trace_logger.error("[error] %s", error_msg)

            elif event_type == "system":
                # System messages (often subagent info)
                subtype = event.get("subtype", "")
                if subtype:
                    claude_trace_logger.debug("[system:%s]", subtype)

        except json.JSONDecodeError:
            # Non-JSON line (shouldn't happen with stream-json)
            if line:
                claude_trace_logger.debug("[raw] %s", line[:100])

    def _parse_stream_output(self, stdout: str) -> dict[str, Any]:
        """Parse stream-json output to extract final result."""
        if not stdout.strip():
            raise ClaudeCodeError("Claude Code returned empty output")

        # Stream-json outputs one JSON object per line
        # Find the "result" type event which contains the final output
        result_event = None
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "result":
                    result_event = event
                    break
            except json.JSONDecodeError:
                continue

        if not result_event:
            # Fall back to parsing as single JSON (legacy format)
            return self._parse_output(stdout)

        # Extract result from the result event
        result_str = result_event.get("result", "")
        if isinstance(result_str, dict):
            if "claims" in result_str:
                return result_str
        elif isinstance(result_str, str):
            # Try direct JSON parse
            try:
                parsed = json.loads(result_str)
                if isinstance(parsed, dict) and "claims" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

            # Extract from markdown
            extracted = self._extract_json_from_markdown(result_str)
            if extracted:
                return extracted

        raise ClaudeCodeError("Could not extract verification report from Claude stream output")

    def _parse_output(self, stdout: str) -> dict[str, Any]:
        """Parse Claude Code JSON output (legacy single-JSON format)."""
        if not stdout.strip():
            raise ClaudeCodeError("Claude Code returned empty output")

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse direct JSON, attempting extraction: %s", exc)
            raise ClaudeCodeError(f"Failed to parse Claude output as JSON: {exc}") from exc

        # Extract result from Claude's JSON wrapper if present
        if isinstance(data, dict):
            # Claude Code JSON format: {"type": "result", "result": "...", ...}
            if "result" in data:
                result_str = data["result"]
                if isinstance(result_str, dict):
                    # Result is already a dict
                    if "claims" in result_str:
                        return result_str
                elif isinstance(result_str, str):
                    # Try direct JSON parse first
                    try:
                        parsed = json.loads(result_str)
                        if isinstance(parsed, dict) and "claims" in parsed:
                            return parsed
                    except json.JSONDecodeError:
                        pass

                    # Extract JSON from markdown code block (```json ... ```)
                    extracted = self._extract_json_from_markdown(result_str)
                    if extracted:
                        return extracted

            # If data already looks like a report, return it
            if "claims" in data or "report_id" in data:
                return data

        raise ClaudeCodeError("Could not extract verification report from Claude output")

    @staticmethod
    def _extract_json_from_markdown(text: str) -> dict[str, Any] | None:
        """Extract JSON object from markdown code blocks."""
        import re

        # Pattern 1: ```json ... ``` block
        json_block = re.search(r"```(?:json)?\s*\n?({[\s\S]*?})\s*\n?```", text)
        if json_block:
            try:
                parsed = json.loads(json_block.group(1))
                if isinstance(parsed, dict) and "claims" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        # Pattern 2: Raw JSON object starting with {"claims"
        raw_json = re.search(r'(\{"claims"[\s\S]*?\})\s*(?:$|[^}])', text)
        if raw_json:
            # Try progressively longer matches for nested JSON
            start = raw_json.start(1)
            for end in range(len(text), start, -1):
                candidate = text[start:end]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict) and "claims" in parsed:
                        return parsed
                except json.JSONDecodeError:
                    continue

        return None
