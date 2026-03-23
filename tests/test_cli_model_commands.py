"""Tests for --list-models and --select-model CLI commands."""

from unittest.mock import patch

import pytest
import tomli

from onomatool.cli import main
from onomatool.model_discovery import ModelInfo


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temp config file with mock provider."""
    config_path = tmp_path / ".onomarc"
    config_path.write_text('default_provider = "mock"\n')
    return str(config_path)


class TestListModels:
    def test_list_models_mock_provider(self, tmp_config, capsys):
        result = main(["--list-models", "--config", tmp_config])
        assert result == 0
        out = capsys.readouterr().out
        assert "mock-model" in out
        assert "1 model(s) found" in out

    def test_list_models_with_verbose(self, tmp_config, capsys):
        result = main(["--list-models", "-v", "--config", tmp_config])
        assert result == 0
        out = capsys.readouterr().out
        assert "mock-model" in out

    def test_list_models_error(self, tmp_config, capsys):
        with patch(
            "onomatool.cli.list_models",
            side_effect=RuntimeError("Connection refused"),
        ):
            result = main(["--list-models", "--config", tmp_config])
        assert result == 1
        err = capsys.readouterr().err
        assert "Connection refused" in err


class TestSelectModel:
    def test_select_model_and_save(self, tmp_path, capsys):
        config_path = tmp_path / ".onomarc"
        config_path.write_text('default_provider = "mock"\nllm_model = "old-model"\n')

        fake_models = [
            ModelInfo(id="new-model", name="New Model", provider="mock"),
        ]
        with (
            patch("onomatool.cli.list_models", return_value=fake_models),
            patch(
                "onomatool.cli.select_model_interactive",
                return_value=fake_models[0],
            ),
        ):
            result = main(["--select-model", "--config", str(config_path)])

        assert result == 0
        out = capsys.readouterr().out
        assert "new-model" in out

        # Verify config was updated
        with open(config_path, "rb") as f:
            saved = tomli.load(f)
        assert saved["llm_model"] == "new-model"
        # Original keys preserved
        assert saved["default_provider"] == "mock"

    def test_select_model_cancelled(self, tmp_config, capsys):
        with (
            patch(
                "onomatool.cli.list_models",
                return_value=[ModelInfo(id="m", name="M", provider="mock")],
            ),
            patch("onomatool.cli.select_model_interactive", return_value=None),
        ):
            result = main(["--select-model", "--config", tmp_config])

        assert result == 0
        out = capsys.readouterr().out
        assert "No model selected" in out

    def test_select_model_api_error(self, tmp_config, capsys):
        with patch(
            "onomatool.cli.list_models",
            side_effect=RuntimeError("No API key"),
        ):
            result = main(["--select-model", "--config", tmp_config])
        assert result == 1


class TestNoConflictWithExistingArgs:
    """Ensure new flags don't break existing CLI behavior."""

    def test_pattern_still_required_without_flags(self, capsys):
        with pytest.raises(SystemExit):
            main([])

    def test_save_config_still_works(self, tmp_path, monkeypatch):
        config_path = tmp_path / ".onomarc"
        monkeypatch.setattr(
            "onomatool.cli.os.path.expanduser", lambda p: str(config_path)
        )
        result = main(["--save-config"])
        assert result == 0
        assert config_path.exists()
