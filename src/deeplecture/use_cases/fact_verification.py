"""Fact verification use case.

Orchestrates:
- Subtitle context loading
- Claude Code CLI invocation for claim extraction and verification
- Report storage and retrieval
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from deeplecture.domain.errors import ContentNotFoundError
from deeplecture.use_cases.dto.fact_verification import (
    Claim,
    Evidence,
    VerificationReport,
)
from deeplecture.use_cases.shared.subtitle import (
    load_first_available_subtitle_segments,
    prioritize_subtitle_languages,
)

if TYPE_CHECKING:
    from deeplecture.use_cases.dto.fact_verification import GenerateVerificationRequest
    from deeplecture.use_cases.interfaces import MetadataStorageProtocol, SubtitleStorageProtocol
    from deeplecture.use_cases.interfaces.fact_verification import (
        ClaudeCodeProtocol,
        FactVerificationStorageProtocol,
    )

logger = logging.getLogger(__name__)
UTC = timezone.utc

# Maximum subtitle characters to send to Claude Code
MAX_SUBTITLE_CHARS = 100_000

# Valid verdicts (allowlist)
VALID_VERDICTS = frozenset({"supported", "disputed", "unverifiable", "context_missing"})
DEFAULT_VERDICT = "unverifiable"

# Valid URL schemes for evidence links
VALID_URL_SCHEMES = frozenset({"http", "https"})


class FactVerificationUseCase:
    """
    Fact verification using Claude Code CLI.

    Orchestrates:
    - Loading subtitles as context
    - Building verification prompt
    - Calling Claude Code with WebSearch-enabled subagents
    - Parsing and storing verification reports
    """

    def __init__(
        self,
        *,
        metadata_storage: MetadataStorageProtocol,
        subtitle_storage: SubtitleStorageProtocol,
        verification_storage: FactVerificationStorageProtocol,
        claude_code: ClaudeCodeProtocol,
    ) -> None:
        self._metadata = metadata_storage
        self._subtitles = subtitle_storage
        self._storage = verification_storage
        self._claude = claude_code

    def get_report(self, content_id: str, language: str) -> VerificationReport | None:
        """Get existing verification report."""
        return self._storage.load(content_id, language)

    def generate_report(self, request: GenerateVerificationRequest) -> VerificationReport:
        """
        Generate fact verification report using Claude Code.

        Args:
            request: Generation request with content_id and language

        Returns:
            VerificationReport with verified claims

        Raises:
            ContentNotFoundError: Content not found
            ValueError: No subtitles available
            RuntimeError: Claude Code execution failed
        """
        # 1. Validate content exists
        metadata = self._metadata.get(request.content_id)
        if metadata is None:
            raise ContentNotFoundError(request.content_id)

        # 2. Load subtitle context
        subtitle_text = self._load_subtitle_context(request.content_id)
        if not subtitle_text:
            raise ValueError(
                "Cannot generate verification: no subtitles available. " "Please generate subtitles first."
            )

        # 3. Build prompt for Claude Code
        prompt = self._build_prompt(subtitle_text, request.language)

        # 4. Run Claude Code verification
        logger.info("Starting fact verification for content_id=%s", request.content_id)
        raw_result = self._claude.run_verification(prompt)

        # 5. Parse result into report
        report = self._parse_result(
            raw_result,
            content_id=request.content_id,
            language=request.language,
        )

        # 6. Save report
        self._storage.save(report)
        logger.info("Saved verification report: %s claims", len(report.claims))

        return report

    def _load_subtitle_context(self, content_id: str) -> str:
        """Load subtitle text with timestamps for context."""
        candidate_languages = prioritize_subtitle_languages(self._subtitles.list_languages(content_id))

        loaded = load_first_available_subtitle_segments(
            self._subtitles,
            content_id=content_id,
            candidate_languages=candidate_languages,
        )

        if not loaded:
            return ""

        _lang, segments = loaded

        # Format with timestamps: [segment_id] [start-end] text
        lines = []
        for i, seg in enumerate(segments, start=1):
            text = seg.text.replace("\n", " ").strip()
            if text:
                lines.append(f"[{i}] [{seg.start:.1f}-{seg.end:.1f}] {text}")

        result = "\n".join(lines)

        # Truncate if too long
        if len(result) > MAX_SUBTITLE_CHARS:
            result = result[:MAX_SUBTITLE_CHARS] + "\n[... truncated ...]"
            logger.warning("Subtitle context truncated to %d chars", MAX_SUBTITLE_CHARS)

        return result

    def _build_prompt(self, subtitle_text: str, language: str) -> str:
        """Build the verification prompt for Claude Code."""
        return f"""TASK: Fact-check video lecture content. Execute immediately.

PHASE 1 - EXTRACT CLAIMS:
Analyze the subtitles and extract all verifiable factual claims (scientific facts, statistics, historical events, technical specifications). Skip opinions and subjective statements.

For each claim, note:
- The exact factual statement
- The timestamp range from subtitle markers [n] [start-end]

PHASE 2 - VERIFY EACH CLAIM:
For EACH extracted claim, use WebSearch to find authoritative sources that support or refute it.

For each claim, determine:
- verdict: "supported" (evidence confirms), "disputed" (evidence contradicts), "unverifiable" (insufficient evidence), or "context_missing" (claim lacks context)
- confidence: 0.0 to 1.0 based on source quality and consensus
- evidence: list of sources found

PHASE 3 - OUTPUT JSON:
Return ONLY a valid JSON object in this EXACT format (no markdown, no explanation):

{{
  "claims": [
    {{
      "claim_id": "c1",
      "text": "exact claim text",
      "start": 0.0,
      "end": 5.0,
      "verdict": "supported",
      "confidence": 0.85,
      "evidence": [
        {{
          "url": "https://example.com/source",
          "title": "Source Article Title",
          "publisher": "Publisher Name",
          "quote": "Relevant quote from source"
        }}
      ],
      "notes": "Brief explanation of verification result"
    }}
  ],
  "summary": "Overall assessment in {language}"
}}

IMPORTANT:
- evidence MUST be an array of objects with url, title, publisher, quote fields
- All text fields (summary, notes) MUST be in {language}
- Output ONLY the JSON object, nothing else

SUBTITLE CONTENT (format: [segment_id] [start-end] text):
{subtitle_text}

BEGIN VERIFICATION:"""

    def _parse_result(
        self,
        raw: dict,
        content_id: str,
        language: str,
    ) -> VerificationReport:
        """Parse Claude Code output into VerificationReport."""
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        claims = []
        for c in raw.get("claims", []):
            evidence = []
            for e in c.get("evidence", []):
                # Handle both dict format and plain string URL
                if isinstance(e, str):
                    url = self._validate_url(e)
                    if url:
                        evidence.append(Evidence(
                            url=url,
                            title="",
                            publisher="",
                            quote="",
                            retrieved_at=now.isoformat(),
                        ))
                elif isinstance(e, dict):
                    url = self._validate_url(e.get("url", ""))
                    if url:
                        evidence.append(Evidence(
                            url=url,
                            title=str(e.get("title", ""))[:500],
                            publisher=str(e.get("publisher", ""))[:200],
                            quote=str(e.get("quote", ""))[:2000],
                            retrieved_at=e.get("retrieved_at", now.isoformat()),
                        ))

            claims.append(
                Claim(
                    claim_id=c.get("claim_id", f"c{len(claims)+1}"),
                    text=str(c.get("text", ""))[:2000],
                    start=self._clamp_float(c.get("start"), 0, float("inf"), 0),
                    end=self._clamp_float(c.get("end"), 0, float("inf"), 0),
                    verdict=self._validate_verdict(c.get("verdict")),
                    confidence=self._clamp_float(c.get("confidence"), 0, 1, 0.5),
                    evidence=evidence,
                    notes=str(c.get("notes", ""))[:5000],
                )
            )

        return VerificationReport(
            report_id=report_id,
            content_id=content_id,
            language=language,
            created_at=now,
            claims=claims,
            summary=str(raw.get("summary", ""))[:5000],
        )

    @staticmethod
    def _validate_verdict(verdict: str | None) -> str:
        """Validate verdict against allowlist, fallback to default."""
        if verdict and verdict in VALID_VERDICTS:
            return verdict
        return DEFAULT_VERDICT

    @staticmethod
    def _clamp_float(value: float | str | None, min_val: float, max_val: float, default: float) -> float:
        """Safely parse and clamp a float value."""
        try:
            result = float(value) if value is not None else default
            return max(min_val, min(max_val, result))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _validate_url(url: str | None) -> str:
        """Validate URL scheme, return empty string if invalid."""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if parsed.scheme in VALID_URL_SCHEMES:
                return url
        except Exception:
            pass
        return ""
