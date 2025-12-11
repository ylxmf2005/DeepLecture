import os
import shutil
import unittest

from deeplecture.transcription.voiceover import SubtitleSegment, SubtitleVoiceoverGenerator


class TestVoiceoverSync(unittest.TestCase):
    def setUp(self):
        self.output_dir = "tests/output_test_sync"
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir)

    def tearDown(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_segment_alignment(self):
        """Test that segment alignment produces correct timing with video speed-up."""
        # Subclass to mock ffmpeg interactions without touching real TTS/ffmpeg.
        class MockGenerator(SubtitleVoiceoverGenerator):
            def __init__(self):
                self.durations = {}
                self.sample_rate = 44100
                self.silence_threshold = 1.0
                self.max_speed_factor = 2.5
                self._speed_buckets = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]

            def _generate_silence_wav(self, output_file: str, duration: float) -> None:
                with open(output_file, "w") as f:
                    f.write("silence")
                self.durations[output_file] = duration

            def _pad_audio_to_duration(self, input_file, output_file, target_duration, work_dir):
                with open(output_file, "w") as f:
                    f.write("padded")
                self.durations[output_file] = target_duration

            def _speed_up_audio(self, input_file, output_file, speed, target_duration, work_dir):
                with open(output_file, "w") as f:
                    f.write("sped_up")
                self.durations[output_file] = target_duration

        generator = MockGenerator()

        # Override _get_audio_duration to use the durations map.
        def get_duration(path):
            return generator.durations.get(path, 0.8)  # Default 0.8s (shorter than 1s slot)
        generator._get_audio_duration = get_duration

        # Create segments with 1s slots each
        segments = [
            SubtitleSegment(index=1, start=0.0, end=1.0, text="One"),
            SubtitleSegment(index=2, start=1.0, end=2.0, text="Two"),
        ]

        # Create dummy input wavs
        segments_dir = os.path.join(self.output_dir, "test_segments")
        os.makedirs(segments_dir)
        for i in range(len(segments)):
            path = os.path.join(segments_dir, f"subtitle_{i+1}.wav")
            with open(path, "wb") as f:
                f.write(b"audio")
            generator.durations[path] = 0.8  # TTS produces 0.8s audio for 1s slot

        audio_files, segment_timings = generator._build_aligned_segments(
            segments, segments_dir, video_duration=2.0
        )

        # Should have 2 adjusted audio files (one per segment)
        adjusted_files = [f for f in audio_files if "adjusted_" in f]
        self.assertEqual(len(adjusted_files), 2, "Should have 2 adjusted audio files")

        # Should have 2 segment timings
        self.assertEqual(len(segment_timings), 2, "Should have 2 segment timings")

        # Verify segment timings track source and output correctly
        self.assertEqual(segment_timings[0].src_start, 0.0)
        self.assertEqual(segment_timings[0].src_end, 1.0)
        self.assertEqual(segment_timings[1].src_start, 1.0)
        self.assertEqual(segment_timings[1].src_end, 2.0)

    def test_video_speedup_threshold(self):
        """Test that video speed-up is triggered when gap exceeds threshold."""
        class MockGenerator(SubtitleVoiceoverGenerator):
            def __init__(self):
                self.durations = {}
                self.sample_rate = 44100
                self.silence_threshold = 0.5  # Low threshold to trigger speed-up
                self.max_speed_factor = 2.5
                self._speed_buckets = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]

            def _generate_silence_wav(self, output_file: str, duration: float) -> None:
                with open(output_file, "w") as f:
                    f.write("silence")
                self.durations[output_file] = duration

            def _pad_audio_to_duration(self, input_file, output_file, target_duration, work_dir):
                with open(output_file, "w") as f:
                    f.write("padded")
                self.durations[output_file] = target_duration

            def _speed_up_audio(self, input_file, output_file, speed, target_duration, work_dir):
                with open(output_file, "w") as f:
                    f.write("sped_up")
                self.durations[output_file] = target_duration

        generator = MockGenerator()

        def get_duration(path):
            return generator.durations.get(path, 1.0)
        generator._get_audio_duration = get_duration

        # Segment with 2s slot but TTS only produces 1s audio
        # Gap = 1s > threshold 0.5s, should trigger video speed-up
        segments = [
            SubtitleSegment(index=1, start=0.0, end=2.0, text="One"),
        ]

        segments_dir = os.path.join(self.output_dir, "test_segments")
        os.makedirs(segments_dir)
        path = os.path.join(segments_dir, "subtitle_1.wav")
        with open(path, "wb") as f:
            f.write(b"audio")
        generator.durations[path] = 1.0  # TTS produces 1s for 2s slot

        audio_files, segment_timings = generator._build_aligned_segments(
            segments, segments_dir, video_duration=2.0
        )

        # Gap = 2.0 - 1.0 = 1.0s > threshold 0.5s
        # Required speed = 2.0 / 1.0 = 2.0x
        self.assertEqual(len(segment_timings), 1)
        self.assertGreater(segment_timings[0].speed, 1.0, "Should trigger video speed-up")
        self.assertAlmostEqual(segment_timings[0].speed, 2.0, places=1)

    def test_leading_silence(self):
        """Test that leading silence is generated when first subtitle doesn't start at 0."""
        class MockGenerator(SubtitleVoiceoverGenerator):
            def __init__(self):
                self.durations = {}
                self.sample_rate = 44100
                self.silence_threshold = 1.0
                self.max_speed_factor = 2.5
                self._speed_buckets = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5]

            def _generate_silence_wav(self, output_file: str, duration: float) -> None:
                with open(output_file, "w") as f:
                    f.write("silence")
                self.durations[output_file] = duration

            def _pad_audio_to_duration(self, input_file, output_file, target_duration, work_dir):
                with open(output_file, "w") as f:
                    f.write("padded")
                self.durations[output_file] = target_duration

            def _speed_up_audio(self, input_file, output_file, speed, target_duration, work_dir):
                with open(output_file, "w") as f:
                    f.write("sped_up")
                self.durations[output_file] = target_duration

        generator = MockGenerator()

        def get_duration(path):
            return generator.durations.get(path, 1.0)
        generator._get_audio_duration = get_duration

        # First subtitle starts at 1.0s, not 0
        segments = [
            SubtitleSegment(index=1, start=1.0, end=2.0, text="One"),
        ]

        segments_dir = os.path.join(self.output_dir, "test_segments")
        os.makedirs(segments_dir)
        path = os.path.join(segments_dir, "subtitle_1.wav")
        with open(path, "wb") as f:
            f.write(b"audio")
        generator.durations[path] = 1.0

        audio_files, segment_timings = generator._build_aligned_segments(
            segments, segments_dir, video_duration=2.0
        )

        # Should have leading silence + 1 subtitle segment = 2 segments
        silence_files = [f for f in audio_files if "silence_0" in f]
        self.assertEqual(len(silence_files), 1, "Should have leading silence")

        # Should have 2 segment timings (leading + subtitle)
        self.assertEqual(len(segment_timings), 2)
        self.assertEqual(segment_timings[0].src_start, 0.0)
        self.assertEqual(segment_timings[0].src_end, 1.0)
        self.assertEqual(segment_timings[1].src_start, 1.0)
        self.assertEqual(segment_timings[1].src_end, 2.0)


if __name__ == "__main__":
    unittest.main()
