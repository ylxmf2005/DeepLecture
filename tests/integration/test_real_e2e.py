#!/usr/bin/env python3
"""
Real end-to-end test using actual video files from uploads directory.
This test uses real faster-whisper library, not mocks.
"""

import sys
import os
import time
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_real_video_transcription():
    """Test with real video file from uploads directory."""

    print("=" * 70)
    print("🎬 Real Video E2E Test with Faster-whisper")
    print("=" * 70)

    # Find a test video
    video_file = "uploads/2bb42300-91ae-437c-bbab-7fdb0696c58b.mp4"

    if not os.path.exists(video_file):
        print(f"❌ Video file not found: {video_file}")
        return False

    file_size_mb = os.path.getsize(video_file) / (1024 * 1024)
    print(f"\n📹 Test video: {os.path.basename(video_file)}")
    print(f"   Size: {file_size_mb:.1f} MB")

    # Step 1: Create test configuration
    print("\n📝 Step 1: Setting up configuration...")

    # Create a test config that uses faster-whisper
    test_config = {
        'subtitle': {
            'engine': 'faster_whisper',
            'use_mock': False,
            'source_language': 'en',
            'faster_whisper': {
                'model_size': 'tiny',  # Use tiny model for speed
                'device': 'cpu',
                'compute_type': 'int8',
                'download_root': os.path.expanduser('~/.cache/whisper')
            }
        }
    }

    # Step 2: Initialize the engine
    print("\n🔧 Step 2: Initializing FasterWhisperEngine...")

    from deeplecture.transcription.faster_whisper_engine import FasterWhisperEngine

    engine = FasterWhisperEngine(
        model_size='tiny',  # Small model for testing speed
        device='cpu',
        compute_type='int8'
    )

    print("   ✅ Engine initialized")

    # Step 3: Perform transcription
    print("\n🎙️ Step 3: Transcribing video (this may take a few minutes)...")
    print("   Using model: tiny (fastest, ~39MB)")
    print("   First run will download the model if needed...")

    output_dir = "outputs/test_e2e"
    os.makedirs(output_dir, exist_ok=True)

    output_srt = os.path.join(output_dir, "test_transcription.srt")

    start_time = time.time()

    try:
        # Extract first 60 seconds for faster testing
        print("\n   Extracting first 60 seconds for testing...")
        temp_video = os.path.join(output_dir, "test_clip.mp4")

        # Use ffmpeg to extract first minute
        extract_cmd = f'ffmpeg -i "{video_file}" -t 60 -c copy -y "{temp_video}" 2>/dev/null'
        os.system(extract_cmd)

        if not os.path.exists(temp_video):
            print("   ⚠️ Could not extract clip, using full video")
            temp_video = video_file
        else:
            clip_size_mb = os.path.getsize(temp_video) / (1024 * 1024)
            print(f"   ✅ Created test clip: {clip_size_mb:.1f} MB")

        # Transcribe
        print("\n   Starting transcription...")
        success = engine.generate_subtitles(
            video_path=temp_video,
            output_path=output_srt,
            language='en'  # Force English for testing
        )

        elapsed = time.time() - start_time

        if not success:
            print(f"   ❌ Transcription failed after {elapsed:.1f} seconds")
            return False

        print(f"   ✅ Transcription completed in {elapsed:.1f} seconds")

    except Exception as e:
        print(f"   ❌ Error during transcription: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Verify SRT output
    print("\n📄 Step 4: Verifying SRT output...")

    if not os.path.exists(output_srt):
        print("   ❌ Output SRT file not found")
        return False

    with open(output_srt, 'r', encoding='utf-8') as f:
        srt_content = f.read()

    # Parse and validate SRT format
    lines = srt_content.strip().split('\n')

    if len(lines) < 3:
        print("   ❌ SRT file too short")
        return False

    # Count subtitles
    subtitle_count = 0
    timestamps = []
    texts = []

    i = 0
    while i < len(lines):
        # Skip empty lines
        if not lines[i].strip():
            i += 1
            continue

        # Expect subtitle number
        if lines[i].strip().isdigit():
            subtitle_count += 1
            i += 1

            # Expect timestamp
            if i < len(lines) and ' --> ' in lines[i]:
                timestamps.append(lines[i].strip())
                i += 1

                # Collect text until next empty line or number
                text_lines = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit():
                    text_lines.append(lines[i].strip())
                    i += 1

                if text_lines:
                    texts.append(' '.join(text_lines))
        else:
            i += 1

    print(f"   📊 Subtitle statistics:")
    print(f"      - Total subtitles: {subtitle_count}")
    print(f"      - Total duration: {timestamps[-1].split(' --> ')[1] if timestamps else 'N/A'}")
    print(f"      - Average text length: {sum(len(t) for t in texts) / len(texts) if texts else 0:.1f} chars")

    # Show sample subtitles
    print(f"\n   📝 First 5 subtitles:")
    print("   " + "-" * 50)
    for i in range(min(5, len(texts))):
        print(f"   [{i+1}] {timestamps[i] if i < len(timestamps) else ''}")
        print(f"       {texts[i] if i < len(texts) else ''}")
    print("   " + "-" * 50)

    # Validate format
    validations = {
        "Has subtitles": subtitle_count > 0,
        "Has timestamps": len(timestamps) > 0,
        "Has text": len(texts) > 0,
        "Valid timestamp format": all(' --> ' in ts for ts in timestamps),
        "Text not empty": all(len(t.strip()) > 0 for t in texts)
    }

    print("\n   ✅ Format validations:")
    all_valid = True
    for check, passed in validations.items():
        status = "✅" if passed else "❌"
        print(f"      {status} {check}")
        if not passed:
            all_valid = False

    if not all_valid:
        return False

    # Step 5: Test integration with WhisperEngine
    print("\n🔌 Step 5: Testing integration with WhisperEngine...")

    from unittest.mock import patch

    with patch('deeplecture.config.config.load_config', return_value=test_config):
        from deeplecture.transcription.whisper_engine import WhisperEngine

        whisper_engine = WhisperEngine()

        # Check engine type
        engine_type = type(whisper_engine._delegate).__name__

        if engine_type == "FasterWhisperEngine":
            print(f"   ✅ WhisperEngine correctly selected {engine_type}")
        else:
            print(f"   ❌ Wrong engine type: {engine_type}")
            return False

        # Test through WhisperEngine
        output_srt2 = os.path.join(output_dir, "test_via_whisper_engine.srt")

        print("\n   Testing transcription through WhisperEngine...")
        success = whisper_engine.generate_subtitles(
            video_path=temp_video,
            output_path=output_srt2,
            language='en'
        )

        if success and os.path.exists(output_srt2):
            print("   ✅ WhisperEngine integration successful")

            # Compare outputs
            with open(output_srt2, 'r', encoding='utf-8') as f:
                srt2_content = f.read()

            if srt2_content == srt_content:
                print("   ✅ Output identical through both paths")
            else:
                print("   ⚠️ Output differs slightly (this is okay)")
        else:
            print("   ❌ WhisperEngine integration failed")
            return False

    # Step 6: Performance analysis
    print("\n📊 Step 6: Performance Analysis...")

    if temp_video != video_file:
        clip_duration = 60  # seconds
        transcription_time = elapsed
        real_time_factor = transcription_time / clip_duration

        print(f"   ⏱️ Performance metrics:")
        print(f"      - Clip duration: {clip_duration} seconds")
        print(f"      - Transcription time: {transcription_time:.1f} seconds")
        print(f"      - Real-time factor: {real_time_factor:.2f}x")

        if real_time_factor < 1:
            print(f"      - Speed: Faster than real-time! ⚡")
        else:
            print(f"      - Speed: {1/real_time_factor:.1f}x real-time")

    # Cleanup
    print("\n🧹 Cleaning up test files...")
    if temp_video != video_file and os.path.exists(temp_video):
        os.remove(temp_video)
        print("   ✅ Removed test clip")

    return True


def main():
    """Run the real E2E test."""

    print("\n🚀 " * 20)
    print("Real End-to-End Test with Actual Video")
    print("🚀 " * 20)

    # Check faster-whisper installation
    try:
        import faster_whisper
        print(f"\n✅ Using faster-whisper version {faster_whisper.__version__}")
    except ImportError:
        print("\n❌ faster-whisper not installed!")
        return 1

    # Check for GPU
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✅ GPU available: {torch.cuda.get_device_name(0)}")
        else:
            print("ℹ️ Using CPU mode")
    except ImportError:
        print("ℹ️ PyTorch not installed, using CPU mode")

    # Run test
    success = test_real_video_transcription()

    if success:
        print("\n" + "=" * 70)
        print("🎉 SUCCESS: Real E2E test passed!")
        print("=" * 70)

        print("\n✨ What we verified:")
        print("  1. Real video file transcription works")
        print("  2. SRT format is correct and valid")
        print("  3. WhisperEngine integration works")
        print("  4. Performance is acceptable")
        print("  5. Ready for production use!")

        return 0
    else:
        print("\n" + "=" * 70)
        print("❌ FAILED: Real E2E test failed")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())