"""Tests for LLM integration module.

Tests the main llm_integration functions including get_suggestions,
utility functions, and provider integration.

Test Cases:
- TC-LI-001: Test get_suggestions with mock provider returns 3 suggestions for snake_case
- TC-LI-002: Test get_suggestions with mock provider and different naming conventions
- TC-LI-003: Test is_image_file returns True for .jpg, .png, .webp, .gif, .bmp, .svg
- TC-LI-004: Test is_image_file returns False for .txt, .pdf, .docx
- TC-LI-005: Test get_pydantic_model_and_schema returns tuple for valid convention
- TC-LI-006: Test get_pydantic_model_and_schema falls back to snake_case for invalid convention
- TC-LI-007: Test encode_image_base64 encodes a file correctly (create a small test file)
- TC-LI-008: Test get_suggestions raises RuntimeError for SVG file_path (SVG guard)
- TC-LI-009: Test content truncation - get_suggestions should handle content longer than MAX_CONTENT_CHARS
- TC-LI-010: Test get_provider factory returns correct types
- TC-LI-011: Test unsupported provider raises RuntimeError
"""

import base64

import pytest

from onomatool.llm_integration import (
    MAX_CONTENT_CHARS,
    GoogleProvider,
    MockProvider,
    OpenAIProvider,
    encode_image_base64,
    get_provider,
    get_pydantic_model_and_schema,
    get_suggestions,
    is_image_file,
)
from onomatool.models import (
    CamelCaseFilenameSuggestions,
    DotNotationFilenameSuggestions,
    KebabCaseFilenameSuggestions,
    NaturalLanguageFilenameSuggestions,
    PascalCaseFilenameSuggestions,
    SnakeCaseFilenameSuggestions,
)


class TestGetSuggestions:
    """Tests for get_suggestions function."""

    def test_get_suggestions_mock_provider_snake_case(self):
        """TC-LI-001: Test get_suggestions with mock provider returns 3 suggestions for snake_case."""
        config = {
            "default_provider": "mock",
            "naming_convention": "snake_case",
        }

        suggestions = get_suggestions(
            content="This is test content for a file.",
            verbose_level=0,
            config=config,
        )

        assert len(suggestions) == 3
        assert suggestions == ["mock_file_one", "mock_file_two", "mock_file_three"]
        assert all(isinstance(s, str) for s in suggestions)
        assert all("_" in s for s in suggestions)

    def test_get_suggestions_mock_provider_different_conventions(self):
        """TC-LI-002: Test get_suggestions with mock provider and different naming conventions."""
        test_cases = [
            ("snake_case", ["mock_file_one", "mock_file_two", "mock_file_three"]),
            ("camelCase", ["mockFileOne", "mockFileTwo", "mockFileThree"]),
            ("kebab-case", ["mock-file-one", "mock-file-two", "mock-file-three"]),
            ("PascalCase", ["MockFileOne", "MockFileTwo", "MockFileThree"]),
            ("dot.notation", ["mock.file.one", "mock.file.two", "mock.file.three"]),
            ("natural language", ["Mock File One", "Mock File Two", "Mock File Three"]),
        ]

        for convention, expected in test_cases:
            config = {
                "default_provider": "mock",
                "naming_convention": convention,
            }

            suggestions = get_suggestions(
                content="Test content",
                verbose_level=0,
                config=config,
            )

            assert suggestions == expected, f"Failed for {convention}"
            assert len(suggestions) == 3

    def test_get_suggestions_raises_for_svg_file(self):
        """TC-LI-008: Test get_suggestions raises RuntimeError for SVG file_path (SVG guard)."""
        config = {
            "default_provider": "mock",
            "naming_convention": "snake_case",
        }

        with pytest.raises(
            RuntimeError,
            match="Raw SVG files must not be sent to the LLM. Convert to PNG first.",
        ):
            get_suggestions(
                content="<svg>...</svg>",
                verbose_level=0,
                file_path="/test/file.svg",
                config=config,
            )

    def test_get_suggestions_content_truncation(self, caplog):
        """TC-LI-009: Test content truncation - get_suggestions should handle content longer than MAX_CONTENT_CHARS."""
        import logging

        # Set log level to DEBUG to capture debug messages
        caplog.set_level(logging.DEBUG)

        config = {
            "default_provider": "mock",
            "naming_convention": "snake_case",
        }

        # Create content longer than MAX_CONTENT_CHARS
        long_content = "x" * (MAX_CONTENT_CHARS + 10000)

        suggestions = get_suggestions(
            content=long_content,
            verbose_level=1,  # Enable verbose to see truncation message
            config=config,
        )

        # Should still return suggestions
        assert len(suggestions) == 3
        assert suggestions == ["mock_file_one", "mock_file_two", "mock_file_three"]

        # Check that truncation was logged
        assert "Content truncated" in caplog.text


class TestIsImageFile:
    """Tests for is_image_file function."""

    def test_is_image_file_returns_true_for_image_extensions(self):
        """TC-LI-003: Test is_image_file returns True for .jpg, .png, .webp, .gif, .bmp, .svg."""
        image_extensions = [
            "/path/to/file.jpg",
            "/path/to/file.JPG",
            "/path/to/file.jpeg",
            "/path/to/file.JPEG",
            "/path/to/file.png",
            "/path/to/file.PNG",
            "/path/to/file.webp",
            "/path/to/file.WEBP",
            "/path/to/file.gif",
            "/path/to/file.GIF",
            "/path/to/file.bmp",
            "/path/to/file.BMP",
            "/path/to/file.svg",
            "/path/to/file.SVG",
        ]

        for file_path in image_extensions:
            assert is_image_file(file_path) is True, f"Failed for {file_path}"

    def test_is_image_file_returns_false_for_non_image_extensions(self):
        """TC-LI-004: Test is_image_file returns False for .txt, .pdf, .docx."""
        non_image_extensions = [
            "/path/to/file.txt",
            "/path/to/file.TXT",
            "/path/to/file.pdf",
            "/path/to/file.PDF",
            "/path/to/file.docx",
            "/path/to/file.DOCX",
            "/path/to/file.md",
            "/path/to/file.json",
            "/path/to/file.py",
            "/path/to/file",  # No extension
        ]

        for file_path in non_image_extensions:
            assert is_image_file(file_path) is False, f"Should be False for {file_path}"


class TestGetPydanticModelAndSchema:
    """Tests for get_pydantic_model_and_schema function."""

    def test_get_pydantic_model_and_schema_valid_conventions(self):
        """TC-LI-005: Test get_pydantic_model_and_schema returns tuple for valid convention."""
        test_cases = [
            ("snake_case", SnakeCaseFilenameSuggestions),
            ("camelCase", CamelCaseFilenameSuggestions),
            ("kebab-case", KebabCaseFilenameSuggestions),
            ("PascalCase", PascalCaseFilenameSuggestions),
            ("dot.notation", DotNotationFilenameSuggestions),
            ("natural language", NaturalLanguageFilenameSuggestions),
        ]

        for convention, expected_model in test_cases:
            model, schema = get_pydantic_model_and_schema(convention)

            assert model == expected_model, f"Failed for {convention}"
            assert isinstance(schema, dict)
            assert "type" in schema
            assert schema["type"] == "json_schema"
            assert "json_schema" in schema
            assert "schema" in schema["json_schema"]

    def test_get_pydantic_model_and_schema_fallback_to_snake_case(self):
        """TC-LI-006: Test get_pydantic_model_and_schema falls back to snake_case for invalid convention."""
        invalid_conventions = [
            "invalid_convention",
            "unknown",
            "UPPERCASE",
            "",
        ]

        for convention in invalid_conventions:
            model, schema = get_pydantic_model_and_schema(convention)

            # Should fall back to snake_case
            assert model == SnakeCaseFilenameSuggestions
            assert isinstance(schema, dict)
            assert "type" in schema


class TestEncodeImageBase64:
    """Tests for encode_image_base64 function."""

    def test_encode_image_base64_encodes_correctly(self, tmp_path):
        """TC-LI-007: Test encode_image_base64 encodes a file correctly (create a small test file)."""
        # Create a small test image file
        test_image_path = tmp_path / "test_image.png"
        test_image_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00"  # PNG header
        )

        test_image_path.write_bytes(test_image_content)

        # Encode the image
        encoded = encode_image_base64(str(test_image_path))

        # Verify it's a valid base64 string
        assert isinstance(encoded, str)
        assert len(encoded) > 0

        # Verify it decodes back to original content
        decoded = base64.b64decode(encoded)
        assert decoded == test_image_content

    def test_encode_image_base64_handles_different_file_sizes(self, tmp_path):
        """Test encode_image_base64 handles various file sizes."""
        test_cases = [
            (b"small", "small.png"),
            (b"x" * 100, "medium.png"),
            (b"y" * 1000, "large.png"),
        ]

        for content, filename in test_cases:
            file_path = tmp_path / filename
            file_path.write_bytes(content)

            encoded = encode_image_base64(str(file_path))

            # Verify encoding/decoding round-trip
            assert base64.b64decode(encoded) == content


class TestGetProvider:
    """Tests for get_provider factory function."""

    def test_get_provider_returns_correct_types(self):
        """TC-LI-010: Test get_provider factory returns correct types."""
        test_cases = [
            ({"default_provider": "mock"}, MockProvider),
            ({"default_provider": "openai"}, OpenAIProvider),
            ({"default_provider": "google"}, GoogleProvider),
        ]

        for config, expected_type in test_cases:
            provider = get_provider(config)
            assert isinstance(provider, expected_type), (
                f"Failed for {config['default_provider']}"
            )

    def test_get_provider_unsupported_raises_runtime_error(self):
        """TC-LI-011: Test unsupported provider raises RuntimeError."""
        config = {"default_provider": "unsupported_provider"}

        with pytest.raises(
            RuntimeError, match="Unsupported provider: unsupported_provider"
        ):
            get_provider(config)

    def test_get_provider_defaults_to_openai(self):
        """Test get_provider defaults to openai when no provider specified."""
        config = {}

        provider = get_provider(config)

        assert isinstance(provider, OpenAIProvider)


class TestGetSuggestionsWithImages:
    """Tests for get_suggestions with image file paths."""

    def test_get_suggestions_with_png_image(self, tmp_path):
        """Test get_suggestions processes PNG images correctly."""
        # Create a small PNG file
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n")

        config = {
            "default_provider": "mock",
            "naming_convention": "snake_case",
        }

        suggestions = get_suggestions(
            content="",  # Content ignored for images
            verbose_level=0,
            file_path=str(test_image),
            config=config,
        )

        assert len(suggestions) == 3
        assert all(isinstance(s, str) for s in suggestions)

    def test_get_suggestions_with_jpg_image(self, tmp_path):
        """Test get_suggestions processes JPG images correctly."""
        # Create a small JPG file
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"\xff\xd8\xff")  # JPEG header

        config = {
            "default_provider": "mock",
            "naming_convention": "kebab-case",
        }

        suggestions = get_suggestions(
            content="",
            verbose_level=0,
            file_path=str(test_image),
            config=config,
        )

        assert len(suggestions) == 3
        assert suggestions == ["mock-file-one", "mock-file-two", "mock-file-three"]
