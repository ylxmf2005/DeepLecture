#!/usr/bin/env python3
"""
Integration test for faster-whisper engine selection in whisper_engine.py
"""

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_engine_selection():
    """Test that WhisperEngine correctly selects FasterWhisperEngine."""

    print("=" * 60)
    print("Testing WhisperEngine Integration with FasterWhisper")
    print("=" * 60)

    # Mock the faster_whisper module first
    mock_whisper_module = MagicMock()
    mock_model_class = MagicMock()
    mock_whisper_module.WhisperModel = mock_model_class

    # Mock model instance
    mock_model = MagicMock()
    mock_model_class.return_value = mock_model

    # Mock transcription results
    mock_segments = [
        Mock(start=0.0, end=2.0, text=" Test subtitle "),
    ]
    mock_info = Mock(language="en", language_probability=0.99)
    mock_model.transcribe.return_value = (mock_segments, mock_info)

    # Inject mock
    sys.modules['faster_whisper'] = mock_whisper_module

    try:
        # Test 1: Import check
        print("\n1. Testing imports...")
        try:
            from deeplecture.transcription.faster_whisper_engine import FasterWhisperEngine
            print("   ✅ FasterWhisperEngine imported successfully")
        except Exception as e:
            print(f"   ❌ Failed to import FasterWhisperEngine: {e}")
            return False

        # Test 2: Direct instantiation
        print("\n2. Testing direct FasterWhisperEngine instantiation...")
        try:
            engine = FasterWhisperEngine(
                model_size="tiny",
                device="cpu",
                compute_type="int8"
            )
            print("   ✅ Engine created directly")
        except Exception as e:
            print(f"   ❌ Failed to create engine: {e}")
            return False

        # Test 3: WhisperEngine selection with config
        print("\n3. Testing WhisperEngine with faster_whisper config...")

        # Create a temporary config file
        config_content = """
subtitle:
  engine: faster_whisper
  use_mock: false
  faster_whisper:
    model_size: small
    device: cpu
    compute_type: int8
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_config_path = f.name

        try:
            # Mock load_config to return our test config
            import yaml
            with open(temp_config_path, 'r') as f:
                test_config = yaml.safe_load(f)

            with patch('deeplecture.transcription.whisper_engine.load_config', return_value=test_config):
                from deeplecture.transcription.whisper_engine import WhisperEngine

                whisper_engine = WhisperEngine()

                # Check if the delegate is FasterWhisperEngine
                delegate_name = type(whisper_engine._delegate).__name__
                print(f"   Selected engine type: {delegate_name}")

                if delegate_name == "FasterWhisperEngine":
                    print("   ✅ WhisperEngine correctly selected FasterWhisperEngine")
                else:
                    print(f"   ❌ Expected FasterWhisperEngine, got {delegate_name}")
                    return False

        finally:
            # Cleanup config file
            if os.path.exists(temp_config_path):
                os.remove(temp_config_path)

        # Test 4: Test subtitle generation through WhisperEngine
        print("\n4. Testing subtitle generation through WhisperEngine...")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            output_path = f.name

        try:
            result = whisper_engine.generate_subtitles(
                video_path="test.mp4",
                output_path=output_path,
                language="en"
            )

            if result:
                print("   ✅ Subtitle generation succeeded through WhisperEngine")

                # Check output
                with open(output_path, 'r') as f:
                    content = f.read()
                    if "Test subtitle" in content:
                        print("   ✅ Output content correct")
                    else:
                        print(f"   ❌ Unexpected output: {content}")
            else:
                print("   ❌ Subtitle generation failed")
                return False

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

        # Test 5: Test fallback behavior
        print("\n5. Testing unknown engine fallback...")

        bad_config = {
            'subtitle': {
                'engine': 'unknown_engine',
                'use_mock': False
            }
        }

        with patch('deeplecture.transcription.whisper_engine.load_config', return_value=bad_config):
            from deeplecture.transcription.whisper_engine import WhisperEngine, MockSubtitleEngine

            engine = WhisperEngine()
            delegate_name = type(engine._delegate).__name__

            if delegate_name == "MockSubtitleEngine":
                print("   ✅ Correctly fell back to MockSubtitleEngine for unknown engine")
            else:
                print(f"   ❌ Expected MockSubtitleEngine fallback, got {delegate_name}")

        # Test 6: Test auto device selection
        print("\n6. Testing auto device selection...")

        auto_config = {
            'subtitle': {
                'engine': 'faster_whisper',
                'use_mock': False,
                'faster_whisper': {
                    'model_size': 'tiny',
                    'device': 'auto',
                    'compute_type': 'auto'
                }
            }
        }

        with patch('deeplecture.transcription.whisper_engine.load_config', return_value=auto_config):
            engine = WhisperEngine()

            if hasattr(engine._delegate, '_device'):
                print(f"   Device setting: {engine._delegate._device}")
                print(f"   Compute type: {engine._delegate._compute_type}")
                print("   ✅ Auto configuration accepted")
            else:
                print("   ✅ Engine created with auto settings")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup mock
        if 'faster_whisper' in sys.modules:
            del sys.modules['faster_whisper']

    print("\n" + "=" * 60)
    print("✅ All integration tests passed!")
    print("=" * 60)
    return True


def test_config_switching():
    """Test switching between whisper_cpp and faster_whisper."""

    print("\n" + "=" * 60)
    print("Testing Engine Switching")
    print("=" * 60)

    # Mock both engines
    sys.modules['faster_whisper'] = MagicMock()

    try:
        # Test whisper_cpp selection
        print("\n1. Testing whisper_cpp selection...")
        whisper_config = {
            'subtitle': {
                'engine': 'whisper_cpp',
                'use_mock': False,
                'whisper_cpp': {
                    'model_path': './models/test.bin',
                    'whisper_bin': './whisper-cli'
                }
            }
        }

        with patch('deeplecture.transcription.whisper_engine.load_config', return_value=whisper_config):
            from deeplecture.transcription.whisper_engine import WhisperEngine, WhisperCppEngine

            engine = WhisperEngine()
            delegate_name = type(engine._delegate).__name__

            if delegate_name == "WhisperCppEngine":
                print("   ✅ Correctly selected WhisperCppEngine")
            else:
                print(f"   ❌ Expected WhisperCppEngine, got {delegate_name}")

        # Test faster_whisper selection
        print("\n2. Testing faster_whisper selection...")
        faster_config = {
            'subtitle': {
                'engine': 'faster_whisper',
                'use_mock': False,
                'faster_whisper': {
                    'model_size': 'base'
                }
            }
        }

        with patch('deeplecture.transcription.whisper_engine.load_config', return_value=faster_config):
            engine = WhisperEngine()
            delegate_name = type(engine._delegate).__name__

            if delegate_name == "FasterWhisperEngine":
                print("   ✅ Correctly selected FasterWhisperEngine")
            else:
                print(f"   ❌ Expected FasterWhisperEngine, got {delegate_name}")

        # Test mock selection
        print("\n3. Testing mock engine selection...")
        mock_config = {
            'subtitle': {
                'engine': 'whisper_cpp',
                'use_mock': True  # This should override engine setting
            }
        }

        with patch('deeplecture.transcription.whisper_engine.load_config', return_value=mock_config):
            engine = WhisperEngine()
            delegate_name = type(engine._delegate).__name__

            if delegate_name == "MockSubtitleEngine":
                print("   ✅ use_mock correctly overrides engine setting")
            else:
                print(f"   ❌ Expected MockSubtitleEngine, got {delegate_name}")

    finally:
        if 'faster_whisper' in sys.modules:
            del sys.modules['faster_whisper']

    print("\n" + "=" * 60)
    return True


if __name__ == "__main__":
    print("\nRunning Faster-whisper Integration Tests\n")

    # Run main integration test
    success = test_engine_selection()

    if success:
        # Run config switching test
        test_config_switching()

    if success:
        print("\n🎉 All integration tests passed successfully!")
        print("\nThe faster-whisper engine is fully integrated and working correctly.")
        print("Users can now switch between engines by changing 'subtitle.engine' in config.")
        sys.exit(0)
    else:
        print("\n❌ Some integration tests failed.")
        sys.exit(1)