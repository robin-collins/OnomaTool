"""Tests for file filtering and sorting functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from onomatool.rename_orchestrator import RenameOrchestrator


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config():
    """Basic config for testing."""
    return {
        "default_provider": "mock",
        "naming_convention": "snake_case",
    }


def create_test_file(path: Path, name: str, size: int = 100):
    """Create a test file with specified size."""
    file_path = path / name
    file_path.write_bytes(b"x" * size)
    return file_path


def test_exclude_single_pattern(temp_test_dir, mock_config):
    """Test that --exclude pattern filters matching files."""
    create_test_file(temp_test_dir, "keep1.txt")
    create_test_file(temp_test_dir, "keep2.txt")
    create_test_file(temp_test_dir, "ignore.log")

    orch = RenameOrchestrator(
        config=mock_config,
        exclude_patterns=["*.log"]
    )

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    basenames = [os.path.basename(f) for f in processed]
    assert "keep1.txt" in basenames
    assert "keep2.txt" in basenames
    assert "ignore.log" not in basenames


def test_exclude_multiple_patterns(temp_test_dir, mock_config):
    """Test that multiple --exclude patterns work."""
    create_test_file(temp_test_dir, "keep.txt")
    create_test_file(temp_test_dir, "ignore1.log")
    create_test_file(temp_test_dir, "ignore2.tmp")

    orch = RenameOrchestrator(
        config=mock_config,
        exclude_patterns=["*.log", "*.tmp"]
    )

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    basenames = [os.path.basename(f) for f in processed]
    assert basenames == ["keep.txt"]


def test_hidden_files_auto_skipped(temp_test_dir, mock_config):
    """Test that hidden files (dotfiles) are automatically skipped."""
    create_test_file(temp_test_dir, "visible.txt")
    create_test_file(temp_test_dir, ".hidden")
    create_test_file(temp_test_dir, ".gitignore")

    orch = RenameOrchestrator(config=mock_config)

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    basenames = [os.path.basename(f) for f in processed]
    assert basenames == ["visible.txt"]


def test_zero_byte_files_auto_skipped(temp_test_dir, mock_config):
    """Test that zero-byte files are automatically skipped."""
    create_test_file(temp_test_dir, "has_content.txt", size=100)
    create_test_file(temp_test_dir, "empty.txt", size=0)

    orch = RenameOrchestrator(config=mock_config)

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    basenames = [os.path.basename(f) for f in processed]
    assert basenames == ["has_content.txt"]


def test_sort_by_name(temp_test_dir, mock_config):
    """Test --sort name sorts alphabetically by basename."""
    create_test_file(temp_test_dir, "zebra.txt")
    create_test_file(temp_test_dir, "alpha.txt")
    create_test_file(temp_test_dir, "Beta.txt")

    orch = RenameOrchestrator(config=mock_config, sort_order="name")

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    basenames = [os.path.basename(f) for f in processed]
    assert basenames == ["alpha.txt", "Beta.txt", "zebra.txt"]


def test_sort_by_size(temp_test_dir, mock_config):
    """Test --sort size sorts by file size."""
    create_test_file(temp_test_dir, "large.txt", size=500)
    create_test_file(temp_test_dir, "small.txt", size=10)
    create_test_file(temp_test_dir, "medium.txt", size=100)

    orch = RenameOrchestrator(config=mock_config, sort_order="size")

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    basenames = [os.path.basename(f) for f in processed]
    assert basenames == ["small.txt", "medium.txt", "large.txt"]


def test_sort_by_modified(temp_test_dir, mock_config):
    """Test --sort modified sorts by modification time."""
    import time

    file1 = create_test_file(temp_test_dir, "first.txt")
    time.sleep(0.01)
    file2 = create_test_file(temp_test_dir, "second.txt")
    time.sleep(0.01)
    file3 = create_test_file(temp_test_dir, "third.txt")

    orch = RenameOrchestrator(config=mock_config, sort_order="modified")

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    basenames = [os.path.basename(f) for f in processed]
    assert basenames == ["first.txt", "second.txt", "third.txt"]


def test_non_regular_files_skipped(temp_test_dir, mock_config):
    """Test that directories are skipped by collect_files."""
    create_test_file(temp_test_dir, "regular.txt")

    # Create subdirectory
    subdir = temp_test_dir / "subdir"
    subdir.mkdir()

    orch = RenameOrchestrator(config=mock_config)

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    # Should only process the regular file, not the directory
    assert len(processed) == 1
    assert os.path.basename(processed[0]) == "regular.txt"


def test_combined_filtering_sorting(temp_test_dir, mock_config):
    """Test combining exclude patterns, hidden file filtering, and sorting."""
    create_test_file(temp_test_dir, "c_keep.txt", size=300)
    create_test_file(temp_test_dir, "a_keep.txt", size=100)
    create_test_file(temp_test_dir, "b_ignore.log", size=200)
    create_test_file(temp_test_dir, ".hidden", size=50)
    create_test_file(temp_test_dir, "empty.txt", size=0)

    orch = RenameOrchestrator(
        config=mock_config,
        exclude_patterns=["*.log"],
        sort_order="size"
    )

    processed = []
    with patch.object(orch, '_process_single_file', side_effect=lambda f: processed.append(f)):
        orch.process_files(str(temp_test_dir / '*'))

    basenames = [os.path.basename(f) for f in processed]
    assert basenames == ["a_keep.txt", "c_keep.txt"]
