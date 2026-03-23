"""Tests for Google Gemini image/vision support.

TEST_SPECS §19.1: 3 tests TC-GV-001 to TC-GV-003.
- Image files use Gemini vision path
- Non-image files use text-only path
- GoogleProvider.supports_images() returns True after update
"""

from unittest.mock import patch

from onomatool.llm_integration import GoogleProvider, get_suggestions


class TestGeminiVision:
    """Tests for Gemini vision/image support."""

    def test_image_files_use_gemini_vision_path(self, tmp_path):
        """TC-GV-001: Image files routed through vision path with base64 image data.

        When get_suggestions is called with an image file_path and google provider,
        the messages should contain image_url content for vision processing.
        """
        # Create a small test image (1x1 PNG)
        import base64

        # Minimal valid PNG (1x1 pixel, red)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "nGP4z8BQDwAEgAF/pooBPQAAAABJRU5ErkJggg=="
        )
        image_file = tmp_path / "test_image.png"
        image_file.write_bytes(png_data)

        config = {
            "default_provider": "google",
            "google_api_key": "test-key",
            "naming_convention": "snake_case",
            "llm_model": "gemini-2.0-flash",
            "max_retries": 0,
            "retry_delay": 1.0,
            "rate_limit_delay": 0.0,
        }

        # Mock GoogleProvider.get_suggestions to capture the messages
        captured_messages = []

        def mock_get_suggestions(
            messages, pydantic_model, json_schema, model, verbose_level
        ):
            captured_messages.extend(messages)
            return ["test_image_one", "test_image_two", "test_image_three"]

        with patch.object(
            GoogleProvider, "get_suggestions", side_effect=mock_get_suggestions
        ):
            result = get_suggestions(
                content="",
                file_path=str(image_file),
                config=config,
            )

        assert len(result) == 3
        # Messages should contain image_url content (vision path)
        assert len(captured_messages) == 1
        msg = captured_messages[0]
        assert msg["role"] == "user"
        assert isinstance(msg["content"], list)
        content_types = [item["type"] for item in msg["content"]]
        assert "image_url" in content_types
        assert "text" in content_types

    def test_non_image_files_use_text_only_path(self, tmp_path):
        """TC-GV-002: Non-image files use text-only messages without image data.

        When get_suggestions is called with a non-image file_path and google provider,
        the messages should NOT contain image_url content.
        """
        text_file = tmp_path / "document.txt"
        text_file.write_text("Some document content")

        config = {
            "default_provider": "google",
            "google_api_key": "test-key",
            "naming_convention": "snake_case",
            "llm_model": "gemini-2.0-flash",
            "max_retries": 0,
            "retry_delay": 1.0,
            "rate_limit_delay": 0.0,
        }

        captured_messages = []

        def mock_get_suggestions(
            messages, pydantic_model, json_schema, model, verbose_level
        ):
            captured_messages.extend(messages)
            return [
                "document_summary_one",
                "document_summary_two",
                "document_summary_three",
            ]

        with patch.object(
            GoogleProvider, "get_suggestions", side_effect=mock_get_suggestions
        ):
            result = get_suggestions(
                content="Some document content",
                file_path=str(text_file),
                config=config,
            )

        assert len(result) == 3
        # Messages should be text-only (system + user), no image_url
        assert len(captured_messages) == 2
        for msg in captured_messages:
            assert isinstance(msg["content"], str), (
                f"Expected string content for text file, got {type(msg['content'])}"
            )

    def test_google_provider_supports_images(self):
        """TC-GV-003: GoogleProvider.supports_images() returns True.

        After the vision update, GoogleProvider should report image support.
        """
        config = {"google_api_key": "test-key"}
        provider = GoogleProvider(config)

        assert provider.supports_images() is True
