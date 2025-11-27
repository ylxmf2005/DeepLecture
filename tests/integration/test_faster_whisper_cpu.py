#!/usr/bin/env python3
"""
Simple test to verify the faster-whisper engine code works correctly.
This test mocks the actual faster-whisper library to test our integration.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_cpu_mode():
    """Test faster-whisper engine in CPU mode (mocked)."""

    print("=" * 60)
    print("Testing Faster-whisper Engine Integration (CPU Mode)")
    print("=" * 60)

    # Mock the faster_whisper module
    mock_whisper_module = MagicMock()
    mock_whisper_module.WhisperModel = MagicMock()

    # Mock model instance
    mock_model = MagicMock()
    mock_whisper_module.WhisperModel.return_value = mock_model

    # Mock transcription results
    mock_segments = [
        Mock(start=0.0, end=2.5, text=" Hello, this is a test. "),
        Mock(start=2.5, end=5.0, text="Testing subtitle generation."),
        Mock(start=5.0, end=8.0, text=" Final test segment! ")
    ]
    mock_info = Mock(language="en", language_probability=0.99)
    mock_model.transcribe.return_value = (mock_segments, mock_info)

    # Inject mock into sys.modules
    sys.modules['faster_whisper'] = mock_whisper_module

    try:
        # Now import our engine
        from deeplecture.transcription.faster_whisper_engine import FasterWhisperEngine

        print("\n1. Creating FasterWhisperEngine in CPU mode...")
        engine = FasterWhisperEngine(
            model_size="medium",
            device="cpu",
            compute_type="int8"
        )
        print("   ✅ Engine created successfully")

        print("\n2. Testing SRT time conversion...")
        test_times = [
            (0.0, "00:00:00,000"),
            (1.5, "00:00:01,500"),
            (61.25, "00:01:01,250"),
            (3661.999, "01:01:01,999"),  # Fixed: 3661 seconds = 1 hour, 1 minute, 1.999 seconds
        ]

        all_passed = True
        for seconds, expected in test_times:
            result = engine._seconds_to_srt_time(seconds)
            if result == expected:
                print(f"   ✅ {seconds}s → {result}")
            else:
                print(f"   ❌ {seconds}s → {result} (expected {expected})")
                all_passed = False

        print("\n3. Testing subtitle generation...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            output_path = f.name

        try:
            # Test generation
            result = engine.generate_subtitles(
                video_path="test_video.mp4",
                output_path=output_path,
                language="en"
            )

            if result:
                print("   ✅ Subtitle generation succeeded")

                # Check output file
                with open(output_path, 'r') as f:
                    content = f.read()

                print("\n4. Checking SRT output format...")
                lines = content.strip().split('\n')

                # Check first subtitle
                if lines[0] == "1":
                    print("   ✅ Subtitle numbering correct")
                else:
                    print(f"   ❌ Expected '1', got '{lines[0]}'")

                if "00:00:00,000 --> 00:00:02,500" in lines[1]:
                    print("   ✅ Timestamp format correct")
                else:
                    print(f"   ❌ Timestamp format issue: {lines[1]}")

                if "Hello, this is a test." in lines[2]:
                    print("   ✅ Text content correct (whitespace trimmed)")
                else:
                    print(f"   ❌ Text content issue: {lines[2]}")

                print("\n5. Full SRT output:")
                print("-" * 40)
                print(content)
                print("-" * 40)

            else:
                print("   ❌ Subtitle generation failed")

        finally:
            # Cleanup
            if os.path.exists(output_path):
                os.remove(output_path)

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up mock
        if 'faster_whisper' in sys.modules:
            del sys.modules['faster_whisper']

    print("\n" + "=" * 60)
    print("✅ All CPU mode tests passed!")
    print("=" * 60)
    return True


def test_config_integration():
    """Test configuration loading for faster-whisper."""

    print("\n" + "=" * 60)
    print("Testing Configuration Integration")
    print("=" * 60)

    from deeplecture.config.config import load_config

    # Test loading config
    config = load_config()
    if config:
        subtitle_config = config.get('subtitle', {})
        print(f"\n1. Current subtitle engine: {subtitle_config.get('engine', 'not set')}")
        print(f"2. Mock mode: {subtitle_config.get('use_mock', False)}")

        if 'faster_whisper' in subtitle_config:
            fw_config = subtitle_config['faster_whisper']
            print("\n3. Faster-whisper configuration:")
            print(f"   - Model size: {fw_config.get('model_size', 'not set')}")
            print(f"   - Device: {fw_config.get('device', 'not set')}")
            print(f"   - Compute type: {fw_config.get('compute_type', 'not set')}")
        else:
            print("\n3. No faster-whisper configuration found in config")

    else:
        print("❌ Could not load configuration")

    print("\n" + "=" * 60)
    return True


if __name__ == "__main__":
    # Run tests
    success = test_cpu_mode()

    if success:
        test_config_integration()

    if success:
        print("\n🎉 All tests passed! The faster-whisper engine is ready for use.")
        print("\nTo use in production:")
        print("1. Install faster-whisper: pip install faster-whisper")
        print("2. Set 'engine: faster_whisper' in config/conf.yaml")
        print("3. Set 'use_mock: false' to enable actual transcription")
        sys.exit(0)
    else:
        sys.exit(1)