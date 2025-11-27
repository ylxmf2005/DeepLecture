import json
import unittest
from unittest.mock import MagicMock

from deeplecture.transcription.enhance_translator import SubtitleEnhanceTranslator
from deeplecture.transcription.interactive import SubtitleSegment


class TestSubtitleEnhanceTranslator(unittest.TestCase):
    def setUp(self):
        self.mock_llm = MagicMock()
        self.translator = SubtitleEnhanceTranslator(self.mock_llm)

    def test_build_background(self):
        segments = [
            SubtitleSegment(1, 0.0, 1.0, "Hello world"),
            SubtitleSegment(2, 1.0, 2.0, "This is a test"),
        ]
        
        # Mock LLM response for background extraction
        self.mock_llm.generate_response.return_value = json.dumps({
            "topic": "Test Topic",
            "summary": "Test Summary",
            "keywords": ["test", "world"],
            "tone": "neutral"
        })

        background = self.translator.build_background(segments)
        
        self.assertEqual(background["topic"], "Test Topic")
        self.assertEqual(background["keywords"], ["test", "world"])

    def test_process_batch(self):
        segments = [
            SubtitleSegment(1, 0.0, 1.0, "Hello"),
            SubtitleSegment(2, 1.0, 2.0, "world"),
        ]
        background = {"topic": "Test"}
        
        # Mock LLM response for enhance & translate
        # The prompt expects start_index/end_index to be 1-based relative to the batch
        self.mock_llm.generate_response.return_value = json.dumps({
            "subtitles": [
                {
                    "start_index": 1,
                    "end_index": 2,
                    "text_en": "Hello world.",
                    "text_zh": "Hello world (translated)."
                }
            ]
        })

        processed = self.translator._process_batch(segments, background, "zh")
        
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0]["text_en"], "Hello world.")
        self.assertEqual(processed[0]["text_zh"], "Hello world (translated).")
        self.assertEqual(processed[0]["start"], 0.0)
        self.assertEqual(processed[0]["end"], 2.0)

    def test_reconstruct_srt(self):
        entries = [
            {
                "start": 0.0,
                "end": 2.0,
                "text_en": "Hello world.",
                "text_zh": "Hello world (translated)."
            }
        ]

        srt_content = self.translator._reconstruct_srt(entries)

        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:02,000\n"
            "Hello world.\n"
        )
        # Note: The actual output might have an extra newline at the end
        self.assertEqual(srt_content.strip(), expected.strip())

    def test_fallback_batch_includes_error_message(self):
        """Fallback should include error reason in text_zh, not empty string."""
        segments = [
            SubtitleSegment(1, 0.0, 1.0, "Hello"),
            SubtitleSegment(2, 1.0, 2.0, "world"),
        ]
        exc = RuntimeError("API rate limit exceeded")

        result = self.translator._fallback_batch(segments, exc)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text_en"], "Hello")
        self.assertIn("Translation failed", result[0]["text_zh"])
        self.assertIn("rate limit", result[0]["text_zh"])

if __name__ == "__main__":
    unittest.main()
