from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from deeplecture.app_context import AppContext, get_app_context
from deeplecture.dto.storage import ContentMetadata

try:
    import json_repair
except ImportError:
    json_repair = None


logger = logging.getLogger(__name__)
UTC = getattr(datetime, "UTC", timezone.utc)

# Feature status type
FeatureStatus = Literal["none", "processing", "ready", "error"]

# Feature names for status updates
FeatureName = Literal["video", "subtitle", "translation", "enhanced", "timeline", "notes"]


def _migrate_legacy_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate legacy metadata format to new feature-based status model.

    Legacy format:
        status: "ready" | "processing"
        has_subtitles: bool
        has_translation: bool
        has_enhanced_subtitles: bool
        processing_job_id: str

    New format:
        video_status: "none" | "processing" | "ready" | "error"
        subtitle_status: "none" | "processing" | "ready" | "error"
        translation_status: "none" | "processing" | "ready" | "error"
        enhanced_status: "none" | "processing" | "ready" | "error"
        timeline_status: "none" | "processing" | "ready" | "error"
        notes_status: "none" | "processing" | "ready" | "error"
        {feature}_job_id: str | None
    """
    # Check if already migrated (has new status fields)
    if "video_status" in data:
        # Remove legacy fields if present
        for legacy_field in ["status", "processing_job_id", "has_subtitles", "has_translation", "has_enhanced_subtitles"]:
            data.pop(legacy_field, None)
        return data

    # Migrate video status
    legacy_status = data.pop("status", None)
    video_file = data.get("video_file")
    if video_file:
        if legacy_status == "processing":
            data["video_status"] = "processing"
        else:
            data["video_status"] = "ready"
    else:
        if legacy_status == "processing":
            data["video_status"] = "processing"
        else:
            data["video_status"] = "none"

    # Migrate subtitle status
    has_subtitles = data.pop("has_subtitles", None)
    if has_subtitles or data.get("subtitle_path"):
        data["subtitle_status"] = "ready"
    else:
        data["subtitle_status"] = "none"

    # Migrate translation status
    has_translation = data.pop("has_translation", None)
    if has_translation or data.get("translated_subtitle_path"):
        data["translation_status"] = "ready"
    else:
        data["translation_status"] = "none"

    # Migrate enhanced status
    has_enhanced = data.pop("has_enhanced_subtitles", None)
    if has_enhanced or data.get("enhanced_subtitle_path"):
        data["enhanced_status"] = "ready"
    else:
        data["enhanced_status"] = "none"

    # Migrate timeline status
    if data.get("timeline_path"):
        data["timeline_status"] = "ready"
    else:
        data["timeline_status"] = "none"

    # Migrate notes status
    if data.get("notes_path"):
        data["notes_status"] = "ready"
    else:
        data["notes_status"] = "none"

    # Remove legacy processing_job_id
    data.pop("processing_job_id", None)

    logger.info("Migrated legacy metadata for content %s", data.get("id"))

    return data


class MetadataStorage:
    """
    Storage abstraction for content metadata.

    New structure: data/content/{content_id}/metadata.json
    """

    def __init__(
        self,
        *,
        app_context: Optional[AppContext] = None,
        metadata_folder: Optional[str] = None,
    ) -> None:
        if metadata_folder:
            self._content_dir = metadata_folder
            os.makedirs(self._content_dir, exist_ok=True)
        else:
            ctx = app_context or get_app_context()
            ctx.init_paths()
            self._content_dir = ctx.content_dir

    def _get_metadata_path(self, content_id: str) -> str:
        """Get the metadata file path: data/content/{content_id}/metadata.json"""
        content_path = os.path.join(self._content_dir, content_id)
        os.makedirs(content_path, exist_ok=True)
        return os.path.join(content_path, "metadata.json")

    def metadata_path(self, content_id: str) -> str:
        return self._get_metadata_path(content_id)

    def save(self, metadata: ContentMetadata) -> None:
        path = self._get_metadata_path(metadata.id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info("Saved metadata for content %s", metadata.id)
        except Exception as exc:
            logger.error("Failed to save metadata for %s: %s", metadata.id, exc)
            raise

    def get(self, content_id: str) -> Optional[ContentMetadata]:
        path = self._get_metadata_path(content_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                if json_repair:
                    data = json_repair.load(f)
                else:
                    data = json.load(f)

            # Migrate legacy format if needed
            data = _migrate_legacy_metadata(data)

            return ContentMetadata.from_dict(data)
        except Exception as exc:
            logger.error("Failed to load metadata for %s: %s", content_id, exc)
            return None

    def exists(self, content_id: str) -> bool:
        return os.path.exists(self._get_metadata_path(content_id))

    def delete(self, content_id: str) -> bool:
        path = self._get_metadata_path(content_id)
        if not os.path.exists(path):
            return False

        try:
            os.remove(path)
            logger.info("Deleted metadata for content %s", content_id)
            return True
        except Exception as exc:
            logger.error("Failed to delete metadata for %s: %s", content_id, exc)
            return False

    def list_all(self) -> List[ContentMetadata]:
        """List all content metadata, sorted by created_at descending."""
        if not os.path.exists(self._content_dir):
            return []

        metadata_list: List[ContentMetadata] = []
        try:
            for content_id in os.listdir(self._content_dir):
                content_path = os.path.join(self._content_dir, content_id)
                if not os.path.isdir(content_path):
                    continue

                metadata = self.get(content_id)
                if metadata:
                    metadata_list.append(metadata)
        except Exception as exc:
            logger.error("Failed to list metadata: %s", exc)

        metadata_list.sort(key=lambda m: m.created_at, reverse=True)
        return metadata_list

    def update_feature_status(
        self,
        content_id: str,
        feature: FeatureName,
        status: FeatureStatus,
        job_id: Optional[str] = None,
    ) -> bool:
        """
        Update the status of a specific feature.

        Args:
            content_id: The content ID
            feature: The feature name (video, subtitle, translation, etc.)
            status: The new status (none, processing, ready, error)
            job_id: Optional job ID for processing tasks

        Returns:
            True if update succeeded, False otherwise
        """
        metadata = self.get(content_id)
        if not metadata:
            return False

        status_attr = f"{feature}_status"
        job_attr = f"{feature}_job_id"

        setattr(metadata, status_attr, status)
        setattr(metadata, job_attr, job_id)
        metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()

        self.save(metadata)
        return True

    def update_video_file(self, content_id: str, video_file: str) -> bool:
        metadata = self.get(content_id)
        if not metadata:
            return False

        metadata.video_file = video_file
        metadata.video_status = "ready"
        metadata.video_job_id = None
        metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
        self.save(metadata)
        return True

    def update_subtitles(
        self,
        content_id: str,
        subtitle_path: Optional[str] = None,
        translated_path: Optional[str] = None,
        enhanced_path: Optional[str] = None,
    ) -> bool:
        metadata = self.get(content_id)
        if not metadata:
            return False

        if subtitle_path:
            metadata.subtitle_path = subtitle_path
            metadata.subtitle_status = "ready"
            metadata.subtitle_job_id = None

        if translated_path:
            metadata.translated_subtitle_path = translated_path
            metadata.translation_status = "ready"
            metadata.translation_job_id = None

        if enhanced_path:
            metadata.enhanced_subtitle_path = enhanced_path
            metadata.enhanced_status = "ready"
            metadata.enhanced_job_id = None

        metadata.updated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()
        self.save(metadata)
        return True


def get_default_metadata_storage() -> MetadataStorage:
    return MetadataStorage()
