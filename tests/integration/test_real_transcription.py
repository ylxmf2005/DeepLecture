#!/usr/bin/env python3
"""
Real-world test for faster-whisper with actual audio file.
This test requires faster-whisper to be installed.

Usage:
    # First install faster-whisper
    pip install faster-whisper

    # Then run this test with an audio/video file
    python tests/test_real_transcription.py your_video.mp4
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_test_audio():
    """Create a simple test audio file using text-to-speech."""

    print("Creating test audio file...")

    # Try to use system TTS to create a test file
    test_text = "Hello, this is a test of DeepLecture. It works great on Windows."
    test_audio_path = "test_audio.wav"

    # macOS: use 'say' command
    if sys.platform == "darwin":
        os.system(f'say "{test_text}" -o {test_audio_path}')
        if os.path.exists(test_audio_path):
            # Convert to proper format
            os.system(f'ffmpeg -i {test_audio_path} -ar 16000 -ac 1 -y test_audio_16k.wav 2>/dev/null')
            if os.path.exists("test_audio_16k.wav"):
                os.rename("test_audio_16k.wav", test_audio_path)
            return test_audio_path

    # Windows: use SAPI
    elif sys.platform == "win32":
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            # This would need additional code to save to file
            print("Windows TTS detected but file save not implemented")
        except:
            pass

    # Linux: use espeak
    elif sys.platform.startswith("linux"):
        os.system(f'espeak "{test_text}" -w {test_audio_path} 2>/dev/null')
        if os.path.exists(test_audio_path):
            return test_audio_path

    print("Could not create test audio automatically.")
    return None


def test_real_transcription(audio_file=None):
    """Test faster-whisper with a real audio file."""

    print("=" * 60)
    print("Real-World Faster-whisper Test")
    print("=" * 60)

    # Check if faster-whisper is installed
    try:
        import faster_whisper
        print(f"✅ faster-whisper is installed (version {faster_whisper.__version__})")
    except ImportError:
        print("❌ faster-whisper is not installed!")
        print("\nTo install:")
        print("  pip install faster-whisper")
        print("\nFor GPU support:")
        print("  pip install faster-whisper torch nvidia-cublas-cu12")
        return False

    # Check for GPU
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✅ GPU available: {torch.cuda.get_device_name(0)}")
            device = "cuda"
            compute_type = "float16"
        else:
            print("ℹ️ No GPU detected, using CPU")
            device = "cpu"
            compute_type = "int8"
    except ImportError:
        print("ℹ️ PyTorch not installed, using CPU")
        device = "cpu"
        compute_type = "int8"

    # Get or create test audio
    if audio_file and os.path.exists(audio_file):
        test_audio = audio_file
        print(f"\n📁 Using provided file: {test_audio}")
    else:
        test_audio = create_test_audio()
        if not test_audio:
            print("\n⚠️ No audio file available for testing.")
            print("Please provide an audio/video file:")
            print("  python tests/test_real_transcription.py your_file.mp4")
            return False

    # Test our integration
    print("\n🎯 Testing our FasterWhisperEngine...")

    from deeplecture.transcription.faster_whisper_engine import FasterWhisperEngine

    engine = FasterWhisperEngine(
        model_size="tiny",  # Use tiny for quick testing
        device=device,
        compute_type=compute_type
    )

    output_srt = "test_output.srt"

    print(f"\n⏳ Transcribing (this may take a moment)...")
    print(f"   Model: tiny")
    print(f"   Device: {device}")
    print(f"   Compute type: {compute_type}")

    start_time = time.time()

    try:
        success = engine.generate_subtitles(
            video_path=test_audio,
            output_path=output_srt,
            language=None  # Auto-detect
        )

        elapsed = time.time() - start_time

        if success:
            print(f"\n✅ Transcription completed in {elapsed:.2f} seconds")

            # Show the output
            if os.path.exists(output_srt):
                with open(output_srt, 'r', encoding='utf-8') as f:
                    content = f.read()

                lines = content.strip().split('\n')
                print(f"\n📝 Generated {len([l for l in lines if l and not l[0].isdigit() and '-->' not in l])} subtitle segments")

                print("\n📄 First few subtitles:")
                print("-" * 40)
                for line in lines[:20]:  # Show first few entries
                    print(line)
                if len(lines) > 20:
                    print("...")
                print("-" * 40)

                # Cleanup
                os.remove(output_srt)
                if audio_file is None and test_audio and os.path.exists(test_audio):
                    os.remove(test_audio)

            else:
                print("❌ Output file was not created")
                return False

        else:
            print(f"❌ Transcription failed after {elapsed:.2f} seconds")
            return False

    except Exception as e:
        print(f"\n❌ Error during transcription: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("🎉 Real transcription test passed!")
    print("=" * 60)

    return True


def test_performance_comparison():
    """Compare performance of different model sizes."""

    print("\n" + "=" * 60)
    print("Performance Comparison (if you have test audio)")
    print("=" * 60)

    print("\nModel size vs Speed/Accuracy trade-off:")
    print("  tiny    - Fastest, least accurate (~39 MB)")
    print("  base    - Fast, reasonable accuracy (~74 MB)")
    print("  small   - Balanced (~244 MB)")
    print("  medium  - Slower, good accuracy (~769 MB)")
    print("  large   - Slowest, best accuracy (~1550 MB)")

    print("\nRecommended for different use cases:")
    print("  Development/Testing: tiny or base")
    print("  Production (speed priority): small")
    print("  Production (quality priority): medium or large")
    print("  GPU available: large-v3 with float16")


if __name__ == "__main__":
    audio_file = sys.argv[1] if len(sys.argv) > 1 else None

    success = test_real_transcription(audio_file)

    if success:
        test_performance_comparison()

    sys.exit(0 if success else 1)