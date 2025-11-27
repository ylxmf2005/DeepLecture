#!/usr/bin/env python3
"""
Simple test to verify faster-whisper can transcribe audio at all.
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_simple_transcription():
    """Test with minimal configuration."""

    print("=" * 70)
    print("🎬 Simple Faster-whisper Test")
    print("=" * 70)

    # Find a test video
    video_file = "uploads/2bb42300-91ae-437c-bbab-7fdb0696c58b.mp4"

    if not os.path.exists(video_file):
        print(f"❌ Video file not found: {video_file}")
        return False

    print(f"\n📹 Test video: {os.path.basename(video_file)}")

    # Test direct faster-whisper usage
    print("\n🔧 Testing direct faster-whisper usage...")

    try:
        from faster_whisper import WhisperModel

        # Use tiny model for speed
        print("Loading tiny model...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")

        print("Transcribing (without VAD)...")
        start_time = time.time()

        # Transcribe without VAD first
        segments, info = model.transcribe(
            video_file,
            language="en",
            vad_filter=False,  # Disable VAD
            beam_size=5,
        )

        # Convert to list to consume the generator
        segment_list = list(segments)

        elapsed = time.time() - start_time

        print(f"\n✅ Transcription took {elapsed:.1f} seconds")
        print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
        print(f"Number of segments: {len(segment_list)}")

        if len(segment_list) > 0:
            print("\n📝 First 5 segments:")
            print("-" * 50)
            for i, segment in enumerate(segment_list[:5]):
                print(f"[{i+1}] {segment.start:.2f}s - {segment.end:.2f}s")
                print(f"    Text: {segment.text}")
            print("-" * 50)

            # Test our engine wrapper
            print("\n🔧 Testing FasterWhisperEngine wrapper...")
            from deeplecture.transcription.faster_whisper_engine import FasterWhisperEngine

            engine = FasterWhisperEngine(
                model_size="tiny",
                device="cpu",
                compute_type="int8"
            )

            output_srt = "outputs/test_e2e/simple_test.srt"
            os.makedirs("outputs/test_e2e", exist_ok=True)

            # Temporarily disable VAD in the engine
            print("Transcribing through engine (without VAD)...")
            success = engine.generate_subtitles(
                video_path=video_file,
                output_path=output_srt,
                language="en"
            )

            if success and os.path.exists(output_srt):
                with open(output_srt, 'r', encoding='utf-8') as f:
                    content = f.read()

                if content:
                    lines = content.split('\n')
                    print(f"\n✅ Engine generated {len(lines)} lines of SRT")
                    print("\nFirst 20 lines of SRT:")
                    print("-" * 50)
                    for line in lines[:20]:
                        print(line)
                    print("-" * 50)
                else:
                    print("❌ Engine generated empty SRT file")
            else:
                print("❌ Engine failed to generate SRT")
        else:
            print("\n❌ No segments detected!")
            print("\nTrying with different settings...")

            # Try without specifying language
            print("\nTranscribing with auto-detect language...")
            segments, info = model.transcribe(
                video_file,
                vad_filter=False,
                beam_size=5,
            )

            segment_list = list(segments)
            print(f"Segments with auto-detect: {len(segment_list)}")

            if len(segment_list) > 0:
                print(f"Detected language: {info.language}")
                for i, segment in enumerate(segment_list[:3]):
                    print(f"  [{i+1}] {segment.text}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = test_simple_transcription()

    if success:
        print("\n" + "=" * 70)
        print("🎉 Simple test completed!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ Simple test failed")
        print("=" * 70)

    sys.exit(0 if success else 1)