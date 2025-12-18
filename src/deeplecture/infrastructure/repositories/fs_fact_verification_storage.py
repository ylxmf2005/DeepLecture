"""Filesystem implementation of FactVerificationStorageProtocol.

Stores a single JSON report per content/language combination at:
    content/{content_id}/fact_verification/{language}.json
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from deeplecture.infrastructure.repositories.path_resolver import validate_segment
from deeplecture.use_cases.dto.fact_verification import Claim, Evidence, VerificationReport

if TYPE_CHECKING:
    from deeplecture.use_cases.interfaces import PathResolverProtocol

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FsFactVerificationStorage:
    """Filesystem-backed fact verification report storage."""

    def __init__(self, path_resolver: PathResolverProtocol) -> None:
        self._paths = path_resolver

    def _get_report_path(self, content_id: str, language: str) -> Path:
        """Get the path for a verification report."""
        validate_segment(content_id, "content_id")
        validate_segment(language, "language")
        base = self._paths.ensure_content_dir(content_id, "fact_verification")
        return Path(base) / f"{language}.json"

    def load(self, content_id: str, language: str) -> VerificationReport | None:
        """Load the latest verification report."""
        path = self._get_report_path(content_id, language)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load verification report %s: %s", path, exc)
            return None

        return self._parse_report(data)

    def save(self, report: VerificationReport) -> None:
        """Save verification report (atomic write)."""
        path = self._get_report_path(report.content_id, report.language)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = report.to_dict()
        tmp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                suffix=".tmp",
                delete=False,
            ) as f:
                tmp_path = f.name
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path))
            logger.info("Saved verification report: %s", path)
        except Exception:
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)
            raise

    def exists(self, content_id: str, language: str) -> bool:
        """Check if verification report exists."""
        return self._get_report_path(content_id, language).exists()

    @staticmethod
    def _parse_report(data: dict) -> VerificationReport:
        """Parse raw JSON into VerificationReport."""
        claims = []
        for c in data.get("claims", []):
            evidence = [
                Evidence(
                    url=e.get("url", ""),
                    title=e.get("title", ""),
                    publisher=e.get("publisher", ""),
                    quote=e.get("quote", ""),
                    retrieved_at=e.get("retrieved_at", ""),
                )
                for e in c.get("evidence", [])
            ]
            claims.append(
                Claim(
                    claim_id=c.get("claim_id", ""),
                    text=c.get("text", ""),
                    start=float(c.get("start", 0)),
                    end=float(c.get("end", 0)),
                    verdict=c.get("verdict", "unverifiable"),
                    confidence=float(c.get("confidence", 0)),
                    evidence=evidence,
                    notes=c.get("notes", ""),
                )
            )

        created_at_str = data.get("created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.now(UTC)

        return VerificationReport(
            report_id=data.get("report_id", ""),
            content_id=data.get("content_id", ""),
            language=data.get("language", ""),
            created_at=created_at,
            claims=claims,
            summary=data.get("summary", ""),
        )
