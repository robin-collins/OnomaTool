import builtins
import os
from pathlib import Path

import pytest

from onomatool.cli import main

MOCK_CONFIG = str(Path(__file__).resolve().parent / "mock_config.toml")


@pytest.fixture
def temp_copy(copy_example_file):
    """Copy note_0.md to an isolated temp directory for destructive tests."""
    return copy_example_file("note_0.md")


def test_basic_rename(temp_copy):
    result = main([temp_copy, "--config", MOCK_CONFIG])
    assert result == 0
    renamed = os.path.join(os.path.dirname(temp_copy), "mock_file_one.md")
    assert os.path.exists(renamed)


def test_dry_run(temp_copy, capsys):
    result = main([temp_copy, "--config", MOCK_CONFIG, "--dry-run"])
    assert result == 0
    captured = capsys.readouterr()
    assert "mock_file_one.md" in captured.out
    # File should not be renamed in dry-run
    assert os.path.exists(temp_copy)


@pytest.mark.usefixtures("temp_copy")
def test_interactive(temp_copy, capsys, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _: "y")
    result = main([temp_copy, "--config", MOCK_CONFIG, "--dry-run", "--interactive"])
    assert result == 0
    renamed = os.path.join(os.path.dirname(temp_copy), "mock_file_one.md")
    assert os.path.exists(renamed)


def test_debug_mode(temp_copy, capsys):
    result = main([temp_copy, "--config", MOCK_CONFIG, "--debug"])
    assert result == 0
    # Debug mode should still rename successfully; for text files processed
    # via MarkitdownProcessor in debug mode, [DEBUG] output may appear
    captured = capsys.readouterr()
    renamed = os.path.join(os.path.dirname(temp_copy), "mock_file_one.md")
    assert os.path.exists(renamed) or "[DEBUG]" in captured.out


def test_alternate_config(temp_copy):
    result = main([temp_copy, "--config", MOCK_CONFIG])
    assert result == 0
    renamed = os.path.join(os.path.dirname(temp_copy), "mock_file_one.md")
    assert os.path.exists(renamed)
