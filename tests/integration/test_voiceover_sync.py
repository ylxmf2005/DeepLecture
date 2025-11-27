import os
import shutil
import unittest
from unittest.mock import MagicMock
from deeplecture.transcription.voiceover import SubtitleVoiceoverGenerator, SubtitleSegment

class TestVoiceoverSync(unittest.TestCase):
    def setUp(self):
        self.output_dir = "tests/output_test_sync"
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir)

    def tearDown(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_drift_correction(self):
        # Subclass to mock ffmpeg interactions without touching real TTS/ffmpeg.
        class MockGenerator(SubtitleVoiceoverGenerator):
            def __init__(self):
                self.durations = {}

            def _generate_silence_wav(self, output_file: str, duration: float) -> None:
                with open(output_file, "w") as f:
                    f.write("silence")
                self.durations[output_file] = duration

            def _adjust_audio_duration(self, input_file, output_file, target_duration, work_dir):
                actual_duration = target_duration - 0.05  # 50ms short
                if actual_duration < 0:
                    actual_duration = 0

                with open(output_file, "w") as f:
                    f.write("adjusted")

                self.durations[output_file] = actual_duration
                return 0.0, actual_duration

        generator = MockGenerator()

        # Override _get_audio_duration to use the durations map.
        def get_duration(path):
            return generator.durations.get(path, 1.0)  # Default 1s if not found
        generator._get_audio_duration = get_duration

        # Create segments:
        # Segment 1: 0.0 - 1.0 (Target 1.0s) -> Actual 0.95s (Drift -0.05s)
        # Segment 2: 1.0 - 2.0 (Target 1.0s) -> Start at 1.0, but track is at 0.95. Drift = 1.0 - 0.95 = 0.05s.
        # Should trigger correction.
        
        segments = [
            SubtitleSegment(index=1, start=0.0, end=1.0, text="One"),
            SubtitleSegment(index=2, start=1.0, end=2.0, text="Two"),
        ]
        
        # Mock TTS to produce dummy files
        generator.tts = MagicMock()
        generator.tts.synthesize.return_value = b"audio"

        # Create dummy input wavs
        segments_dir = os.path.join(self.output_dir, "test_segments")
        os.makedirs(segments_dir)
        for i in range(len(segments)):
            with open(os.path.join(segments_dir, f"subtitle_{i+1}.wav"), "wb") as f:
                f.write(b"audio")

        audio_files = generator._build_aligned_segment_files(segments, segments_dir)
        
        drift_files = [f for f in audio_files if "drift" in f]
        print(f"Generated audio files: {audio_files}")
        
        self.assertTrue(len(drift_files) > 0, "Drift correction silence should have been generated")
        
        # Verify the drift file is for the second segment (index 1 in loop, so drift_2.wav?)
        # The code uses f"drift_{i + 1}.wav". For i=1 (Segment 2), it should be drift_2.wav.
        self.assertTrue(any("drift_2.wav" in f for f in drift_files))

if __name__ == "__main__":
    unittest.main()
