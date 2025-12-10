from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import json
import json_repair
import logging
from flask import Flask, jsonify, request, send_file

from deeplecture.config.config import load_config
import mimetypes
from deeplecture.workers import TaskManager
from deeplecture.services.content_service import ContentService
from deeplecture.api.error_utils import api_error

logger = logging.getLogger(__name__)


def register_voiceover_routes(
    app: Flask,
    content_service: ContentService,
    task_manager: TaskManager | None = None,
) -> None:
    """
    Register voiceover-related routes (TTS dubbing and playback).
    """

    def _resolve_video_path(video_id: str) -> Optional[str]:
        return content_service.get_video_path(video_id)

    def _resolve_original_subtitle_path(video_id: str) -> Optional[str]:
        # Prefer enhanced subtitles when available; fall back to original.
        path = content_service.get_enhanced_subtitle_path(video_id)
        if path and os.path.exists(path):
            return path

        path = content_service.get_subtitle_path(video_id)
        if path and os.path.exists(path):
            return path

        return None

    def _resolve_translated_subtitle_path(
        video_id: str,
        language: Optional[str],
    ) -> Optional[str]:
        path = content_service.get_translated_subtitle_path(video_id)
        if path and os.path.exists(path):
            return path

        logger.warning(
            "Translated subtitles not found for voiceover: content_id=%s language=%s",
            video_id,
            language,
        )
        return None

    def _get_default_voiceover_language() -> str:
        """
        Resolve the default voiceover language, mirroring subtitle translation target.
        """
        try:
            config = load_config()
            subtitle_cfg = (config or {}).get("subtitle") or {}
            translation_cfg = subtitle_cfg.get("translation") or {}
            value = translation_cfg.get("target_language", "zh")
            return str(value)
        except Exception:
            return "zh"

    # RESTful routes
    @app.route("/api/content/<content_id>/voiceovers", methods=["GET", "POST"])
    @app.route("/api/voiceovers", methods=["GET", "POST"])
    def voiceovers_collection(content_id: str | None = None):
        """
        RESTful endpoint for voiceovers collection.
        GET: List all voiceovers for a video
        POST: Create a new voiceover
        """
        if request.method == "GET":
            video_id = content_id or request.args.get("video_id")
            if not video_id:
                return jsonify({"error": "Missing video_id"}), 400

            try:
                voiceover_dir = content_service.build_content_path(video_id, "voiceover")
                meta_path = os.path.join(voiceover_dir, "voiceovers.json")

                if not os.path.exists(meta_path):
                    return jsonify({"voiceovers": []})

                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json_repair.load(f)

                voiceovers = meta.get("voiceovers") or []

                return jsonify({"voiceovers": voiceovers})
            except Exception as e:
                return api_error(500, "Failed to list voiceovers", logger=logger, exc=e)

        # POST - Create voiceover
        try:
            data = request.json or {}
            video_id = content_id or data.get("video_id")
            subtitle_path = data.get("subtitle_path")
            subtitle_source = data.get("subtitle_source")  # "original" or "translated"
            raw_language = data.get("language")
            language = (
                str(raw_language)
                if raw_language
                else _get_default_voiceover_language()
            )
            voiceover_name = data.get("voiceover_name")

            if not video_id:
                return jsonify({"error": "Missing video_id"}), 400

            video_id = str(video_id)

            if not subtitle_path and not subtitle_source:
                return jsonify(
                    {"error": "Either subtitle_path or subtitle_source is required"},
                ), 400

            if not voiceover_name or not str(voiceover_name).strip():
                return jsonify({"error": "voiceover_name is required"}), 400

            video_path = _resolve_video_path(video_id)
            if not video_path:
                return jsonify(
                    {"error": f"Video file for ID {video_id} not found"},
                ), 404

            if not subtitle_path and subtitle_source:
                subtitle_source = str(subtitle_source).lower()
                if subtitle_source == "original":
                    subtitle_path = _resolve_original_subtitle_path(video_id)
                elif subtitle_source == "translated":
                    subtitle_path = _resolve_translated_subtitle_path(
                        video_id,
                        language,
                    )
                else:
                    return jsonify(
                        {"error": f"Unknown subtitle_source: {subtitle_source}"},
                    ), 400

            if not subtitle_path:
                return jsonify(
                    {
                        "error": "Subtitle file could not be resolved for the requested source",
                    },
                ), 404

            if not os.path.exists(subtitle_path):
                return jsonify(
                    {"error": f"Subtitle file not found: {subtitle_path}"},
                ), 404

            voiceover_dir = content_service.ensure_content_dir(video_id, "voiceover")
            meta_path = os.path.join(voiceover_dir, "voiceovers.json")

            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json_repair.load(f)
                except Exception:
                    meta = {}
            else:
                meta = {}

            voiceovers = meta.get("voiceovers") or []

            name_str = str(voiceover_name).strip()
            for item in voiceovers:
                if item.get("name") == name_str:
                    return jsonify(
                        {
                            "error": f"Voiceover name '{name_str}' already exists for this video",
                        },
                    ), 400

            safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name_str).strip("_") or "voiceover"
            base_filename = f"{safe_name}_{language}"

            voiceover_id = str(uuid.uuid4())

            voiceover_audio_path = os.path.join(voiceover_dir, f"{base_filename}.m4a")
            dubbed_video_path = os.path.join(voiceover_dir, f"{base_filename}.mp4")

            content_service.register_artifact(
                video_id,
                voiceover_audio_path,
                kind="voiceover:audio",
                media_type="audio/mp4",
            )
            content_service.register_artifact(
                video_id,
                dubbed_video_path,
                kind="voiceover:dubbed_video",
                media_type="video/mp4",
            )

            entry: Dict[str, Any] = {
                "id": voiceover_id,
                "name": name_str,
                "language": language,
                "subtitle_source": subtitle_source or "path",
                "subtitle_path": subtitle_path,
                "voiceover_audio_path": voiceover_audio_path,
                "dubbed_video_path": dubbed_video_path,
                "created_at": datetime.now().isoformat(),
                "status": "processing",
                "error": None,
            }
            voiceovers.append(entry)

            meta["video_id"] = video_id
            meta["voiceovers"] = voiceovers

            try:
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
            except Exception as exc:
                logger.error("Failed to update voiceover metadata for %s: %s", video_id, exc)
            else:
                content_service.register_artifact(
                    video_id,
                    meta_path,
                    kind="voiceover:manifest",
                    media_type="application/json",
                )

            if task_manager is None:
                return jsonify({"error": "Task manager not configured"}), 500

            task_id = task_manager.submit_task(
                video_id,
                "voiceover_generation",
                metadata={
                    "video_id": video_id,
                    "voiceover_id": voiceover_id,
                    "subtitle_path": subtitle_path,
                    "language": language,
                    "voiceover_audio_path": voiceover_audio_path,
                    "dubbed_video_path": dubbed_video_path,
                    "meta_path": meta_path,
                    "voiceover_name": name_str,
                    "audio_basename": base_filename,
                    "subtitle_source": subtitle_source or "path",
                },
            )

            return jsonify(
                {
                    "voiceover": entry,
                    "message": "Voiceover generation started",
                    "task_id": task_id,
                },
            )

        except ImportError as e:
            return api_error(500, "TTS dependency error", logger=logger, exc=e)
        except Exception as e:
            return api_error(500, "Voiceover generation failed", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/voiceovers/<voiceover_id>/video", methods=["GET"])
    @app.route("/api/voiceovers/<voiceover_id>/video", methods=["GET"])
    @app.route("/api/get-voiceover-video", methods=["GET"])  # backward-compatible shim
    def voiceover_video_resource(voiceover_id: str, content_id: str | None = None):
        """
        RESTful endpoint for voiceover video resource.
        Stream a generated voiceover (dubbed) video file for a specific voiceover ID.
        """
        # Allow legacy query-param based route for compatibility
        if request.path.endswith("/get-voiceover-video"):
            voiceover_id = request.args.get("voiceover_id", voiceover_id)
            content_id = request.args.get("video_id", content_id)

        video_id = content_id or request.args.get("video_id")
        if not video_id:
            return jsonify({"error": "Missing video_id"}), 400

        try:
            voiceover_dir = content_service.build_content_path(video_id, "voiceover")
            meta_path = os.path.join(voiceover_dir, "voiceovers.json")
            if not os.path.exists(meta_path):
                return jsonify({"error": "No voiceovers found for this video"}), 404

            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json_repair.load(f)

            entry = None
            for item in meta.get("voiceovers") or []:
                if item.get("id") == voiceover_id:
                    entry = item
                    break

            if not entry:
                return jsonify(
                    {"error": f"Voiceover ID {voiceover_id} not found for this video"},
                ), 404

            video_path = entry.get("dubbed_video_path")
            if not video_path or not os.path.exists(video_path):
                return jsonify({"error": "Dubbed video file not found"}), 404

            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                mime_type = "video/mp4"

            range_header = request.headers.get("Range")
            if range_header:
                logger.info(
                    "Voiceover video range request: video_id=%s voiceover_id=%s range=%s",
                    video_id,
                    voiceover_id,
                    range_header,
                )

            return send_file(
                video_path,
                mimetype=mime_type,
                as_attachment=False,
                download_name=os.path.basename(video_path),
                conditional=True,
            )

        except Exception as e:
            return api_error(500, "Failed to retrieve voiceover video", logger=logger, exc=e)
