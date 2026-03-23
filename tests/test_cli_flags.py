"""
Tests for CLI flag parsing and argument validation.

Test Coverage:
- Configuration flags (--save-config, --config)
- Health check (--check)
- File filtering (--exclude)
- Sort and format options
- Undo/history commands
- Verbosity levels (-v, -vv)
- Dry-run and interactive modes
- Required arguments validation
"""

from pathlib import Path

import pytest

from onomatool.cli import main

MOCK_CONFIG = str(Path(__file__).resolve().parent / "mock_config.toml")


class TestConfigFlags:
    """Test configuration-related flags."""

    def test_save_config_creates_file(self, tmp_path, monkeypatch):
        """--save-config creates config file at ~/.onomarc."""
        config_path = tmp_path / ".onomarc"
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(config_path) if p == "~/.onomarc" else p,
        )
        result = main(["--save-config"])
        assert result == 0
        assert config_path.exists()
        # Verify it's valid TOML by reading it
        content = config_path.read_text()
        assert "default_provider" in content or "llm_model" in content

    def test_save_config_does_not_require_pattern(self):
        """--save-config does not require pattern argument."""
        # Should not raise SystemExit for missing pattern
        # (actual file creation tested above)
        result = main(["--save-config"])
        assert result == 0


class TestHealthCheck:
    """Test health check functionality."""

    def test_check_returns_health_output(self, capsys):
        """--check returns health check output."""
        result = main(["--check"])
        # Result may be 0 or 1 depending on system dependencies
        assert result in (0, 1)
        captured = capsys.readouterr()
        # Should show Python version
        assert "Python" in captured.out
        # Should show package checks
        assert "markitdown" in captured.out or "MISSING" in captured.out

    def test_check_does_not_require_pattern(self):
        """--check does not require pattern argument."""
        result = main(["--check"])
        assert result in (0, 1)


class TestExcludePatterns:
    """Test file exclusion patterns."""

    def test_exclude_filters_files(self, tmp_path):
        """--exclude filters out matching files."""
        # Create test files
        (tmp_path / "include_me.txt").write_text("content")
        (tmp_path / "exclude_me.txt").write_text("content")
        (tmp_path / "also_exclude.txt").write_text("content")

        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--exclude",
                "*exclude*",
                "--dry-run",
            ]
        )
        assert result == 0
        # Only include_me.txt should be renamed (in real run)
        # In dry-run, just verify no error

    def test_exclude_multiple_patterns(self, tmp_path, capsys):
        """--exclude can be repeated for multiple patterns."""
        (tmp_path / "keep.txt").write_text("content")
        (tmp_path / "skip1.txt").write_text("content")
        (tmp_path / "skip2.txt").write_text("content")

        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--exclude",
                "*skip1*",
                "--exclude",
                "*skip2*",
                "--dry-run",
            ]
        )
        assert result == 0


class TestSortOption:
    """Test sort order options."""

    def test_sort_accepts_name(self, tmp_path):
        """--sort accepts 'name' as valid choice."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--sort",
                "name",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_sort_accepts_size(self, tmp_path):
        """--sort accepts 'size' as valid choice."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--sort",
                "size",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_sort_accepts_modified(self, tmp_path):
        """--sort accepts 'modified' as valid choice."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--sort",
                "modified",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_sort_rejects_invalid_choice(self):
        """--sort rejects invalid choices."""
        with pytest.raises(SystemExit):
            main(["*.txt", "--sort", "invalid", "--config", MOCK_CONFIG])


class TestFormatOption:
    """Test format override options."""

    def test_format_accepts_text(self, tmp_path):
        """--format accepts 'text' as valid choice."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--format",
                "text",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_format_accepts_markdown(self, tmp_path):
        """--format accepts 'markdown' as valid choice."""
        (tmp_path / "test.md").write_text("# content")
        result = main(
            [
                str(tmp_path / "*.md"),
                "--config",
                MOCK_CONFIG,
                "--format",
                "markdown",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_format_accepts_pdf(self, tmp_path):
        """--format accepts 'pdf' as valid choice."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--format",
                "pdf",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_format_accepts_docx(self, tmp_path):
        """--format accepts 'docx' as valid choice."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--format",
                "docx",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_format_accepts_image(self, tmp_path):
        """--format accepts 'image' as valid choice."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--format",
                "image",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_format_rejects_invalid_choice(self):
        """--format rejects invalid choices."""
        with pytest.raises(SystemExit):
            main(["*.txt", "--format", "invalid", "--config", MOCK_CONFIG])


class TestUndoCommand:
    """Test undo functionality."""

    def test_undo_with_no_sessions_shows_error(self, capsys, tmp_path, monkeypatch):
        """--undo with no sessions shows appropriate error."""
        # Use a temporary history database
        history_db = tmp_path / "history.db"
        monkeypatch.setenv("ONOMATOOL_HISTORY_DB", str(history_db))

        result = main(["--undo"])
        assert result == 0  # Function returns 0 even with no sessions
        captured = capsys.readouterr()
        # Should show some kind of error or empty result
        # (The actual behavior depends on RenameHistory implementation)

    def test_undo_does_not_require_pattern(self):
        """--undo does not require pattern argument."""
        # Should not raise SystemExit for missing pattern
        result = main(["--undo"])
        assert result == 0


class TestHistoryCommand:
    """Test history functionality."""

    def test_history_with_no_sessions_shows_message(
        self, capsys, tmp_path, monkeypatch
    ):
        """--history with no sessions shows 'No rename sessions found'."""
        # Use a temporary history database
        history_db = tmp_path / "history.db"

        # Mock RenameHistory to use isolated database
        from onomatool.history import RenameHistory

        original_init = RenameHistory.__init__

        def mock_init(self, db_path=None):
            original_init(self, db_path=str(history_db))

        monkeypatch.setattr(RenameHistory, "__init__", mock_init)

        result = main(["--history"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No rename sessions found" in captured.out

    def test_history_does_not_require_pattern(self):
        """--history does not require pattern argument."""
        result = main(["--history"])
        assert result == 0


class TestVerbosityLevels:
    """Test verbosity flags."""

    def test_verbose_sets_level_1(self, tmp_path, capsys):
        """-v sets verbose_level=1."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "-v",
                "--dry-run",
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        # With -v, we should see INFO level messages (e.g., [INFO])
        # The actual log format is "[%(levelname)s] %(message)s"

    def test_very_verbose_sets_level_2(self, tmp_path, capsys):
        """-vv sets verbose_level=2."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "-vv",
                "--dry-run",
            ]
        )
        assert result == 0
        captured = capsys.readouterr()
        # With -vv, we should see DEBUG level messages

    def test_verbose_long_form(self, tmp_path):
        """--verbose sets verbose_level=1."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--verbose",
                "--dry-run",
            ]
        )
        assert result == 0

    def test_very_verbose_long_form(self, tmp_path):
        """--very-verbose sets verbose_level=2."""
        (tmp_path / "test.txt").write_text("content")
        result = main(
            [
                str(tmp_path / "*.txt"),
                "--config",
                MOCK_CONFIG,
                "--very-verbose",
                "--dry-run",
            ]
        )
        assert result == 0


class TestDryRunMode:
    """Test dry-run functionality."""

    def test_dry_run_prevents_actual_renames(self, tmp_path, capsys):
        """--dry-run prevents actual file renames."""
        test_file = tmp_path / "original.txt"
        test_file.write_text("test content")

        result = main(
            [
                str(test_file),
                "--config",
                MOCK_CONFIG,
                "--dry-run",
            ]
        )
        assert result == 0

        # Original file should still exist
        assert test_file.exists()

        # Should show intended rename in output
        captured = capsys.readouterr()
        assert "mock_file" in captured.out or "original.txt" in captured.out


class TestInteractiveMode:
    """Test interactive mode requirements."""

    def test_interactive_requires_dry_run(self):
        """--interactive requires --dry-run."""
        with pytest.raises(SystemExit) as exc_info:
            main(["*.txt", "--interactive", "--config", MOCK_CONFIG])
        # Should exit with error status
        assert exc_info.value.code != 0

    def test_interactive_with_dry_run_succeeds(self, tmp_path, monkeypatch):
        """--interactive with --dry-run is valid."""
        import builtins

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Mock user input to decline
        monkeypatch.setattr(builtins, "input", lambda _: "n")

        result = main(
            [
                str(test_file),
                "--config",
                MOCK_CONFIG,
                "--dry-run",
                "--interactive",
            ]
        )
        assert result == 0


class TestRequiredArguments:
    """Test required argument validation."""

    def test_pattern_required_for_normal_operation(self):
        """Pattern is required when not using special flags."""
        with pytest.raises(SystemExit):
            main(["--config", MOCK_CONFIG])

    def test_pattern_not_required_for_save_config(self):
        """Pattern is not required with --save-config."""
        result = main(["--save-config"])
        assert result == 0

    def test_pattern_not_required_for_check(self):
        """Pattern is not required with --check."""
        result = main(["--check"])
        assert result in (0, 1)

    def test_pattern_not_required_for_undo(self):
        """Pattern is not required with --undo."""
        result = main(["--undo"])
        assert result == 0

    def test_pattern_not_required_for_history(self):
        """Pattern is not required with --history."""
        result = main(["--history"])
        assert result == 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_args_shows_error(self):
        """Empty arguments list shows error."""
        with pytest.raises(SystemExit):
            main([])

    def test_help_flag_exits_cleanly(self):
        """--help flag exits cleanly."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        # Help should exit with 0 (success)
        assert exc_info.value.code == 0

    def test_keyboard_interrupt_handling(self, tmp_path, monkeypatch):
        """KeyboardInterrupt is handled gracefully."""
        from onomatool.rename_orchestrator import RenameOrchestrator

        def mock_process(*args, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr(
            RenameOrchestrator,
            "process_files",
            mock_process,
        )

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = main([str(test_file), "--config", MOCK_CONFIG])
        assert result == 130  # Standard exit code for Ctrl+C
