"""Tests for OnomatoolConfig Pydantic model (§3.1)."""

import pytest
from pydantic import ValidationError

from onomatool.config import (
    DEFAULT_CONFIG,
    NamingConvention,
    OnomatoolConfig,
    Provider,
    get_config,
)


def test_valid_config_all_defaults():
    """TC-CM-001: Default config creates successfully with expected values."""
    cfg = OnomatoolConfig()
    assert cfg.default_provider == Provider.openai
    assert cfg.naming_convention == NamingConvention.snake_case
    assert cfg.llm_model == "gpt-4o"
    assert cfg.min_filename_words == 5
    assert cfg.max_filename_words == 15
    assert cfg.use_azure_openai is False


def test_invalid_provider_rejected():
    """TC-CM-002: Invalid provider raises ValidationError."""
    with pytest.raises(ValidationError):
        OnomatoolConfig(default_provider="invalid_provider")


def test_out_of_range_min_words():
    """TC-CM-003: min_filename_words below 1 is rejected."""
    with pytest.raises(ValidationError):
        OnomatoolConfig(min_filename_words=0)


def test_out_of_range_max_words():
    """TC-CM-004: max_filename_words above 100 is rejected."""
    with pytest.raises(ValidationError):
        OnomatoolConfig(max_filename_words=101)


def test_min_greater_than_max_rejected():
    """TC-CM-005: min_filename_words > max_filename_words is rejected."""
    with pytest.raises(ValidationError):
        OnomatoolConfig(min_filename_words=20, max_filename_words=5)


def test_mock_provider_no_key_required():
    """TC-CM-006: Mock provider works without API keys."""
    cfg = OnomatoolConfig(default_provider="mock")
    assert cfg.default_provider == Provider.mock
    assert cfg.openai_api_key == ""


def test_defaults_match_spec():
    """TC-CM-007: DEFAULT_CONFIG dict matches OnomatoolConfig defaults."""
    assert DEFAULT_CONFIG["default_provider"] == "openai"
    assert DEFAULT_CONFIG["naming_convention"] == "snake_case"
    assert DEFAULT_CONFIG["llm_model"] == "gpt-4o"
    assert DEFAULT_CONFIG["min_filename_words"] == 5
    assert DEFAULT_CONFIG["max_filename_words"] == 15


def test_naming_convention_validation():
    """TC-CM-008: All valid naming conventions are accepted."""
    for conv in [
        "snake_case",
        "camelCase",
        "kebab-case",
        "PascalCase",
        "dot.notation",
        "natural language",
    ]:
        cfg = OnomatoolConfig(naming_convention=conv)
        assert cfg.naming_convention.value == conv


def test_invalid_naming_convention():
    """TC-CM-009: Invalid naming convention is rejected."""
    with pytest.raises(ValidationError):
        OnomatoolConfig(naming_convention="SCREAMING_CASE")


def test_config_round_trip(tmp_path):
    """TC-CM-010: Config loaded from file matches validated output."""
    import tomli_w

    config_data = {
        "default_provider": "mock",
        "llm_model": "test-model",
        "min_filename_words": 3,
        "max_filename_words": 10,
    }
    config_path = tmp_path / "test.toml"
    config_path.write_bytes(tomli_w.dumps(config_data).encode())

    loaded = get_config(str(config_path))
    assert loaded["default_provider"] == "mock"
    assert loaded["llm_model"] == "test-model"
    assert loaded["min_filename_words"] == 3
    assert loaded["max_filename_words"] == 10
    # Defaults should be filled in
    assert loaded["openai_api_key"] == ""
    assert loaded["naming_convention"] == "snake_case"
