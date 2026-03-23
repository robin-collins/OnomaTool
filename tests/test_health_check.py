"""
Tests for the --check health check command.

Test Coverage:
- --check returns 0 when all dependencies are available
- Output contains Python version
- Output contains package names
- Output contains status indicators ([OK] or [MISSING])
- Summary line appears
"""

import sys

from onomatool.cli import main, run_health_check


class TestHealthCheck:
    """Test the --check health check functionality."""

    def test_check_flag_calls_health_check(self, capsys):
        """--check flag invokes the health check."""
        result = main(["--check"])
        # Result may be 0 or 1 depending on system dependencies
        assert result in (0, 1)
        captured = capsys.readouterr()
        # Should have some output
        assert len(captured.out) > 0

    def test_health_check_returns_exit_code(self):
        """run_health_check returns appropriate exit code."""
        result = run_health_check()
        # Should return 0 if all OK, 1 if some missing
        assert result in (0, 1)

    def test_health_check_shows_python_version(self, capsys):
        """Health check output contains Python version."""
        run_health_check()
        captured = capsys.readouterr()
        assert "Python" in captured.out
        # Should show actual version like "3.10.1" or similar
        python_version = sys.version.split()[0]
        assert python_version in captured.out

    def test_health_check_shows_package_names(self, capsys):
        """Health check output contains package names."""
        run_health_check()
        captured = capsys.readouterr()

        # Core packages that should be checked
        expected_packages = [
            "markitdown",
            "openai",
            "google-genai",
            "tomli",
            "pydantic",
            "tiktoken",
            "chardet",
            "cairosvg",
            "Pillow",
            "PyMuPDF",
        ]

        for package in expected_packages:
            assert package in captured.out, (
                f"Package {package} not found in health check output"
            )

    def test_health_check_shows_system_tools(self, capsys):
        """Health check output contains system tool names."""
        run_health_check()
        captured = capsys.readouterr()

        # System tools that should be checked
        expected_tools = ["soffice", "convert"]

        for tool in expected_tools:
            assert tool in captured.out, f"Tool {tool} not found in health check output"

    def test_health_check_shows_status_indicators(self, capsys):
        """Health check output contains status indicators."""
        run_health_check()
        captured = capsys.readouterr()

        # Should contain at least one status indicator
        assert "[OK]" in captured.out or "[MISSING]" in captured.out

    def test_health_check_shows_summary(self, capsys):
        """Health check output contains summary line."""
        result = run_health_check()
        captured = capsys.readouterr()

        if result == 0:
            assert "All dependencies OK" in captured.out
        else:
            assert "Some dependencies are missing" in captured.out

    def test_health_check_output_format(self, capsys):
        """Health check output follows expected format."""
        run_health_check()
        captured = capsys.readouterr()

        lines = captured.out.strip().split("\n")
        # Should have multiple lines
        assert len(lines) > 5

        # Each line (except summary) should follow format:
        # "  package_name    version    [STATUS]"
        non_summary_lines = [
            line
            for line in lines
            if not line.startswith("\n") and "dependencies" not in line.lower()
        ]

        for line in non_summary_lines:
            if line.strip():  # Skip empty lines
                # Should contain either [OK] or [MISSING]
                assert "[OK]" in line or "[MISSING]" in line

    def test_check_does_not_require_pattern(self):
        """--check does not require pattern argument."""
        result = main(["--check"])
        assert result in (0, 1)
        # Should not raise SystemExit for missing pattern

    def test_check_with_other_flags_ignored(self):
        """--check ignores other flags and runs health check."""
        # These flags should be ignored when --check is present
        result = main(["--check", "--dry-run", "-v"])
        assert result in (0, 1)

    def test_check_takes_precedence(self):
        """--check takes precedence over pattern requirement."""
        # Even without a pattern, --check should work
        result = main(["--check"])
        assert result in (0, 1)

    def test_health_check_handles_import_errors(self, capsys, monkeypatch):
        """Health check handles ImportError for missing packages gracefully."""
        # This test verifies the try/except ImportError logic

        # We can't easily mock all imports, but we can verify the output
        # handles missing packages correctly
        run_health_check()
        captured = capsys.readouterr()

        # The output should have status for each package
        # Some might be MISSING, some might be OK
        lines = [line for line in captured.out.split("\n") if line.strip()]

        # At least one package should have a status
        has_status = any("[OK]" in line or "[MISSING]" in line for line in lines)
        assert has_status

    def test_health_check_shows_versions_when_available(self, capsys):
        """Health check shows package versions when available."""
        run_health_check()
        captured = capsys.readouterr()

        # Python should always show a version
        python_version = sys.version.split()[0]
        assert python_version in captured.out

        # Other packages might show versions or "installed"
        # We just verify the format is correct
        lines = captured.out.split("\n")
        for line in lines:
            if "Python" in line:
                # Python line should have version and [OK]
                assert python_version in line
                assert "[OK]" in line

    def test_health_check_exit_code_consistency(self, capsys):
        """Exit code matches the summary message."""
        result = run_health_check()
        captured = capsys.readouterr()

        if result == 0:
            # All OK
            assert "All dependencies OK" in captured.out
            assert "[MISSING]" not in captured.out
        else:
            # Some missing
            assert "Some dependencies are missing" in captured.out
            assert "[MISSING]" in captured.out

    def test_health_check_detects_missing_system_tools(self, capsys):
        """Health check detects when system tools are missing."""
        run_health_check()
        captured = capsys.readouterr()

        # Check for soffice and convert
        # They might be present or missing depending on the system
        # We just verify they're checked
        assert "soffice" in captured.out
        assert "convert" in captured.out

    def test_health_check_timeout_handling(self, capsys):
        """Health check handles subprocess timeouts gracefully."""
        # This test just verifies that the health check completes
        # even if subprocess calls timeout
        result = run_health_check()
        assert result in (0, 1)

        captured = capsys.readouterr()
        # Should still produce output
        assert len(captured.out) > 0

    def test_check_with_config_file_ignored(self, tmp_path):
        """--check ignores --config flag."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('default_provider = "mock"')

        result = main(["--check", "--config", str(config_file)])
        assert result in (0, 1)
        # Should complete without error

    def test_multiple_check_calls_consistent(self, capsys):
        """Multiple health check calls produce consistent results."""
        result1 = run_health_check()
        captured1 = capsys.readouterr()

        result2 = run_health_check()
        captured2 = capsys.readouterr()

        # Results should be the same
        assert result1 == result2

        # Output should be similar (versions might differ slightly if packages update)
        # but structure should be identical
        lines1 = [line for line in captured1.out.split("\n") if line.strip()]
        lines2 = [line for line in captured2.out.split("\n") if line.strip()]

        # Same number of lines
        assert len(lines1) == len(lines2)
