"""
Tests for dry-run fidelity - ensuring re-resolution at confirmation time.

Test Coverage:
- check_planned_renames returns empty when no changes
- check_planned_renames detects conflicts when new files appear
- execute_planned_renames re-resolves conflicts correctly
- Interactive confirmation flow shows diff when names changed
"""

import os

from onomatool.rename_orchestrator import RenameOrchestrator

MOCK_CONFIG = {
    "default_provider": "mock",
    "naming_convention": "snake_case",
    "llm_model": "mock-model",
    "openai_api_key": "test-key",
    "openai_base_url": "https://mock-llm.local",
    "min_filename_words": 5,
    "max_filename_words": 15,
}


class TestDryRunFidelity:
    """Test dry-run fidelity and re-resolution at confirmation time."""

    def test_check_planned_renames_empty_when_no_changes(self, tmp_path):
        """check_planned_renames returns empty list when no conflicts emerged."""
        # Create test file
        test_file = tmp_path / "original.txt"
        test_file.write_text("test content")

        # Run dry-run
        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
        )
        orchestrator.process_files(str(test_file))

        # Check for changes (none should exist)
        changes = orchestrator.check_planned_renames()
        assert changes == []

    def test_check_planned_renames_detects_new_conflict(self, tmp_path):
        """check_planned_renames detects when a new file creates a conflict."""
        # Create test file
        test_file = tmp_path / "original.txt"
        test_file.write_text("test content")

        # Run dry-run
        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
        )
        orchestrator.process_files(str(test_file))

        # Verify we have planned renames
        assert len(orchestrator.planned_renames) == 1

        # Simulate another process creating a conflicting file
        # Mock provider suggests "mock_file_one.txt"
        conflicting_file = tmp_path / "mock_file_one.txt"
        conflicting_file.write_text("conflicting content")

        # Now check for changes
        changes = orchestrator.check_planned_renames()
        assert len(changes) == 1
        file_path, dry_name, actual_name = changes[0]
        assert os.path.basename(file_path) == "original.txt"
        assert dry_name == "mock_file_one.txt"
        assert actual_name == "mock_file_one_2.txt"

    def test_execute_planned_renames_resolves_conflicts(self, tmp_path):
        """execute_planned_renames correctly re-resolves conflicts during execution."""
        # Create test file
        test_file = tmp_path / "original.txt"
        test_file.write_text("test content")

        # Run dry-run
        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
        )
        orchestrator.process_files(str(test_file))

        # Create a conflicting file
        conflicting_file = tmp_path / "mock_file_one.txt"
        conflicting_file.write_text("conflicting content")

        # Execute planned renames (should resolve conflict)
        orchestrator.execute_planned_renames()

        # Original file should be renamed with conflict resolution
        assert not test_file.exists()
        renamed_file = tmp_path / "mock_file_one_2.txt"
        assert renamed_file.exists()
        assert renamed_file.read_text() == "test content"

    def test_multiple_files_with_conflicts(self, tmp_path):
        """Test dry-run fidelity with multiple files and mixed conflicts."""
        # Create test files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content 1")
        file2.write_text("content 2")

        # Run dry-run
        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
        )
        orchestrator.process_files(str(tmp_path / "*.txt"))

        # Verify planned renames
        assert len(orchestrator.planned_renames) == 2

        # Create a conflicting file for first planned rename only
        # Mock provider suggests mock_file_one for all files
        # Both files will get the same suggestion, so both will have conflicts
        conflicting_file = tmp_path / "mock_file_one.txt"
        conflicting_file.write_text("conflict")

        # Check for changes
        changes = orchestrator.check_planned_renames()
        # Both files originally intended mock_file_one.txt, now both need conflict resolution
        assert len(changes) == 2

    def test_interactive_flow_with_conflict(self, tmp_path, capsys, monkeypatch):
        """Test interactive confirmation flow when conflicts are detected."""

        # Create test file
        test_file = tmp_path / "original.txt"
        test_file.write_text("test content")

        # Run dry-run
        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
        )
        orchestrator.process_files(str(test_file))

        # Create a conflicting file
        conflicting_file = tmp_path / "mock_file_one.txt"
        conflicting_file.write_text("conflicting content")

        # Check for changes
        changes = orchestrator.check_planned_renames()
        assert len(changes) == 1

        # Simulate the interactive prompt logic from cli.py
        if changes:
            # Capture output to verify the diff message
            captured = capsys.readouterr()
            # The actual print happens in cli.py, so we just verify the data structure
            file_path, dry_name, actual_name = changes[0]
            assert dry_name == "mock_file_one.txt"
            assert actual_name == "mock_file_one_2.txt"

    def test_no_files_to_rename(self, tmp_path):
        """Test check_planned_renames when no files were processed."""
        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
        )

        # Process non-existent pattern
        orchestrator.process_files(str(tmp_path / "*.nonexistent"))

        # Should have no planned renames
        assert len(orchestrator.planned_renames) == 0

        # check_planned_renames should return empty
        changes = orchestrator.check_planned_renames()
        assert changes == []

    def test_conflict_chain_resolution(self, tmp_path):
        """Test that multiple conflict levels are resolved correctly."""
        # Create test file
        test_file = tmp_path / "original.txt"
        test_file.write_text("test content")

        # Run dry-run
        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
        )
        orchestrator.process_files(str(test_file))

        # Create multiple conflicting files
        (tmp_path / "mock_file_one.txt").write_text("conflict 1")
        (tmp_path / "mock_file_one_2.txt").write_text("conflict 2")

        # Check for changes
        changes = orchestrator.check_planned_renames()
        assert len(changes) == 1
        _, dry_name, actual_name = changes[0]
        assert dry_name == "mock_file_one.txt"
        assert actual_name == "mock_file_one_3.txt"

    def test_execute_without_history(self, tmp_path):
        """Test execute_planned_renames works without history tracking."""
        test_file = tmp_path / "original.txt"
        test_file.write_text("test content")

        # Create orchestrator without history
        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
            history=None,
        )
        orchestrator.process_files(str(test_file))

        # Execute should work fine without history
        orchestrator.execute_planned_renames()
        assert not test_file.exists()

    def test_dry_run_preserves_extension(self, tmp_path):
        """Test that dry-run and re-resolution preserve file extensions."""
        # Create test file with different extension (.md is processed as text)
        test_file = tmp_path / "document.md"
        test_file.write_text("# Markdown content")

        orchestrator = RenameOrchestrator(
            config=MOCK_CONFIG,
            dry_run=True,
            debug=False,
            verbose_level=0,
        )
        orchestrator.process_files(str(test_file))

        # Verify planned rename has correct extension
        assert len(orchestrator.planned_renames) == 1
        _, new_name = orchestrator.planned_renames[0]
        # new_name is stored without extension in planned_renames
        # but should get .md when resolved

        # Create conflict
        (tmp_path / "mock_file_one.md").write_text("conflict")

        # Check changes
        changes = orchestrator.check_planned_renames()
        assert len(changes) == 1
        _, dry_name, actual_name = changes[0]
        assert dry_name.endswith(".md")
        assert actual_name.endswith(".md")
        assert actual_name == "mock_file_one_2.md"
