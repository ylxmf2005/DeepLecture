from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

try:
    import json_repair
except ImportError:  # pragma: no cover - fallback to std json
    import json as _json

    class _JsonRepair:
        @staticmethod
        def load(file_obj):
            return _json.load(file_obj)

    json_repair = _JsonRepair()

UTC = getattr(datetime, "UTC", timezone.utc)


def _serialize_timeline_entries(entries: Iterable[Any]) -> Iterable[Dict[str, Any]]:
    """
    Convert timeline entries to plain dicts. Accepts either objects with a
    to_dict() method or raw dicts.
    """
    serialized = []
    for item in entries or []:
        if hasattr(item, "to_dict"):
            serialized.append(item.to_dict())
        else:
            serialized.append(item)
    return serialized


def save_timeline_to_file(
    entries: Iterable[Any],
    *,
    video_id: str,
    language: str,
    output_dir: str,
    learner_profile: Optional[str] = None,
    status: str = "ready",
    error: Optional[str] = None,
) -> str:
    """
    Persist timeline entries to a JSON file for later reuse.

    Returns:
        Absolute path to the JSON file on disk.
    """
    os.makedirs(output_dir, exist_ok=True)

    payload: Dict[str, Any] = {
        "video_id": video_id,
        "language": language,
        "learner_profile": learner_profile or "",
        "generated_at": datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
        "status": status,
        "timeline": list(_serialize_timeline_entries(entries)),
    }

    if error:
        payload["error"] = error

    filename = f"timeline_{language}.json"
    json_path = os.path.join(output_dir, filename)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return json_path


def load_timeline_from_file(json_path: str) -> Optional[Dict[str, Any]]:
    """Load previously saved timeline data if the file exists."""
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            # Use json_repair to be resilient to partially written/corrupted files
            return json_repair.load(f)
    except Exception as exc:  # pragma: no cover - best-effort load
        logger.error("Failed to read timeline file %s: %s", json_path, exc)
        return None
