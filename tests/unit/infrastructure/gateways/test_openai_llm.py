"""Unit tests for OpenAI LLM gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path


class TestOpenAILLMImageValidation:
    """Tests for image path validation in OpenAI LLM."""

    @pytest.fixture
    def llm(self):
        """Create OpenAILLM instance with mocked client."""
        with patch("openai.OpenAI"):
            from deeplecture.infrastructure.gateways.openai import OpenAILLM

            return OpenAILLM(api_key="test-key")

    @pytest.fixture
    def llm_with_roots(self, test_data_dir: Path):
        """Create OpenAILLM with allowed roots."""
        with patch("openai.OpenAI"):
            from deeplecture.infrastructure.gateways.openai import OpenAILLM

            return OpenAILLM(
                api_key="test-key",
                allowed_image_roots=frozenset([test_data_dir]),
            )

    @pytest.mark.unit
    def test_http_url_passthrough(self, llm) -> None:
        """HTTP URLs should pass through unchanged."""
        result = llm._encode_image("http://example.com/image.jpg")
        assert result == "http://example.com/image.jpg"

    @pytest.mark.unit
    def test_https_url_passthrough(self, llm) -> None:
        """HTTPS URLs should pass through unchanged."""
        result = llm._encode_image("https://example.com/image.png")
        assert result == "https://example.com/image.png"

    @pytest.mark.unit
    def test_path_traversal_rejected(self, llm) -> None:
        """Path traversal attempts should be rejected."""
        with pytest.raises(ValueError, match="traversal"):
            llm._encode_image("../../../etc/passwd.jpg")

    @pytest.mark.unit
    def test_invalid_extension_rejected(self, llm) -> None:
        """Non-image extensions should be rejected."""
        with pytest.raises(ValueError, match="Invalid image extension"):
            llm._encode_image("/tmp/malware.exe")

    @pytest.mark.unit
    def test_valid_extensions_accepted(self, llm, test_data_dir: Path) -> None:
        """Valid image extensions should be accepted."""
        # Create test image file
        test_image = test_data_dir / "test.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake png data")

        result = llm._encode_image(str(test_image))
        assert result.startswith("data:image/png;base64,")

    @pytest.mark.unit
    def test_jpeg_extension(self, llm, test_data_dir: Path) -> None:
        """JPEG extension should be accepted."""
        test_image = test_data_dir / "test.jpeg"
        test_image.write_bytes(b"\xff\xd8\xff" + b"fake jpeg data")

        result = llm._encode_image(str(test_image))
        assert result.startswith("data:image/jpeg;base64,")

    @pytest.mark.unit
    def test_file_not_found(self, llm) -> None:
        """Non-existent file should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            llm._encode_image("/nonexistent/path/image.jpg")

    @pytest.mark.unit
    def test_path_outside_allowed_roots(self, llm_with_roots, test_data_dir: Path) -> None:
        """Path outside allowed roots should be rejected."""
        # Create a file outside allowed roots to test the validation
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff" + b"fake jpeg")
            temp_path = f.name

        try:
            # This file exists but is outside allowed roots (test_data_dir)
            with pytest.raises(ValueError, match="not in allowed"):
                llm_with_roots._encode_image(temp_path)
        finally:
            import os

            os.unlink(temp_path)


class TestOpenAILLMMessageBuilding:
    """Tests for message building logic."""

    @pytest.fixture
    def llm(self):
        """Create OpenAILLM instance with mocked client."""
        with patch("openai.OpenAI"):
            from deeplecture.infrastructure.gateways.openai import OpenAILLM

            return OpenAILLM(api_key="test-key")

    @pytest.mark.unit
    def test_basic_message(self, llm) -> None:
        """Basic prompt should create user message."""
        messages = llm._build_messages("Hello, AI!")

        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    @pytest.mark.unit
    def test_with_system_prompt(self, llm) -> None:
        """System prompt should be added first."""
        messages = llm._build_messages("Hello", system_prompt="You are a helper")

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helper"
        assert messages[1]["role"] == "user"

    @pytest.mark.unit
    def test_text_content_format(self, llm) -> None:
        """User content should be formatted correctly."""
        messages = llm._build_messages("Test prompt")

        user_content = messages[0]["content"]
        assert isinstance(user_content, list)
        assert user_content[0]["type"] == "text"
        assert user_content[0]["text"] == "Test prompt"


class TestOpenAILLMInit:
    """Tests for OpenAILLM initialization."""

    @pytest.mark.unit
    def test_default_model(self) -> None:
        """Default model should be gpt-4o."""
        with patch("openai.OpenAI"):
            from deeplecture.infrastructure.gateways.openai import OpenAILLM

            llm = OpenAILLM(api_key="test")
            assert llm._model == "gpt-4o"

    @pytest.mark.unit
    def test_custom_model(self) -> None:
        """Custom model should be accepted."""
        with patch("openai.OpenAI"):
            from deeplecture.infrastructure.gateways.openai import OpenAILLM

            llm = OpenAILLM(api_key="test", model="gpt-3.5-turbo")
            assert llm._model == "gpt-3.5-turbo"

    @pytest.mark.unit
    def test_default_temperature(self) -> None:
        """Default temperature should be 0.7."""
        with patch("openai.OpenAI"):
            from deeplecture.infrastructure.gateways.openai import OpenAILLM

            llm = OpenAILLM(api_key="test")
            assert llm._temperature == 0.7

    @pytest.mark.unit
    def test_custom_temperature(self) -> None:
        """Custom temperature should be accepted."""
        with patch("openai.OpenAI"):
            from deeplecture.infrastructure.gateways.openai import OpenAILLM

            llm = OpenAILLM(api_key="test", temperature=0.2)
            assert llm._temperature == 0.2

    @pytest.mark.unit
    def test_base_url_passed_to_client(self) -> None:
        """Custom base_url should be passed to OpenAI client."""
        # Must patch where the class is imported, not where it's defined
        with patch("deeplecture.infrastructure.gateways.openai.OpenAI") as mock_openai:
            from deeplecture.infrastructure.gateways.openai import OpenAILLM

            OpenAILLM(api_key="test", base_url="https://custom.api.com")

            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["base_url"] == "https://custom.api.com"
