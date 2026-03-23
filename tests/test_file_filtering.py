"""
Tests for file filtering in file_collector.py.

Tests verify that collect_files correctly filters non-regular files
(directories, symlinks, etc.) and only returns regular files.
"""

import logging
import os

from onomatool.file_collector import collect_files


class TestFileFiltering:
    """Test suite for non-regular file filtering in collect_files."""

    def test_regular_files_are_returned(self, tmp_path):
        """TC-FF-001: Test that regular files are returned by collect_files."""
        # Create regular files
        file1 = tmp_path / "document1.txt"
        file2 = tmp_path / "document2.txt"
        file3 = tmp_path / "report.pdf"

        file1.write_text("Content 1")
        file2.write_text("Content 2")
        file3.write_text("Content 3")

        # Collect files using glob pattern
        pattern = str(tmp_path / "*.txt")
        result = collect_files(pattern)

        # Should return both .txt files
        assert len(result) == 2
        assert str(file1) in result
        assert str(file2) in result
        assert str(file3) not in result

    def test_directories_are_filtered_out(self, tmp_path, caplog):
        """TC-FF-002: Test that directories matching the glob pattern are filtered out."""
        # Create regular files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Content 1")
        file2.write_text("Content 2")

        # Create directories that would match the glob
        dir1 = tmp_path / "dir1.txt"
        dir2 = tmp_path / "dir2.txt"
        dir1.mkdir()
        dir2.mkdir()

        # Collect files - directories should be filtered
        with caplog.at_level(logging.WARNING):
            pattern = str(tmp_path / "*.txt")
            result = collect_files(pattern)

        # Should only return regular files
        assert len(result) == 2
        assert str(file1) in result
        assert str(file2) in result
        assert str(dir1) not in result
        assert str(dir2) not in result

        # Should log warnings for directories
        assert "Skipping non-regular file" in caplog.text
        assert str(dir1) in caplog.text or str(dir2) in caplog.text

    def test_symlinks_to_nonexistent_targets_are_filtered(self, tmp_path, caplog):
        """TC-FF-003: Test that symlinks to non-existent targets are filtered out."""
        # Create a regular file
        regular_file = tmp_path / "regular.txt"
        regular_file.write_text("Regular content")

        # Create a broken symlink (pointing to non-existent target)
        broken_symlink = tmp_path / "broken.txt"
        nonexistent_target = tmp_path / "nonexistent.txt"
        os.symlink(nonexistent_target, broken_symlink)

        # Verify the symlink is broken
        assert broken_symlink.exists() is False  # exists() follows symlinks
        assert broken_symlink.is_symlink() is True

        # Collect files - broken symlink should be filtered
        with caplog.at_level(logging.WARNING):
            pattern = str(tmp_path / "*.txt")
            result = collect_files(pattern)

        # Should only return regular file
        assert len(result) == 1
        assert str(regular_file) in result
        assert str(broken_symlink) not in result

        # Should log warning for broken symlink
        assert "Skipping non-regular file" in caplog.text
        assert str(broken_symlink) in caplog.text

    def test_warning_logged_for_skipped_nonregular_files(self, tmp_path, caplog):
        """TC-FF-004: Test that a warning is logged for skipped non-regular files."""
        # Create regular file
        regular_file = tmp_path / "regular.txt"
        regular_file.write_text("Content")

        # Create directory
        directory = tmp_path / "dir.txt"
        directory.mkdir()

        # Create broken symlink
        broken_link = tmp_path / "link.txt"
        os.symlink(tmp_path / "nonexistent.txt", broken_link)

        # Collect files with logging capture
        with caplog.at_level(logging.WARNING, logger="onomatool.file_collector"):
            pattern = str(tmp_path / "*.txt")
            result = collect_files(pattern)

        # Verify only regular file returned
        assert len(result) == 1
        assert str(regular_file) in result

        # Verify warnings were logged
        warning_messages = [
            rec.message for rec in caplog.records if rec.levelname == "WARNING"
        ]

        # Should have 2 warnings (directory and broken symlink)
        assert len(warning_messages) == 2

        # Each warning should mention the skipped file
        skipped_files = [str(directory), str(broken_link)]
        for skipped_file in skipped_files:
            assert any(skipped_file in msg for msg in warning_messages), (
                f"Expected warning for {skipped_file}"
            )

        # Each warning should contain the expected message format
        for msg in warning_messages:
            assert "Skipping non-regular file:" in msg

    def test_empty_glob_pattern_returns_empty_list(self, tmp_path):
        """TC-FF-005: Test that an empty glob pattern returns empty list."""
        # Create some files
        file1 = tmp_path / "test.txt"
        file1.write_text("Content")

        # Empty pattern should match nothing
        result = collect_files("")

        # Should return empty list
        assert result == []
        assert len(result) == 0

    def test_recursive_glob_with_mixed_file_types(self, tmp_path, caplog):
        """Additional test: recursive glob with nested structure and mixed types."""
        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Regular files at different levels
        root_file = tmp_path / "root.txt"
        sub_file = subdir / "nested.txt"
        root_file.write_text("Root")
        sub_file.write_text("Nested")

        # Directory in subdir
        nested_dir = subdir / "dir.txt"
        nested_dir.mkdir()

        # Collect with recursive pattern
        with caplog.at_level(logging.WARNING):
            pattern = str(tmp_path / "**" / "*.txt")
            result = collect_files(pattern)

        # Should return both regular files
        assert len(result) == 2
        assert str(root_file) in result
        assert str(sub_file) in result
        assert str(nested_dir) not in result

        # Should warn about the directory
        assert "Skipping non-regular file" in caplog.text
        assert str(nested_dir) in caplog.text

    def test_pattern_with_no_matches(self, tmp_path):
        """Additional test: pattern that matches no files."""
        # Create file with different extension
        file1 = tmp_path / "test.txt"
        file1.write_text("Content")

        # Pattern that matches nothing
        pattern = str(tmp_path / "*.pdf")
        result = collect_files(pattern)

        # Should return empty list
        assert result == []
        assert len(result) == 0
