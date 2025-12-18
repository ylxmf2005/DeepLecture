#!/usr/bin/env python3
"""
Prepare test data for performance baseline measurements.

Creates synthetic test content to avoid depending on real production data.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_video(content_id: str, duration_seconds: int, output_dir: Path) -> Path:
    """
    Create synthetic test video using ffmpeg.

    Args:
        content_id: Content identifier
        duration_seconds: Video duration
        output_dir: Output directory

    Returns:
        Path to created video
    """
    import subprocess

    content_dir = output_dir / content_id
    content_dir.mkdir(parents=True, exist_ok=True)

    video_path = content_dir / "source.mp4"

    # Generate test video with color bars and timecode
    cmd = [
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration_seconds}:size=1280x720:rate=30",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=1000:duration={duration_seconds}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        "-y",
        str(video_path),
    ]

    logger.info(f"Creating test video: {content_id} ({duration_seconds}s)")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"Failed to create video: {result.stderr}")
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    logger.info(f"Created: {video_path}")
    return video_path


def create_test_subtitle(content_id: str, duration_seconds: int, output_dir: Path) -> Path:
    """
    Create synthetic SRT subtitle file.

    Args:
        content_id: Content identifier
        duration_seconds: Total duration
        output_dir: Output directory

    Returns:
        Path to created subtitle
    """
    content_dir = output_dir / content_id / "subtitles"
    content_dir.mkdir(parents=True, exist_ok=True)

    subtitle_path = content_dir / "original.srt"

    # Generate subtitle entries every 5 seconds
    with open(subtitle_path, "w") as f:
        for i in range(0, duration_seconds, 5):
            start = i
            end = min(i + 5, duration_seconds)

            f.write(f"{i // 5 + 1}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(f"Test subtitle segment {i // 5 + 1}\n")
            f.write("This is synthetic test content for performance baseline.\n")
            f.write("\n")

    logger.info(f"Created subtitle: {subtitle_path}")
    return subtitle_path


def create_test_pdf(deck_id: str, num_pages: int, output_dir: Path) -> Path:
    """
    Create synthetic PDF with multiple pages.

    Args:
        deck_id: Deck identifier
        num_pages: Number of pages
        output_dir: Output directory

    Returns:
        Path to created PDF
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        logger.warning("reportlab not installed - skipping PDF creation")
        logger.warning("Install with: pip install reportlab")
        return None

    content_dir = output_dir / deck_id
    content_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = content_dir / "source.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter

    for page_num in range(1, num_pages + 1):
        c.setFont("Helvetica-Bold", 24)
        c.drawString(100, height - 100, f"Test Slide {page_num}")

        c.setFont("Helvetica", 12)
        c.drawString(100, height - 150, f"This is page {page_num} of {num_pages}")
        c.drawString(100, height - 170, "Synthetic test content for performance baseline")

        c.showPage()

    c.save()

    logger.info(f"Created PDF: {pdf_path} ({num_pages} pages)")
    return pdf_path


def create_test_metadata(content_id: str, content_type: str, output_dir: Path) -> None:
    """Create metadata JSON for test content."""
    content_dir = output_dir / content_id
    content_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "id": content_id,
        "type": content_type,
        "display_name": f"Test {content_type} - {content_id}",
        "created_at": "2025-12-12T00:00:00Z",
        "subtitle_status": "none",
        "timeline_status": "none",
    }

    metadata_path = content_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Created metadata: {metadata_path}")


def format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def prepare_all_test_data(output_dir: Path) -> None:
    """Prepare all test data required for baseline tests."""
    logger.info("Preparing test data for performance baseline")
    logger.info(f"Output directory: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Video test data
    video_configs = [
        ("test_subtitle_short", 120),  # 2 minutes
        ("test_subtitle_medium", 600),  # 10 minutes
        ("test_subtitle_long", 1800),  # 30 minutes
        ("test_enhance_short", 120),
        ("test_enhance_medium", 600),
        ("test_translate_short", 120),
        ("test_translate_medium", 600),
        ("test_timeline_short", 120),
        ("test_timeline_medium", 600),
        ("test_note_short", 120),
        ("test_note_medium", 600),
        ("test_voiceover_short", 120),
        ("test_voiceover_medium", 600),
    ]

    for content_id, duration in video_configs:
        try:
            create_test_video(content_id, duration, output_dir)
            create_test_subtitle(content_id, duration, output_dir)
            create_test_metadata(content_id, "video", output_dir)
        except Exception as exc:
            logger.error(f"Failed to create {content_id}: {exc}")

    # PDF test data
    pdf_configs = [
        ("test_deck_5", 5),  # 5 pages
        ("test_deck_20", 20),  # 20 pages
    ]

    for deck_id, num_pages in pdf_configs:
        try:
            create_test_pdf(deck_id, num_pages, output_dir)
            create_test_metadata(deck_id, "pdf", output_dir)
        except Exception as exc:
            logger.error(f"Failed to create {deck_id}: {exc}")

    logger.info("\nTest data preparation complete")
    logger.info(f"Total content items created: {len(video_configs) + len(pdf_configs)}")


def main():
    parser = argparse.ArgumentParser(description="Prepare test data for performance baseline")
    parser.add_argument(
        "--output-dir",
        default="data/test",
        help="Output directory for test data",
    )
    parser.add_argument(
        "--skip-videos",
        action="store_true",
        help="Skip video generation (requires ffmpeg)",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.skip_videos:
        logger.warning("Skipping video generation")
        logger.warning("Only subtitle and PDF test data will be created")

    try:
        prepare_all_test_data(output_dir)
        logger.info("\n✅ Test data preparation successful")
    except Exception as exc:
        logger.error(f"\n❌ Test data preparation failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
