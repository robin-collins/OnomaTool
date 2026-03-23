"""
Test suite for config versioning functionality.

Tests cover:
- TC-CV-001: Current version loads cleanly
- TC-CV-002: Old version auto-migrates
- TC-CV-003: Future version loads with best-effort
- TC-CV-004: Missing config_version treated as version 1
"""

import tempfile
from pathlib import Path

import pytest
import tomli_w

from onomatool.config import (
    CURRENT_CONFIG_VERSION,
    OnomatoolConfig,
    _migrate_config,
    get_config,
)


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".toml", delete=False
    ) as tmp:
        yield Path(tmp.name)
    # Cleanup
    Path(tmp.name).unlink(missing_ok=True)


def write_config(path: Path, config_dict: dict):
    """Write a config dictionary to a TOML file."""
    with open(path, "wb") as f:
        tomli_w.dump(config_dict, f)


class TestConfigVersioning:
    """Test suite for config versioning."""

    def test_tc_cv_001_current_version_loads_cleanly(self, temp_config_file):
        """TC-CV-001: Config with config_version = 1 (CURRENT_CONFIG_VERSION) loads without migration."""
        config = {
            "config_version": CURRENT_CONFIG_VERSION,
            "default_provider": "openai",
            "openai_api_key": "test-key-123",
            "naming_convention": "snake_case",
            "llm_model": "gpt-4o",
            "min_filename_words": 5,
            "max_filename_words": 15,
        }
        write_config(temp_config_file, config)

        loaded = get_config(str(temp_config_file))

        assert loaded["config_version"] == CURRENT_CONFIG_VERSION
        assert loaded["openai_api_key"] == "test-key-123"
        assert loaded["default_provider"] == "openai"
        assert loaded["naming_convention"] == "snake_case"

    def test_tc_cv_002_old_version_auto_migrates(self, temp_config_file, caplog):
        """TC-CV-002: Config without config_version gets version added."""
        # Create a config WITHOUT config_version key (simulating old config)
        config = {
            "default_provider": "google",
            "google_api_key": "old-api-key",
            "naming_convention": "kebab-case",
            "llm_model": "gemini-pro",
        }
        write_config(temp_config_file, config)

        loaded = get_config(str(temp_config_file))

        # Should be auto-migrated to current version (defaults to 1, same as current)
        assert loaded["config_version"] == CURRENT_CONFIG_VERSION
        assert loaded["google_api_key"] == "old-api-key"
        assert loaded["default_provider"] == "google"
        assert loaded["naming_convention"] == "kebab-case"

        # Note: Since missing config_version defaults to 1 (which equals CURRENT_CONFIG_VERSION),
        # no migration log is expected in the current implementation

    def test_tc_cv_003_future_version_loads_with_best_effort(self, temp_config_file):
        """TC-CV-003: Config with config_version = 99 loads fine (no downgrade needed)."""
        config = {
            "config_version": 99,  # Future version
            "default_provider": "openai",
            "openai_api_key": "future-key",
            "naming_convention": "PascalCase",
            "llm_model": "gpt-5o",  # Hypothetical future model
            "min_filename_words": 3,
            "max_filename_words": 20,
        }
        write_config(temp_config_file, config)

        loaded = get_config(str(temp_config_file))

        # Should load without error, keeping the future version
        assert loaded["config_version"] == 99
        assert loaded["openai_api_key"] == "future-key"
        assert loaded["naming_convention"] == "PascalCase"
        assert loaded["llm_model"] == "gpt-5o"

    def test_tc_cv_004_missing_config_version_treated_as_version_1(
        self, temp_config_file
    ):
        """TC-CV-004: Config with no config_version key treated as v1."""
        config = {
            # No config_version key
            "default_provider": "openai",
            "openai_api_key": "legacy-key",
            "naming_convention": "camelCase",
        }
        write_config(temp_config_file, config)

        loaded = get_config(str(temp_config_file))

        # Should be treated as v1 and migrated to current
        assert loaded["config_version"] == CURRENT_CONFIG_VERSION
        assert loaded["openai_api_key"] == "legacy-key"
        assert loaded["naming_convention"] == "camelCase"

    def test_migration_from_version_0(self, temp_config_file, caplog):
        """Test that a config with version 0 gets migrated to current version."""
        import logging

        # Set up logging to capture from onomatool.config
        caplog.set_level(logging.INFO, logger="onomatool.config")

        config = {
            "config_version": 0,  # Old version that needs migration
            "default_provider": "openai",
            "openai_api_key": "v0-key",
            "naming_convention": "snake_case",
        }
        write_config(temp_config_file, config)

        loaded = get_config(str(temp_config_file))

        # Should be migrated to current version
        assert loaded["config_version"] == CURRENT_CONFIG_VERSION
        assert loaded["openai_api_key"] == "v0-key"

        # Check that migration was logged
        assert "Migrated config from version 0 to" in caplog.text

    def test_migrate_config_function_directly(self):
        """Test _migrate_config function directly with various inputs."""
        # Test with no version (defaults to 1, equals CURRENT_CONFIG_VERSION, no migration)
        raw = {"default_provider": "openai"}
        migrated = _migrate_config(raw)
        # Since version defaults to 1 and CURRENT_CONFIG_VERSION is 1, returns unchanged
        # The Pydantic model will add the default config_version when validating
        assert "default_provider" in migrated

        # Test with current version (should not change)
        raw = {"config_version": CURRENT_CONFIG_VERSION, "default_provider": "google"}
        migrated = _migrate_config(raw)
        assert migrated["config_version"] == CURRENT_CONFIG_VERSION
        assert migrated["default_provider"] == "google"

        # Test with future version (should not change)
        raw = {"config_version": 100, "default_provider": "openai"}
        migrated = _migrate_config(raw)
        assert migrated["config_version"] == 100

    def test_migrate_config_preserves_all_fields(self):
        """Test that migration preserves all existing fields."""
        raw = {
            # No config_version
            "default_provider": "google",
            "google_api_key": "key123",
            "openai_api_key": "key456",
            "naming_convention": "snake_case",
            "llm_model": "gemini-1.5-pro",
            "min_filename_words": 3,
            "max_filename_words": 12,
            "system_prompt": "Custom system prompt",
            "user_prompt": "Custom user prompt",
            "max_retries": 5,
            "retry_delay": 2.0,
        }
        migrated = _migrate_config(raw)

        # All fields should be preserved
        assert migrated["default_provider"] == "google"
        assert migrated["google_api_key"] == "key123"
        assert migrated["openai_api_key"] == "key456"
        assert migrated["naming_convention"] == "snake_case"
        assert migrated["llm_model"] == "gemini-1.5-pro"
        assert migrated["min_filename_words"] == 3
        assert migrated["max_filename_words"] == 12
        assert migrated["system_prompt"] == "Custom system prompt"
        assert migrated["user_prompt"] == "Custom user prompt"
        assert migrated["max_retries"] == 5
        assert migrated["retry_delay"] == 2.0

    def test_pydantic_model_accepts_current_version(self):
        """Test that OnomatoolConfig Pydantic model accepts current version."""
        config = OnomatoolConfig(
            config_version=CURRENT_CONFIG_VERSION,
            openai_api_key="test-key",
        )
        assert config.config_version == CURRENT_CONFIG_VERSION

    def test_pydantic_model_accepts_future_version(self):
        """Test that OnomatoolConfig Pydantic model accepts future versions."""
        config = OnomatoolConfig(
            config_version=999,
            openai_api_key="test-key",
        )
        assert config.config_version == 999

    def test_pydantic_model_defaults_to_current_version(self):
        """Test that OnomatoolConfig defaults to CURRENT_CONFIG_VERSION when not specified."""
        config = OnomatoolConfig(openai_api_key="test-key")
        assert config.config_version == CURRENT_CONFIG_VERSION

    def test_empty_config_file_loads_default(self, temp_config_file):
        """Test that an empty/invalid config file loads DEFAULT_CONFIG."""
        # Write an invalid config
        with open(temp_config_file, "w") as f:
            f.write("invalid toml content [[[[")

        loaded = get_config(str(temp_config_file))

        # Should fall back to default config
        assert loaded["config_version"] == CURRENT_CONFIG_VERSION
        assert loaded["default_provider"] == "openai"
        assert loaded["naming_convention"] == "snake_case"

    def test_nonexistent_config_file_loads_default(self):
        """Test that a non-existent config file loads DEFAULT_CONFIG."""
        loaded = get_config("/nonexistent/path/to/config.toml")

        assert loaded["config_version"] == CURRENT_CONFIG_VERSION
        assert loaded["default_provider"] == "openai"
        assert loaded["naming_convention"] == "snake_case"
