"""Tests for LLM provider implementations.

Tests the LLMProvider protocol and its implementations:
- MockProvider: Returns static suggestions based on naming convention
- OpenAIProvider: OpenAI/Azure OpenAI integration
- GoogleProvider: Google Gemini integration
- get_provider: Factory function for provider selection

Test Cases:
- TC-LP-001: MockProvider returns correct suggestions for snake_case
- TC-LP-002: MockProvider returns correct suggestions for each naming convention
- TC-LP-003: MockProvider.supports_images() returns True
- TC-LP-004: GoogleProvider.supports_images() returns False
- TC-LP-005: get_provider returns MockProvider when config has default_provider="mock"
- TC-LP-006: get_provider returns OpenAIProvider when config has default_provider="openai"
- TC-LP-007: get_provider returns GoogleProvider when config has default_provider="google"
- TC-LP-008: get_provider raises RuntimeError for unsupported provider
- TC-LP-009: OpenAIProvider.supports_images() returns True
"""

import pytest

from onomatool.llm_integration import (
    GoogleProvider,
    MockProvider,
    OpenAIProvider,
    get_provider,
)


class TestMockProvider:
    """Tests for MockProvider implementation."""

    def test_mock_provider_snake_case(self):
        """TC-LP-001: Test MockProvider returns correct suggestions for snake_case."""
        provider = MockProvider(naming_convention="snake_case")

        suggestions = provider.get_suggestions(
            messages=[],
            pydantic_model=object,
            json_schema={},
            model="mock",
            verbose_level=0,
        )

        assert suggestions == ["mock_file_one", "mock_file_two", "mock_file_three"]
        assert all("_" in s for s in suggestions)
        assert len(suggestions) == 3

    def test_mock_provider_all_naming_conventions(self):
        """TC-LP-002: Test MockProvider returns correct suggestions for each naming convention."""
        test_cases = [
            (
                "snake_case",
                ["mock_file_one", "mock_file_two", "mock_file_three"],
                "_",
            ),
            ("camelCase", ["mockFileOne", "mockFileTwo", "mockFileThree"], None),
            (
                "kebab-case",
                ["mock-file-one", "mock-file-two", "mock-file-three"],
                "-",
            ),
            ("PascalCase", ["MockFileOne", "MockFileTwo", "MockFileThree"], None),
            (
                "dot.notation",
                ["mock.file.one", "mock.file.two", "mock.file.three"],
                ".",
            ),
            (
                "natural language",
                ["Mock File One", "Mock File Two", "Mock File Three"],
                " ",
            ),
        ]

        for convention, expected, separator in test_cases:
            provider = MockProvider(naming_convention=convention)

            suggestions = provider.get_suggestions(
                messages=[],
                pydantic_model=object,
                json_schema={},
                model="mock",
                verbose_level=0,
            )

            assert suggestions == expected, f"Failed for {convention}"
            assert len(suggestions) == 3
            if separator:
                assert all(separator in s for s in suggestions)

    def test_mock_provider_unknown_convention_defaults_to_snake_case(self):
        """Test MockProvider defaults to snake_case for unknown conventions."""
        provider = MockProvider(naming_convention="unknown_convention")

        suggestions = provider.get_suggestions(
            messages=[],
            pydantic_model=object,
            json_schema={},
            model="mock",
            verbose_level=0,
        )

        # Should fall back to snake_case
        assert suggestions == ["mock_file_one", "mock_file_two", "mock_file_three"]

    def test_mock_provider_supports_images(self):
        """TC-LP-003: Test MockProvider.supports_images() returns True."""
        provider = MockProvider()

        assert provider.supports_images() is True


class TestOpenAIProvider:
    """Tests for OpenAIProvider implementation."""

    def test_openai_provider_instantiation(self):
        """Test OpenAIProvider can be instantiated with config."""
        config = {
            "openai_api_key": "test-key",
            "openai_base_url": "https://api.openai.com/v1",
        }

        provider = OpenAIProvider(config)

        assert provider.config == config
        assert isinstance(provider, OpenAIProvider)

    def test_openai_provider_supports_images(self):
        """TC-LP-009: Test OpenAIProvider.supports_images() returns True."""
        config = {"openai_api_key": "test-key"}
        provider = OpenAIProvider(config)

        assert provider.supports_images() is True

    def test_openai_provider_azure_instantiation(self):
        """Test OpenAIProvider can be instantiated with Azure config."""
        config = {
            "use_azure_openai": True,
            "azure_openai_endpoint": "https://test.openai.azure.com/",
            "azure_openai_api_key": "test-key",
            "azure_openai_deployment": "gpt-4",
            "azure_openai_api_version": "2024-02-01",
        }

        provider = OpenAIProvider(config)

        assert provider.config == config
        assert isinstance(provider, OpenAIProvider)


class TestGoogleProvider:
    """Tests for GoogleProvider implementation."""

    def test_google_provider_instantiation(self):
        """Test GoogleProvider can be instantiated with config."""
        config = {"google_api_key": "test-key"}

        provider = GoogleProvider(config)

        assert provider.config == config
        assert isinstance(provider, GoogleProvider)

    def test_google_provider_supports_images(self):
        """TC-LP-004: Test GoogleProvider.supports_images() returns True."""
        config = {"google_api_key": "test-key"}
        provider = GoogleProvider(config)

        assert provider.supports_images() is True


class TestGetProvider:
    """Tests for get_provider factory function."""

    def test_get_provider_mock(self):
        """TC-LP-005: Test get_provider returns MockProvider when config has default_provider="mock"."""
        config = {
            "default_provider": "mock",
            "naming_convention": "snake_case",
        }

        provider = get_provider(config)

        assert isinstance(provider, MockProvider)
        assert provider.naming_convention == "snake_case"

    def test_get_provider_openai(self):
        """TC-LP-006: Test get_provider returns OpenAIProvider when config has default_provider="openai"."""
        config = {
            "default_provider": "openai",
            "openai_api_key": "test-key",
        }

        provider = get_provider(config)

        assert isinstance(provider, OpenAIProvider)
        assert provider.config == config

    def test_get_provider_google(self):
        """TC-LP-007: Test get_provider returns GoogleProvider when config has default_provider="google"."""
        config = {
            "default_provider": "google",
            "google_api_key": "test-key",
        }

        provider = get_provider(config)

        assert isinstance(provider, GoogleProvider)
        assert provider.config == config

    def test_get_provider_unsupported_raises_error(self):
        """TC-LP-008: Test get_provider raises RuntimeError for unsupported provider."""
        config = {"default_provider": "unsupported_provider"}

        with pytest.raises(
            RuntimeError, match="Unsupported provider: unsupported_provider"
        ):
            get_provider(config)

    def test_get_provider_defaults_to_openai(self):
        """Test get_provider defaults to OpenAI when no provider specified."""
        config = {}

        provider = get_provider(config)

        # Should default to openai
        assert isinstance(provider, OpenAIProvider)

    def test_get_provider_mock_with_different_conventions(self):
        """Test get_provider creates MockProvider with correct naming convention."""
        conventions = ["snake_case", "camelCase", "kebab-case", "PascalCase"]

        for convention in conventions:
            config = {
                "default_provider": "mock",
                "naming_convention": convention,
            }

            provider = get_provider(config)

            assert isinstance(provider, MockProvider)
            assert provider.naming_convention == convention
