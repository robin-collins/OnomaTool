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
