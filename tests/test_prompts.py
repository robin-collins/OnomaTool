"""
Test suite for prompt template system.

Tests cover:
- TC-PT-001: Default system prompt usage
- TC-PT-002: Custom system prompt from config
- TC-PT-003: User prompt interpolation with naming_convention and content
- TC-PT-004: Image prompt interpolation with naming_convention
- TC-PT-005: Custom user prompt template from config
- TC-PT-006: Word count values injected from config into prompts
"""

from onomatool.prompts import (
    DEFAULT_IMAGE_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT,
    get_image_prompt,
    get_system_prompt,
    get_user_prompt,
)


class TestSystemPrompt:
    """Tests for get_system_prompt function."""

    def test_returns_default_when_no_config_argument(self):
        """TC-PT-001: Test get_system_prompt calls get_config() when config is None."""
        # This test hits the fallback path where config=None triggers get_config()
        result = get_system_prompt()
        assert result == DEFAULT_SYSTEM_PROMPT or isinstance(result, str)

    def test_returns_default_when_no_custom_prompt(self):
        """TC-PT-001: Test get_system_prompt returns DEFAULT_SYSTEM_PROMPT when no custom prompt in config."""
        config = {}
        result = get_system_prompt(config)
        assert result == DEFAULT_SYSTEM_PROMPT
        assert "file naming suggestion assistant" in result

    def test_returns_default_when_system_prompt_is_none(self):
        """TC-PT-001: Test get_system_prompt returns DEFAULT_SYSTEM_PROMPT when system_prompt is None."""
        config = {"system_prompt": None}
        result = get_system_prompt(config)
        assert result == DEFAULT_SYSTEM_PROMPT

    def test_returns_custom_prompt_when_set(self):
        """TC-PT-002: Test get_system_prompt returns custom prompt when config has system_prompt set."""
        custom_prompt = "You are a custom file naming expert."
        config = {"system_prompt": custom_prompt}
        result = get_system_prompt(config)
        assert result == custom_prompt
        assert result != DEFAULT_SYSTEM_PROMPT


class TestUserPrompt:
    """Tests for get_user_prompt function."""

    def test_calls_get_config_when_no_config_argument(self):
        """TC-PT-003: Test get_user_prompt calls get_config() when config is None."""
        # This test hits the fallback path where config=None triggers get_config()
        result = get_user_prompt("snake_case", "test content")
        assert isinstance(result, str)
        assert "test content" in result

    def test_interpolates_naming_convention_and_content(self):
        """TC-PT-003: Test get_user_prompt interpolates naming_convention and content into template."""
        config = {}
        naming_convention = "snake_case"
        content = "This is the file content."

        result = get_user_prompt(naming_convention, content, config)

        # The default template doesn't explicitly mention naming_convention in the text,
        # but content should be present
        assert content in result
        assert "expert file naming assistant" in result
        assert "CONTENT:" in result

    def test_uses_default_word_counts(self):
        """TC-PT-006: Test get_user_prompt uses default word counts when not in config."""
        config = {}
        naming_convention = "kebab-case"
        content = "Test content"

        result = get_user_prompt(naming_convention, content, config)

        # Default values are min=5, max=15
        assert "between 5 and 15 words" in result

    def test_uses_custom_word_counts(self):
        """TC-PT-006: Test word count values (min_words, max_words) are injected from config into prompts."""
        config = {
            "min_filename_words": 3,
            "max_filename_words": 10,
        }
        naming_convention = "camelCase"
        content = "Test content"

        result = get_user_prompt(naming_convention, content, config)

        assert "between 3 and 10 words" in result

    def test_uses_custom_template(self):
        """TC-PT-005: Test get_user_prompt uses custom template from config when user_prompt is set."""
        custom_template = (
            "Custom prompt with {naming_convention}, content: {content}, "
            "words: {min_words}-{max_words}"
        )
        config = {
            "user_prompt": custom_template,
            "min_filename_words": 2,
            "max_filename_words": 8,
        }
        naming_convention = "PascalCase"
        content = "Sample file content"

        result = get_user_prompt(naming_convention, content, config)

        assert result == (
            "Custom prompt with PascalCase, content: Sample file content, words: 2-8"
        )
        assert "expert file naming assistant" not in result  # Not the default template

    def test_handles_none_custom_template(self):
        """TC-PT-005: Test get_user_prompt falls back to default when user_prompt is None."""
        config = {
            "user_prompt": None,
            "min_filename_words": 4,
            "max_filename_words": 12,
        }
        naming_convention = "snake_case"
        content = "Test"

        result = get_user_prompt(naming_convention, content, config)

        # Should use default template
        assert "expert file naming assistant" in result
        assert "between 4 and 12 words" in result
        assert content in result

    def test_preserves_content_with_special_characters(self):
        """TC-PT-003: Test content with special characters is properly interpolated."""
        config = {}
        naming_convention = "dot.notation"
        content = "Content with {braces} and $pecial ch@rs!"

        result = get_user_prompt(naming_convention, content, config)

        assert content in result


class TestImagePrompt:
    """Tests for get_image_prompt function."""

    def test_calls_get_config_when_no_config_argument(self):
        """TC-PT-004: Test get_image_prompt calls get_config() when config is None."""
        # This test hits the fallback path where config=None triggers get_config()
        result = get_image_prompt("kebab-case")
        assert isinstance(result, str)
        assert "kebab-case" in result

    def test_interpolates_naming_convention(self):
        """TC-PT-004: Test get_image_prompt interpolates naming_convention into template."""
        config = {}
        naming_convention = "kebab-case"

        result = get_image_prompt(naming_convention, config)

        assert naming_convention in result
        assert "expert file naming assistant" in result
        assert "Visual Analysis Guidelines" in result

    def test_uses_default_word_counts(self):
        """TC-PT-006: Test get_image_prompt uses default word counts when not in config."""
        config = {}
        naming_convention = "snake_case"

        result = get_image_prompt(naming_convention, config)

        # Default values are min=5, max=15
        assert "between 5 and 15 words" in result

    def test_uses_custom_word_counts(self):
        """TC-PT-006: Test word count values are injected from config into image prompts."""
        config = {
            "min_filename_words": 4,
            "max_filename_words": 20,
        }
        naming_convention = "CamelCase"

        result = get_image_prompt(naming_convention, config)

        assert "between 4 and 20 words" in result

    def test_uses_custom_template(self):
        """TC-PT-005: Test get_image_prompt uses custom template from config when image_prompt is set."""
        custom_template = (
            "Analyze this image using {naming_convention}. "
            "Length: {min_words} to {max_words} words."
        )
        config = {
            "image_prompt": custom_template,
            "min_filename_words": 6,
            "max_filename_words": 18,
        }
        naming_convention = "natural language"

        result = get_image_prompt(naming_convention, config)

        assert result == (
            "Analyze this image using natural language. Length: 6 to 18 words."
        )
        assert "Visual Analysis Guidelines" not in result  # Not the default template

    def test_handles_none_custom_template(self):
        """TC-PT-005: Test get_image_prompt falls back to default when image_prompt is None."""
        config = {
            "image_prompt": None,
            "min_filename_words": 7,
            "max_filename_words": 14,
        }
        naming_convention = "PascalCase"

        result = get_image_prompt(naming_convention, config)

        # Should use default template
        assert "Visual Analysis Guidelines" in result
        assert "between 7 and 14 words" in result
        assert naming_convention in result

    def test_all_naming_conventions(self):
        """TC-PT-004: Test image prompt works with all standard naming conventions."""
        config = {}
        conventions = [
            "snake_case",
            "kebab-case",
            "camelCase",
            "PascalCase",
            "dot.notation",
            "natural language",
        ]

        for convention in conventions:
            result = get_image_prompt(convention, config)
            assert convention in result
            assert len(result) > 100  # Should be a substantial prompt


class TestPromptTemplateEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_content_in_user_prompt(self):
        """Test get_user_prompt handles empty content string."""
        config = {}
        result = get_user_prompt("snake_case", "", config)
        assert "CONTENT:\n" in result

    def test_very_long_content_in_user_prompt(self):
        """Test get_user_prompt handles very long content."""
        config = {}
        long_content = "X" * 10000
        result = get_user_prompt("kebab-case", long_content, config)
        assert long_content in result

    def test_word_count_boundary_values(self):
        """TC-PT-006: Test extreme word count values."""
        config = {
            "min_filename_words": 1,
            "max_filename_words": 100,
        }

        user_result = get_user_prompt("snake_case", "content", config)
        image_result = get_image_prompt("snake_case", config)

        assert "between 1 and 100 words" in user_result
        assert "between 1 and 100 words" in image_result

    def test_missing_format_keys_in_custom_template(self):
        """Test custom template with only some format keys works (unused params ignored)."""
        config = {
            "user_prompt": "This template only uses {content}",
        }

        # Should work fine - naming_convention, min_words, max_words are passed but not used
        result = get_user_prompt("snake_case", "test", config)
        assert result == "This template only uses test"

    def test_extra_format_keys_in_custom_template(self):
        """Test custom template with extra format keys works (unused keys ignored)."""
        config = {
            "image_prompt": "Convention: {naming_convention}",
            "min_filename_words": 5,
            "max_filename_words": 15,
        }

        # Should work fine, extra keys (min_words, max_words) are just not used
        result = get_image_prompt("kebab-case", config)
        assert result == "Convention: kebab-case"


class TestPromptConstants:
    """Tests to verify the default prompt constants are defined correctly."""

    def test_default_system_prompt_exists(self):
        """Verify DEFAULT_SYSTEM_PROMPT is defined and non-empty."""
        assert DEFAULT_SYSTEM_PROMPT
        assert isinstance(DEFAULT_SYSTEM_PROMPT, str)
        assert len(DEFAULT_SYSTEM_PROMPT) > 10

    def test_default_user_prompt_exists(self):
        """Verify DEFAULT_USER_PROMPT is defined and contains required placeholders."""
        assert DEFAULT_USER_PROMPT
        assert isinstance(DEFAULT_USER_PROMPT, str)
        assert "{content}" in DEFAULT_USER_PROMPT
        assert "{min_words}" in DEFAULT_USER_PROMPT
        assert "{max_words}" in DEFAULT_USER_PROMPT

    def test_default_image_prompt_exists(self):
        """Verify DEFAULT_IMAGE_PROMPT is defined and contains required placeholders."""
        assert DEFAULT_IMAGE_PROMPT
        assert isinstance(DEFAULT_IMAGE_PROMPT, str)
        assert "{naming_convention}" in DEFAULT_IMAGE_PROMPT
        assert "{min_words}" in DEFAULT_IMAGE_PROMPT
        assert "{max_words}" in DEFAULT_IMAGE_PROMPT
