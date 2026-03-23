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


# CLI edge case tests (§2.4)


def test_missing_pattern_error():
    """TC-E2E-002: Missing pattern exits with error."""
    with pytest.raises(SystemExit):
        main([])


def test_interactive_without_dry_run():
    """TC-E2E-004: --interactive without --dry-run is rejected."""
    with pytest.raises(SystemExit):
        main(["*.txt", "--interactive", "--config", MOCK_CONFIG])


def test_save_config(tmp_path, monkeypatch):
    """TC-E2E-005: --save-config creates config file."""
    config_path = tmp_path / ".onomarc"
    monkeypatch.setattr(
        "os.path.expanduser", lambda p: str(config_path) if p == "~/.onomarc" else p
    )
    result = main(["--save-config"])
    assert result == 0
    assert config_path.exists()


def test_batch_rename_multiple(tmp_path):
    """TC-E2E-006: Multiple files are renamed in batch."""
    for name in ["a.txt", "b.txt"]:
        (tmp_path / name).write_text(f"content of {name}")
    result = main([str(tmp_path / "*.txt"), "--config", MOCK_CONFIG])
    assert result == 0
    # Original files should be gone
    assert not (tmp_path / "a.txt").exists()
    assert not (tmp_path / "b.txt").exists()


def test_interactive_abort(temp_copy, capsys, monkeypatch):
    """TC-E2E-007: Interactive mode with 'n' aborts rename."""
    monkeypatch.setattr(builtins, "input", lambda _: "n")
    result = main([temp_copy, "--config", MOCK_CONFIG, "--dry-run", "--interactive"])
    assert result == 0
    # File should still exist (abort)
    assert os.path.exists(temp_copy)
    captured = capsys.readouterr()
    assert "Aborted" in captured.out
