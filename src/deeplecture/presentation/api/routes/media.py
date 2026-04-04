"""Media file serving routes (video, pdf, screenshots)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Blueprint, request, send_file

from deeplecture.di import get_container
from deeplecture.presentation.api.shared import bad_request, handle_errors, not_found
from deeplecture.presentation.api.shared.validation import (
    validate_content_id,
    validate_filename,
    validate_language,
)
from deeplecture.use_cases.shared.source_language import (
    SourceLanguageResolutionError,
    resolve_source_language,
)
from deeplecture.use_cases.shared.subtitle import load_subtitle_segments_with_fallback

if TYPE_CHECKING:
    from flask import Response

bp = Blueprint("media", __name__)

ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
ALLOWED_PDF_EXT = {".pdf"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}
FILENAME_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


@bp.route("/<content_id>/video", methods=["GET"])
@handle_errors
def get_content_video(content_id: str) -> Response:
    """Serve the playable video for a content item."""
    content_id = validate_content_id(content_id)
    container = get_container()
    metadata = container.content_usecase.get_content(content_id)
    content_dir = Path(container.path_resolver.get_content_dir(content_id))
    video_path = _resolve_content_video_path(metadata, content_dir)
    if video_path is not None:
        return send_file(video_path, conditional=True)

    return not_found("No video available for this content")


@bp.route("/<content_id>/video/download", methods=["GET"])
@handle_errors
def download_content_video(content_id: str) -> Response:
    """
    Download an MP4 export with selectable audio track and hard subtitles.

    Query params:
    - audio_track: "original" or voiceover id
    - burn_source_subtitle: bool
    - burn_target_subtitle: bool
    - source_language: base language (required when burn_source_subtitle=true)
    - target_language: base language (required when burn_target_subtitle=true)
    """
    content_id = validate_content_id(content_id)
    container = get_container()
    metadata = container.content_usecase.get_content(content_id)
    content_dir = Path(container.path_resolver.get_content_dir(content_id))
    video_path = _resolve_content_video_path(metadata, content_dir)
    if video_path is None:
        return not_found("No video available for this content")

    audio_track_raw = (request.args.get("audio_track") or "original").strip()
    audio_path = _resolve_audio_track_path(content_dir, audio_track_raw)
    if audio_path is False:
        return not_found("Selected audio track not found")

    burn_source = _parse_bool_query(
        request.args.get("burn_source_subtitle"),
        field_name="burn_source_subtitle",
        default=False,
    )
    burn_target = _parse_bool_query(
        request.args.get("burn_target_subtitle"),
        field_name="burn_target_subtitle",
        default=False,
    )

    source_language = validate_language(
        request.args.get("source_language"),
        field_name="source_language",
        default="",
        allow_auto=True,
    )
    target_language = validate_language(request.args.get("target_language"), field_name="target_language", default="")

    subtitle_path: Path | None = None
    subtitle_mode_label = "sub_none"
    exports_dir = (content_dir / "exports").resolve(strict=False)
    exports_dir.mkdir(parents=True, exist_ok=True)
    if not _is_within_dir(exports_dir, content_dir):
        return not_found("Export directory not available")

    source_loaded = None
    target_loaded = None

    if burn_source:
        if not source_language:
            return bad_request("source_language is required when burn_source_subtitle=true")
        try:
            resolved_source_language = resolve_source_language(
                source_language,
                metadata=metadata,
                field_name="source_language",
            )
        except SourceLanguageResolutionError as exc:
            return bad_request(str(exc))
        source_loaded = load_subtitle_segments_with_fallback(
            container.subtitle_storage,
            content_id=content_id,
            base_language=resolved_source_language,
        )
        if source_loaded is None:
            return not_found(f"Source subtitles not found for language: {resolved_source_language}")

    if burn_target:
        if not target_language:
            return bad_request("target_language is required when burn_target_subtitle=true")
        target_loaded = load_subtitle_segments_with_fallback(
            container.subtitle_storage,
            content_id=content_id,
            base_language=target_language,
        )
        if target_loaded is None:
            return not_found(f"Target subtitles not found for language: {target_language}")

    if burn_source and source_loaded is not None and not burn_target:
        source_key, source_segments = source_loaded
        source_fp = _subtitle_segments_fingerprint(source_segments)
        subtitle_path = (exports_dir / f"subtitle_source_{source_key}_{source_fp}.srt").resolve(strict=False)
        if not subtitle_path.exists():
            subtitle_path.write_text(_segments_to_srt(source_segments), encoding="utf-8")
        subtitle_mode_label = f"sub_source_{source_key}"

    elif burn_target and target_loaded is not None and not burn_source:
        target_key, target_segments = target_loaded
        target_fp = _subtitle_segments_fingerprint(target_segments)
        subtitle_path = (exports_dir / f"subtitle_target_{target_key}_{target_fp}.srt").resolve(strict=False)
        if not subtitle_path.exists():
            subtitle_path.write_text(_segments_to_srt(target_segments), encoding="utf-8")
        subtitle_mode_label = f"sub_target_{target_key}"

    elif burn_source and burn_target and source_loaded is not None and target_loaded is not None:
        source_key, source_segments = source_loaded
        target_key, target_segments = target_loaded
        source_fp = _subtitle_segments_fingerprint(source_segments)
        target_fp = _subtitle_segments_fingerprint(target_segments)
        dual_fp = hashlib.sha1(f"{source_fp}|{target_fp}".encode()).hexdigest()[:16]
        subtitle_path = (exports_dir / f"subtitle_dual_{source_key}_{target_key}_{dual_fp}.srt").resolve(strict=False)
        if not subtitle_path.exists():
            subtitle_path.write_text(
                _dual_segments_to_srt(source_segments, target_segments),
                encoding="utf-8",
            )
        subtitle_mode_label = f"sub_dual_{source_key}_{target_key}"

    if subtitle_path is not None and not _is_within_dir(subtitle_path, content_dir):
        return not_found("Subtitle overlay unavailable")

    audio_label = "original"
    if isinstance(audio_path, Path):
        audio_label = audio_path.stem

    download_name = _build_download_name(
        getattr(metadata, "original_filename", "") or content_id,
        audio_label=audio_label,
        subtitle_label=subtitle_mode_label,
    )

    # Fast path: no transform needed, original is already mp4 with original audio.
    if audio_path is None and subtitle_path is None and video_path.suffix.lower() == ".mp4":
        return send_file(
            video_path,
            mimetype="video/mp4",
            as_attachment=True,
            download_name=download_name,
            conditional=True,
        )

    cache_key_input = "|".join(
        [
            str(video_path),
            f"audio={audio_label}",
            f"subtitle={subtitle_mode_label}",
        ]
    )
    cache_key = hashlib.sha1(cache_key_input.encode("utf-8")).hexdigest()[:16]
    output_path = (exports_dir / f"download_{cache_key}.mp4").resolve(strict=False)
    if not _is_within_dir(output_path, content_dir):
        return not_found("Export path unavailable")

    deps = [video_path]
    if isinstance(audio_path, Path):
        deps.append(audio_path)
    if subtitle_path is not None:
        deps.append(subtitle_path)

    latest_dep_mtime = max(path.stat().st_mtime for path in deps)
    needs_render = (not output_path.exists()) or (output_path.stat().st_mtime < latest_dep_mtime)
    if needs_render:
        container.video_processor.export_mp4(
            str(video_path),
            str(output_path),
            audio_path=str(audio_path) if isinstance(audio_path, Path) else None,
            subtitle_path=str(subtitle_path) if subtitle_path is not None else None,
        )

    return send_file(
        output_path,
        mimetype="video/mp4",
        as_attachment=True,
        download_name=download_name,
        conditional=True,
    )


@bp.route("/<content_id>/pdf", methods=["GET"])
@handle_errors
def get_content_pdf(content_id: str) -> Response:
    """Serve the PDF slide deck for a content item."""
    content_id = validate_content_id(content_id)
    container = get_container()
    metadata = container.content_usecase.get_content(content_id)
    content_dir = Path(container.path_resolver.get_content_dir(content_id))

    source_file = getattr(metadata, "source_file", "")
    if not source_file:
        return not_found("PDF not available for this content")

    path = Path(source_file).expanduser().resolve(strict=False)
    if not _is_within_dir(path, content_dir):
        return not_found("PDF not available for this content")

    if path.is_file() and path.suffix.lower() in ALLOWED_PDF_EXT:
        return send_file(path, mimetype="application/pdf", conditional=True)

    return not_found("PDF not available for this content")


@bp.route("/<content_id>/screenshots/<filename>", methods=["GET"])
@handle_errors
def get_content_screenshot(content_id: str, filename: str) -> Response:
    """Serve a captured screenshot or note image for a content item."""
    content_id = validate_content_id(content_id)
    filename = validate_filename(filename, field_name="filename", allowed_extensions=ALLOWED_IMAGE_EXT)

    container = get_container()
    container.content_usecase.get_content(content_id)

    content_dir = Path(container.path_resolver.get_content_dir(content_id))
    image_path = (content_dir / "screenshots" / filename).resolve(strict=False)

    if not _is_within_dir(image_path, content_dir):
        return not_found("Screenshot not found")
    if not image_path.is_file():
        return not_found("Screenshot not found")

    return send_file(image_path, conditional=True)


def _is_within_dir(path: Path, base_dir: Path) -> bool:
    """Check that path stays within base_dir."""
    try:
        path.resolve(strict=False).relative_to(base_dir.resolve(strict=False))
        return True
    except ValueError:
        return False


def _resolve_content_video_path(metadata: object, content_dir: Path) -> Path | None:
    candidates = []
    if getattr(metadata, "video_file", None):
        candidates.append(metadata.video_file)
    if getattr(metadata, "source_file", None):
        candidates.append(metadata.source_file)

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve(strict=False)
        if not _is_within_dir(path, content_dir):
            continue
        if path.is_file() and path.suffix.lower() in ALLOWED_VIDEO_EXT:
            return path
    return None


def _resolve_audio_track_path(content_dir: Path, audio_track_raw: str) -> Path | None | bool:
    normalized = audio_track_raw.strip().lower()
    if normalized in ("", "original", "video_original"):
        return None

    audio_track = validate_filename(audio_track_raw, field_name="audio_track")
    audio_track_id = Path(audio_track).stem
    if not audio_track_id:
        raise ValueError("audio_track is invalid")

    audio_path = (content_dir / "voiceovers" / f"{audio_track_id}.m4a").resolve(strict=False)
    if not _is_within_dir(audio_path, content_dir):
        raise ValueError("audio_track is invalid")
    if not audio_path.is_file():
        return False
    return audio_path


def _parse_bool_query(raw_value: str | None, *, field_name: str, default: bool) -> bool:
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{field_name} must be a boolean")


def _subtitle_segments_fingerprint(segments: list[object]) -> str:
    hasher = hashlib.sha1()
    for seg in segments:
        start = float(getattr(seg, "start", 0.0))
        end = float(getattr(seg, "end", 0.0))
        text = str(getattr(seg, "text", ""))
        hasher.update(f"{start:.6f}|{end:.6f}|{text}\n".encode())
    return hasher.hexdigest()[:16]


def _segments_to_srt(segments: list[object]) -> str:
    rows: list[tuple[float, float, str]] = []
    for seg in segments:
        rows.append(
            (
                float(getattr(seg, "start", 0.0)),
                float(getattr(seg, "end", 0.0)),
                str(getattr(seg, "text", "")),
            )
        )
    return _rows_to_srt(rows)


def _dual_segments_to_srt(source_segments: list[object], target_segments: list[object]) -> str:
    rows: list[tuple[float, float, str]] = []
    max_len = max(len(source_segments), len(target_segments))

    for idx in range(max_len):
        src = source_segments[idx] if idx < len(source_segments) else None
        tgt = target_segments[idx] if idx < len(target_segments) else None
        if src is None and tgt is None:
            continue

        start = float(getattr(src, "start", getattr(tgt, "start", 0.0)))
        end = float(getattr(src, "end", getattr(tgt, "end", start)))

        lines: list[str] = []
        if src is not None:
            src_text = str(getattr(src, "text", "")).strip()
            if src_text:
                lines.append(src_text)
        if tgt is not None:
            tgt_text = str(getattr(tgt, "text", "")).strip()
            if tgt_text:
                lines.append(tgt_text)

        text = "\n".join(lines).strip()
        if text:
            rows.append((start, end, text))

    return _rows_to_srt(rows)


def _rows_to_srt(rows: list[tuple[float, float, str]]) -> str:
    blocks: list[str] = []
    next_index = 1
    for start, end, text in rows:
        clean_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not clean_text:
            continue
        blocks.append(f"{next_index}\n" f"{_format_srt_time(start)} --> {_format_srt_time(end)}\n" f"{clean_text}\n")
        next_index += 1
    return "\n".join(blocks)


def _format_srt_time(seconds: float) -> str:
    sec = max(0.0, float(seconds))
    hours = int(sec // 3600)
    minutes = int((sec % 3600) // 60)
    whole_seconds = int(sec % 60)
    millis = round((sec - int(sec)) * 1000)
    if millis >= 1000:
        whole_seconds += 1
        millis -= 1000
    if whole_seconds >= 60:
        minutes += 1
        whole_seconds -= 60
    if minutes >= 60:
        hours += 1
        minutes -= 60
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


def _build_download_name(original_filename: str, *, audio_label: str, subtitle_label: str) -> str:
    base = Path(original_filename).stem or "video"
    safe_base = _sanitize_filename_component(base)
    safe_audio = _sanitize_filename_component(audio_label or "original")
    safe_sub = _sanitize_filename_component(subtitle_label or "sub_none")
    return f"{safe_base}_{safe_audio}_{safe_sub}.mp4"


def _sanitize_filename_component(value: str) -> str:
    cleaned = FILENAME_SAFE_RE.sub("_", value).strip("._")
    return cleaned or "video"
