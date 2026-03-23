import os

import tomli_w

from onomatool.config import DEFAULT_CONFIG, get_config


def test_get_config_default(monkeypatch):
    # No config file exists, should return DEFAULT_CONFIG
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    assert get_config("/nonexistent.toml") == DEFAULT_CONFIG


def test_get_config_valid(tmp_path):
    config_data = {"default_provider": "mock", "llm_model": "test-model"}
    config_path = tmp_path / "config.toml"
    config_path.write_bytes(tomli_w.dumps(config_data).encode())
    loaded = get_config(str(config_path))
    assert loaded["default_provider"] == "mock"
    assert loaded["llm_model"] == "test-model"


def test_get_config_error(tmp_path):
    # Invalid TOML should fallback to DEFAULT_CONFIG
    config_path = tmp_path / "bad.toml"
    config_path.write_text("not a valid [[[toml")
    assert get_config(str(config_path)) == DEFAULT_CONFIG


# Deep-merge and edge case tests (§2.1)


def test_deep_merge_partial_config(tmp_path):
    """TC-CFG-001: Partial config inherits missing defaults."""
    config_path = tmp_path / "partial.toml"
    config_path.write_bytes(tomli_w.dumps({"llm_model": "gpt-4o-mini"}).encode())
    loaded = get_config(str(config_path))
    assert loaded["llm_model"] == "gpt-4o-mini"
    assert loaded["default_provider"] == "openai"  # default
    assert loaded["min_filename_words"] == 5  # default


def test_nested_markitdown_section(tmp_path):
    """TC-CFG-002: Nested markitdown section is preserved."""
    data = {"markitdown": {"enable_plugins": True, "docintel_endpoint": "http://test"}}
    config_path = tmp_path / "nested.toml"
    config_path.write_bytes(tomli_w.dumps(data).encode())
    loaded = get_config(str(config_path))
    assert loaded["markitdown"]["enable_plugins"] is True
    assert loaded["markitdown"]["docintel_endpoint"] == "http://test"


def test_empty_config_file(tmp_path):
    """TC-CFG-003: Empty config file returns all defaults."""
    config_path = tmp_path / "empty.toml"
    config_path.write_bytes(b"")
    loaded = get_config(str(config_path))
    assert loaded["default_provider"] == "openai"
    assert loaded["llm_model"] == "gpt-4o"


def test_config_precedence(tmp_path):
    """TC-CFG-004: User values override defaults."""
    data = {
        "default_provider": "google",
        "naming_convention": "camelCase",
        "min_filename_words": 3,
        "max_filename_words": 8,
    }
    config_path = tmp_path / "override.toml"
    config_path.write_bytes(tomli_w.dumps(data).encode())
    loaded = get_config(str(config_path))
    assert loaded["default_provider"] == "google"
    assert loaded["naming_convention"] == "camelCase"
    assert loaded["min_filename_words"] == 3
    assert loaded["max_filename_words"] == 8


def test_validation_error_falls_back(tmp_path, caplog):
    """TC-CFG-005: Invalid values fall back to defaults with error message."""
    data = {"min_filename_words": 0}  # Below minimum
    config_path = tmp_path / "invalid.toml"
    config_path.write_bytes(tomli_w.dumps(data).encode())
    loaded = get_config(str(config_path))
    # Should fall back to defaults
    assert loaded == DEFAULT_CONFIG
    assert "validation error" in caplog.text.lower()
