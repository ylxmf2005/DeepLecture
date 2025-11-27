from __future__ import annotations

import os
import re
import subprocess
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

import json
import json_repair
import mimetypes
import logging
from flask import Flask, jsonify, request, send_file

from deeplecture.config.config import load_config
from deeplecture.prompts.slide_lecture_prompt import build_slide_lecture_prompt  # noqa: F401 - imported for side-effect docs
from deeplecture.services.slide_lecture_service import SlideLectureService
from deeplecture.services.content_service import ContentService
from deeplecture.transcription.interactive import parse_srt_to_segments
from deeplecture.workers import TaskManager
from deeplecture.api.error_utils import api_error


# Namespaced subdirectories under the content workspace. Kept as simple
# constants here to avoid leaking slide-specific details into app_context.
SCREENSHOTS_SUBDIR = "screenshots"
EXPLANATIONS_SUBDIR = "explanations"
NOTES_ASSETS_SUBDIR = "notes_assets"

logger = logging.getLogger(__name__)
VALID_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

def _srt_to_vtt(srt_content: str) -> str:
    """
    Convert basic SRT subtitle content to WebVTT.
    """
    lines = srt_content.splitlines()
    vtt_lines = ["WEBVTT", ""]

    for line in lines:
        if "-->" in line:
            vtt_lines.append(line.replace(",", "."))
        else:
            vtt_lines.append(line)

    return "\n".join(vtt_lines)


def _get_subtitle_context_window_seconds() -> float:
    """
    Resolve the default subtitle context window (half‑width in seconds)
    used when combining screenshots with nearby transcript text.
    """
    try:
        config = load_config()
        slides_cfg = (config or {}).get("slides") or {}
        explanation_cfg = slides_cfg.get("explanation") or {}
        raw = explanation_cfg.get("subtitle_context_window_seconds", 30.0)
        value = float(raw)
        if value <= 0:
            return 30.0
        return value
    except Exception:
        # Fail safe to a reasonable default.
        return 30.0


def _build_subtitle_context_for_timestamp(
    subtitle_path: Optional[str],
    timestamp: Optional[float],
    window_seconds: float,
) -> str:
    """
    Load the original‑language subtitles for a video and extract a small
    window of context around the given timestamp.

    Returns a human‑readable text block (one line per subtitle) or an
    empty string if subtitles are missing.
    """
    if timestamp is None or not subtitle_path:
        return ""

    if not os.path.exists(subtitle_path):
        return ""

    try:
        with open(subtitle_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        logger.error(
            "Failed to read subtitle file %s for context: %s",
            subtitle_path,
            exc,
        )
        return ""

    segments = parse_srt_to_segments(content)
    if not segments:
        return ""

    try:
        center = float(timestamp)
    except (TypeError, ValueError):
        return ""

    window = max(float(window_seconds), 0.0)
    start_time = max(0.0, center - window)
    end_time = center + window

    lines: List[str] = []
    for seg in segments:
        if seg.end < start_time or seg.start > end_time:
            continue
        text = seg.text.replace("\n", " ").strip()
        if not text:
            continue
        lines.append(f"[{seg.start:.1f}s] {text}")

    return "\n".join(lines)


def register_slide_routes(
    app: Flask,
    content_service: ContentService,
    slide_lecture_service: SlideLectureService | None = None,
    task_manager: TaskManager | None = None,
) -> None:
    """
    Register slide/screenshot capture and explanation routes.
    """

    slide_lecture_service = slide_lecture_service or SlideLectureService(
        content_service=content_service,
        task_manager=task_manager,
    )

    @app.route("/api/content/<content_id>/screenshots", methods=["POST"])
    @app.route("/api/capture-slide", methods=["POST"])
    def capture_slide(content_id: str | None = None):
        """Capture a frame from the video at the specified timestamp."""
        try:
            data = request.json or {}
            video_id = data.get("video_id") or content_id
            timestamp = data.get("timestamp")

            if not video_id or timestamp is None:
                return jsonify({"error": "Missing video_id or timestamp"}), 400
            # Use the unified content service for resolving video paths so
            # that both regular videos and slide lecture videos (generated from
            # PDFs) are supported. Older uploads without metadata are no longer
            # supported.
            video_path = content_service.get_video_path(str(video_id))
            if not video_path:
                return jsonify({"error": "Video not found"}), 404

            screenshots_dir = content_service.ensure_content_dir(
                str(video_id),
                SCREENSHOTS_SUBDIR,
            )

            filename = f"{int(float(timestamp) * 1000)}.jpg"
            output_path = os.path.join(screenshots_dir, filename)

            command = [
                "ffmpeg",
                "-ss",
                str(timestamp),
                "-i",
                video_path,
                "-vframes",
                "1",
                "-q:v",
                "2",
                "-y",
                output_path,
            ]

            subprocess.run(command, check=True, capture_output=True)

            image_url = (
                f"/api/get-screenshot?video_id={video_id}&filename={filename}"
            )

            try:
                ts_value = float(timestamp)
            except (TypeError, ValueError):
                ts_value = None

            content_service.register_artifact(
                str(video_id),
                output_path,
                kind="screenshot",
                media_type="image/jpeg",
                metadata={"timestamp": ts_value} if ts_value is not None else None,
            )

            # Also copy the screenshot into a notes‑scoped assets directory so
            # that exported markdown notes can reference images via a simple
            # relative path (../notes_assets/<video_id>/<filename>) without
            # depending on the API.
            try:
                notes_assets_dir = content_service.ensure_content_dir(
                    str(video_id),
                    NOTES_ASSETS_SUBDIR,
                )
                note_asset_path = os.path.join(notes_assets_dir, filename)
                shutil.copy2(output_path, note_asset_path)
                content_service.register_artifact(
                    str(video_id),
                    note_asset_path,
                    kind="note-image",
                    media_type="image/jpeg",
                    metadata={"timestamp": ts_value} if ts_value is not None else None,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to copy screenshot %s into notes assets for %s: %s",
                    output_path,
                    video_id,
                    exc,
                )

            return jsonify(
                {
                    "image_url": image_url,
                    "image_path": output_path,
                    "timestamp": timestamp,
                },
            )

        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg error: %s", e.stderr.decode())
            return jsonify({"error": "Failed to capture frame"}), 500
        except Exception as e:
            return api_error(500, "Failed to capture slide", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/screenshots/<filename>", methods=["GET"])
    @app.route("/api/get-screenshot", methods=["GET"])
    def get_screenshot(content_id: str | None = None, filename: str | None = None):
        """Serve captured screenshot."""
        video_id = (content_id or request.args.get("video_id", "")).strip()
        filename = (filename or request.args.get("filename", "")).strip()

        if not video_id or not filename:
            return jsonify({"error": "Missing parameters"}), 400

        if not VALID_ID_RE.match(video_id):
            return jsonify({"error": "Invalid video_id"}), 400

        # Prevent path traversal by normalising the filename.
        safe_filename = os.path.basename(filename)
        if safe_filename != filename or not safe_filename:
            return jsonify({"error": "Invalid filename"}), 400

        ext = os.path.splitext(safe_filename)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            return jsonify({"error": "Unsupported file type"}), 400

        try:
            file_path = content_service.build_content_path(
                str(video_id),
                SCREENSHOTS_SUBDIR,
                safe_filename,
            )
        except ValueError:
            return jsonify({"error": "Invalid path"}), 400

        if not os.path.exists(file_path):
            return jsonify({"error": "Image not found"}), 404

        return send_file(file_path, mimetype=mimetypes.guess_type(file_path)[0] or "image/jpeg")

    @app.route("/api/content/<content_id>/explanations", methods=["POST"])
    @app.route("/api/explain-slide", methods=["POST"])
    def explain_slide(content_id: str | None = None):
        """Generate AI explanation for a slide as a background task."""
        try:
            data = request.json or {}
            image_path = data.get("image_path")
            video_id = data.get("video_id") or content_id
            timestamp = data.get("timestamp")
            raw_instruction = data.get("prompt")
            learner_profile = data.get("learner_profile")
            context_window_override = data.get("subtitle_context_window_seconds")

            if not image_path or not video_id:
                return jsonify({"error": "Missing required parameters"}), 400

            explanations_dir = content_service.ensure_content_dir(
                str(video_id),
                EXPLANATIONS_SUBDIR,
            )

            # Parse timestamp once so we can reuse it for file naming and
            # subtitle window selection.
            timestamp_value: Optional[float]
            try:
                timestamp_value = float(timestamp)
            except (TypeError, ValueError):
                timestamp_value = None

            try:
                base_seconds = (
                    timestamp_value
                    if timestamp_value is not None
                    else datetime.now().timestamp()
                )
                timestamp_ms = int(base_seconds * 1000)
            except Exception:
                timestamp_ms = int(datetime.now().timestamp() * 1000)

            json_filename = f"{timestamp_ms}.json"
            json_path = os.path.join(explanations_dir, json_filename)

            explanation_id = str(timestamp_ms)

            base_payload: Dict[str, Any] = {
                "id": explanation_id,
                "timestamp": timestamp_value if timestamp_value is not None else timestamp,
                "image_path": image_path,
                "explanation": "",
                "created_at": datetime.now().isoformat(),
            }

            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(base_payload, f, ensure_ascii=False, indent=2)
            except Exception as exc:
                logger.error(
                    "Failed to write placeholder explanation file %s: %s",
                    json_path,
                    exc,
                )
            else:
                content_service.register_artifact(
                    str(video_id),
                    json_path,
                    kind="explanation:placeholder",
                    media_type="application/json",
                )

            # Resolve subtitle context window (seconds) and collect nearby
            # original‑language subtitles around this frame so that the LLM
            # can combine what is said with what is shown.
            try:
                if context_window_override is not None:
                    window_seconds = float(context_window_override)
                else:
                    window_seconds = _get_subtitle_context_window_seconds()
            except (TypeError, ValueError):
                window_seconds = _get_subtitle_context_window_seconds()

            if window_seconds <= 0:
                window_seconds = _get_subtitle_context_window_seconds()

            subtitle_path = content_service.get_enhanced_subtitle_path(str(video_id))
            if not subtitle_path or not os.path.exists(subtitle_path):
                subtitle_path = content_service.get_subtitle_path(str(video_id))

            subtitle_context = _build_subtitle_context_for_timestamp(
                subtitle_path,
                timestamp_value,
                window_seconds,
            )

            if task_manager is None:
                return jsonify({"error": "Task manager not configured"}), 500

            task_id = task_manager.submit_task(
                str(video_id),
                "slide_explanation",
                metadata={
                    "video_id": str(video_id),
                    "image_path": image_path,
                    "json_path": json_path,
                    "timestamp": timestamp_value if timestamp_value is not None else timestamp,
                    "raw_instruction": raw_instruction,
                    "learner_profile": learner_profile,
                    "subtitle_context": subtitle_context,
                    "subtitle_window_seconds": window_seconds,
                },
            )

            return jsonify({"explanation": "", "data": base_payload, "task_id": task_id})

        except Exception as e:
            return api_error(500, "Failed to explain slide", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/explanations", methods=["GET"])
    @app.route("/api/explanation-history", methods=["GET"])
    def explanation_history(content_id: str | None = None):
        """Get history of explanations for a video."""
        video_id = content_id or request.args.get("video_id")
        if not video_id:
            return jsonify({"error": "Missing video_id"}), 400

        try:
            explanations_dir = content_service.build_content_path(
                str(video_id),
                EXPLANATIONS_SUBDIR,
            )
            if not os.path.exists(explanations_dir):
                return jsonify({"history": []})

            history: List[Dict[str, Any]] = []
            for filename in os.listdir(explanations_dir):
                if not filename.endswith(".json"):
                    continue
                with open(
                    os.path.join(explanations_dir, filename),
                    "r",
                    encoding="utf-8",
                ) as f:
                    data = json_repair.load(f)

                if "id" not in data:
                    data["id"] = os.path.splitext(filename)[0]

                image_path = data.get("image_path")
                img_filename = os.path.basename(image_path) if image_path else None

                # Backfill notes_assets copies for older explanation records so
                # that their screenshots can also be referenced from exported
                # markdown notes via ../notes_assets/<video_id>/<filename>.
                if img_filename:
                    try:
                        notes_assets_dir = content_service.ensure_content_dir(
                            str(video_id),
                            NOTES_ASSETS_SUBDIR,
                        )
                        note_asset_path = os.path.join(notes_assets_dir, img_filename)
                        if not os.path.exists(note_asset_path):
                            screenshot_path = content_service.build_content_path(
                                str(video_id),
                                SCREENSHOTS_SUBDIR,
                                img_filename,
                            )
                            if os.path.exists(screenshot_path):
                                shutil.copy2(screenshot_path, note_asset_path)
                                content_service.register_artifact(
                                    str(video_id),
                                    note_asset_path,
                                    kind="note-image",
                                    media_type="image/jpeg",
                                )
                    except Exception as exc:
                        logger.warning(
                            "Failed to backfill notes assets for %s (%s): %s",
                            img_filename,
                            image_path,
                            exc,
                        )

                if img_filename:
                    data["image_url"] = (
                        f"/api/get-screenshot?video_id={video_id}&filename={img_filename}"
                    )

                history.append(data)

            def _ts_value(item: Dict[str, Any]) -> float:
                try:
                    return float(item.get("timestamp", 0) or 0.0)
                except (TypeError, ValueError):
                    return 0.0

            history.sort(key=_ts_value)

            return jsonify({"history": history})

        except Exception as e:
            return api_error(500, "Failed to fetch history", logger=logger, exc=e)

    @app.route("/api/content/<content_id>/explanations/<entry_id>", methods=["DELETE"])
    @app.route("/api/delete-explanation", methods=["POST"])
    def delete_explanation(content_id: str | None = None, entry_id: str | None = None):
        """
        Delete a single explanation note for a video.
        """
        data = request.json or {}
        if not data and request.args:
            data = request.args
        video_id = content_id or data.get("video_id")
        entry_id = entry_id or data.get("id") or data.get("entry_id")
        timestamp = data.get("timestamp")

        if not video_id:
            return jsonify({"error": "Missing video_id"}), 400

        if entry_id is None and timestamp is None:
            return jsonify({"error": "Missing id or timestamp"}), 400

        try:
            explanations_dir = content_service.build_content_path(
                str(video_id),
                EXPLANATIONS_SUBDIR,
            )
            if not os.path.exists(explanations_dir):
                return jsonify({"error": "Explanation not found"}), 404

            if entry_id is not None:
                json_filename = f"{entry_id}.json"
            else:
                try:
                    timestamp_ms = int(float(timestamp) * 1000)
                except (TypeError, ValueError):
                    return jsonify({"error": "Invalid timestamp"}), 400
                json_filename = f"{timestamp_ms}.json"

            json_path = os.path.join(explanations_dir, json_filename)
            if not os.path.exists(json_path):
                return jsonify({"error": "Explanation not found"}), 404

            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    payload = json_repair.load(f)
                image_path = payload.get("image_path")
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
                    content_service.unregister_artifact(str(video_id), image_path)
            except Exception as exc:
                logger.warning("Failed to delete explanation screenshot: %s", exc)

            os.remove(json_path)
            content_service.unregister_artifact(str(video_id), json_path)
            return jsonify({"message": "Explanation deleted"})

        except Exception as e:
            return api_error(500, "Failed to delete explanation", logger=logger, exc=e)

    # ------------------------------------------------------------------
    # PDF slide lecture API
    # ------------------------------------------------------------------

    @app.route("/api/decks", methods=["POST"])
    @app.route("/api/upload-slide-pdf", methods=["POST"])
    def upload_slide_pdf():
        """
        Upload a PDF slide deck for AI lecture generation.
        """
        if "file" not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400

        pdf_file = request.files["file"]
        if not pdf_file or pdf_file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        filename = pdf_file.filename
        if not filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are supported"}), 400

        try:
            dto = slide_lecture_service.register_deck(pdf_file, filename)
            return jsonify(
                {
                    "deck_id": dto.deck_id,
                    "filename": dto.filename,
                    "page_count": dto.page_count,
                    "message": "PDF uploaded successfully",
                },
            )
        except ImportError as exc:
            logger.error("PDF rendering dependency error: %s", exc)
            return jsonify(
                {
                    "error": str(exc),
                },
            ), 500
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error uploading slide PDF: %s", exc, exc_info=True)
            return jsonify({"error": f"Failed to upload PDF: {str(exc)}"}), 500

    @app.route("/api/decks/<deck_id>", methods=["GET"])
    @app.route("/api/get-slide-deck-meta", methods=["GET"])
    def get_slide_deck_meta(deck_id: str | None = None):
        """
        Return metadata for a previously uploaded slide deck.
        """
        deck_id = deck_id or request.args.get("deck_id")
        if not deck_id:
            return jsonify({"error": "Missing deck_id"}), 400

        try:
            meta = slide_lecture_service.get_deck_meta(str(deck_id))
        except FileNotFoundError as exc:
            logger.error("Slide deck not found when fetching meta: %s", exc)
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error fetching slide deck meta: %s", exc, exc_info=True)
            return jsonify(
                {"error": f"Failed to fetch slide deck meta: {str(exc)}"},
            ), 500

        return jsonify(meta)

    @app.route("/api/decks/<deck_id>/lecture", methods=["POST"])
    @app.route("/api/generate-slide-lecture", methods=["POST"])
    def generate_slide_lecture(deck_id: str | None = None):
        """
        Start AI lecture generation for a previously uploaded slide deck.
        """
        data = request.json or {}
        deck_id = deck_id or data.get("deck_id")
        if not deck_id:
            return jsonify({"error": "Missing deck_id"}), 400

        try:
            result = slide_lecture_service.start_generate_lecture(
                deck_id=str(deck_id),
                tts_language=data.get("tts_language"),
                page_break_silence_seconds=data.get(
                    "page_break_silence_seconds",
                ),
            )
            return jsonify(
                {
                    "deck_id": result.deck_id,
                    "lecture_video_path": result.lecture_video_path,
                    "subtitle_path": result.subtitle_path,
                    "status": result.status,
                    "message": result.message,
                    "job_id": result.job_id,
                },
            )
        except FileNotFoundError as exc:
            logger.error("Slide deck not found: %s", exc)
            return jsonify({"error": str(exc)}), 404
        except ImportError as exc:
            logger.error("Slide lecture dependency error: %s", exc)
            return jsonify({"error": str(exc)}), 500
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error starting slide lecture generation: %s", exc, exc_info=True)
            return jsonify(
                {"error": f"Slide lecture generation failed to start: {str(exc)}"},
            ), 500

    @app.route("/api/decks/<deck_id>/subtitles", methods=["GET"])
    @app.route("/api/get-slide-lecture-subtitles", methods=["GET"])
    def get_slide_lecture_subtitles(deck_id: str | None = None):
        """
        Return SRT or VTT subtitles for a generated slide lecture.
        """
        deck_id = deck_id or request.args.get("deck_id")
        if not deck_id:
            return jsonify({"error": "Missing deck_id"}), 400

        output_format = str(request.args.get("format", "srt")).lower()
        try:
            subtitle_path = slide_lecture_service.resolve_subtitle_path(deck_id)
            if not os.path.exists(subtitle_path):
                return jsonify(
                    {"error": f"Subtitle file not found for deck_id={deck_id}"},
                ), 404

            with open(subtitle_path, "r", encoding="utf-8") as f:
                content = f.read()

            if output_format == "vtt":
                vtt_content = _srt_to_vtt(content)
                return vtt_content, 200, {
                    "Content-Type": "text/vtt; charset=utf-8",
                }

            return content, 200, {
                "Content-Type": "text/plain; charset=utf-8",
            }
        except FileNotFoundError as exc:
            logger.error("Subtitle file not found for slide lecture: %s", exc)
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error reading slide lecture subtitles: %s", exc, exc_info=True)
            return jsonify(
                {"error": f"Failed to read slide lecture subtitles: {str(exc)}"},
            ), 500

    @app.route("/api/decks/<deck_id>/pdf", methods=["GET"])
    @app.route("/api/get-slide-pdf", methods=["GET"])
    def get_slide_pdf(deck_id: str | None = None):
        """
        Serve the original PDF for a slide deck so the frontend can embed it.
        """
        deck_id = deck_id or request.args.get("deck_id")
        if not deck_id:
            return jsonify({"error": "Missing deck_id"}), 400

        try:
            meta = slide_lecture_service.get_deck_meta(str(deck_id))
        except FileNotFoundError as exc:
            logger.error("Slide deck not found when serving PDF: %s", exc)
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error loading slide deck meta when serving PDF: %s", exc, exc_info=True)
            return jsonify(
                {"error": f"Failed to load slide deck meta: {str(exc)}"},
            ), 500

        pdf_path = meta.get("pdf_path")
        if not pdf_path or not os.path.exists(pdf_path):
            # Fallback to a copy stored under the deck output directory.
            deck_dir = meta.get("output_dir")
            if deck_dir:
                candidate = os.path.join(deck_dir, "source.pdf")
                if os.path.exists(candidate):
                    pdf_path = candidate

        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify(
                {"error": f"PDF file not found for deck_id={deck_id}"},
            ), 404

        return send_file(pdf_path, mimetype="application/pdf")

    @app.route("/api/decks/<deck_id>/video", methods=["GET"])
    @app.route("/api/get-slide-lecture-video", methods=["GET"])
    def get_slide_lecture_video(deck_id: str | None = None):
        """
        Stream the generated slide lecture video for a deck.
        """
        deck_id = deck_id or request.args.get("deck_id")
        if not deck_id:
            return jsonify({"error": "Missing deck_id"}), 400

        try:
            video_path = slide_lecture_service.resolve_lecture_video_path(deck_id)
            if not video_path or not os.path.exists(video_path):
                return jsonify(
                    {"error": f"Lecture video not found for deck_id={deck_id}"},
                ), 404

            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                mime_type = "video/mp4"

            range_header = request.headers.get("Range")
            if range_header:
                logger.info(
                    "Slide lecture video range request: deck_id=%s range=%s",
                    deck_id,
                    range_header,
                )

            return send_file(
                video_path,
                mimetype=mime_type,
                as_attachment=False,
                download_name=os.path.basename(video_path),
                conditional=True,
            )
        except Exception as exc:
            logger.error("Error retrieving slide lecture video: %s", exc)
            return jsonify(
                {"error": f"Failed to retrieve slide lecture video: {str(exc)}"},
            ), 500

    @app.route("/api/decks/<deck_id>/pages/<int:page>", methods=["GET"])
    @app.route("/api/get-slide-page-image", methods=["GET"])
    def get_slide_page_image(deck_id: str | None = None, page: int | None = None):
        """
        Serve a rendered slide page image (PNG) for a given deck.
        """
        deck_id = deck_id or request.args.get("deck_id")
        page_str = page if page is not None else request.args.get("page")

        if not deck_id or page_str is None:
            return jsonify({"error": "Missing deck_id or page"}), 400

        try:
            page_index = int(page_str)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid page index"}), 400

        try:
            image_path = slide_lecture_service.get_page_image_path(
                deck_id,
                page_index,
            )
            if not os.path.exists(image_path):
                return jsonify(
                    {
                        "error": (
                            f"Slide page image not found for deck_id={deck_id}, "
                            f"page={page_index}"
                        ),
                    },
                ), 404

            return send_file(image_path, mimetype="image/png")
        except Exception as exc:
            logger.error("Error retrieving slide page image: %s", exc)
            return jsonify(
                {"error": f"Failed to retrieve slide page image: {str(exc)}"},
            ), 500
