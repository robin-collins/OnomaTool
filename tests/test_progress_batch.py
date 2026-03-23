"""Tests for progress bar display and batch error handling."""

from pathlib import Path
from unittest.mock import patch

import pytest

from onomatool.config import get_config
from onomatool.rename_orchestrator import RenameOrchestrator
from onomatool.suggestion_strategy import TextOnlyStrategy

MOCK_CONFIG = str(Path(__file__).resolve().parent / "mock_config.toml")


@pytest.fixture
def mock_config():
    """Load the mock config for testing."""
    return get_config(MOCK_CONFIG)


@pytest.fixture
def temp_files(work_dir):
    """Create multiple temp files for batch testing."""
    files = []
    for i in range(3):
        file_path = work_dir / f"test_file_{i}.txt"
        file_path.write_text(f"Content of file {i}")
        files.append(str(file_path))
    return files


@pytest.fixture
def single_file(work_dir):
    """Create a single temp file."""
    file_path = work_dir / "single.txt"
    file_path.write_text("Single file content")
    return str(file_path)


def test_progress_bar_disabled_for_single_file(mock_config, single_file, capsys):
    """Test that progress bar is disabled when processing a single file."""
    orchestrator = RenameOrchestrator(mock_config, dry_run=True)

    # Mock sys.stderr.isatty to return True (simulate terminal)
    with patch("sys.stderr.isatty", return_value=True):
        orchestrator.process_files(single_file)

    captured = capsys.readouterr()
    # Progress bar output should not appear for single file
    # tqdm writes to stderr, but we disabled it so nothing should appear there
    assert "Processing" not in captured.err


def test_progress_bar_enabled_for_multiple_files(mock_config, work_dir, capsys):
    """Test that progress bar is enabled when processing multiple files."""
    # Create multiple files
    for i in range(3):
        (work_dir / f"file_{i}.txt").write_text(f"Content {i}")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)

    # Mock sys.stderr.isatty to return True (simulate terminal)
    with patch("sys.stderr.isatty", return_value=True):
        orchestrator.process_files(str(work_dir / "*.txt"))

    # Can't easily capture tqdm output, but we can verify the counts
    assert orchestrator.renamed_count == 3
    assert orchestrator.failed_count == 0
    assert orchestrator.skipped_count == 0


def test_renamed_count_tracks_correctly(mock_config, work_dir, capsys):
    """Test that renamed_count increments for successful renames."""
    for i in range(3):
        (work_dir / f"file_{i}.txt").write_text(f"Content {i}")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)
    orchestrator.process_files(str(work_dir / "*.txt"))

    assert orchestrator.renamed_count == 3
    assert orchestrator.failed_count == 0
    assert orchestrator.skipped_count == 0


def test_failed_count_increments_on_error(mock_config, work_dir, capsys):
    """Test that failed_count increments when file processing fails."""
    for i in range(3):
        (work_dir / f"file_{i}.txt").write_text(f"Content {i}")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)

    # Mock the strategy to raise an exception on second file
    call_count = [0]
    original_get_suggestions = TextOnlyStrategy.get_suggestions

    def mock_get_suggestions(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("Simulated LLM failure")
        return original_get_suggestions(self, *args, **kwargs)

    with patch.object(TextOnlyStrategy, "get_suggestions", mock_get_suggestions):
        orchestrator.process_files(str(work_dir / "*.txt"))

    # One file should fail, two should succeed
    assert orchestrator.renamed_count == 2
    assert orchestrator.failed_count == 1
    assert orchestrator.skipped_count == 0


def test_skipped_count_increments_when_no_suggestions(mock_config, work_dir, capsys):
    """Test that skipped_count increments when LLM returns no suggestions."""
    for i in range(3):
        (work_dir / f"file_{i}.txt").write_text(f"Content {i}")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)

    # Mock strategy to return empty suggestions for second file
    call_count = [0]
    original_get_suggestions = TextOnlyStrategy.get_suggestions

    def mock_get_suggestions(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            return []  # No suggestions
        return original_get_suggestions(self, *args, **kwargs)

    with patch.object(TextOnlyStrategy, "get_suggestions", mock_get_suggestions):
        orchestrator.process_files(str(work_dir / "*.txt"))

    # One file skipped, two renamed
    assert orchestrator.renamed_count == 2
    assert orchestrator.failed_count == 0
    assert orchestrator.skipped_count == 1


def test_summary_printed_at_end(mock_config, work_dir, capsys):
    """Test that summary is printed at end with correct counts."""
    for i in range(3):
        (work_dir / f"file_{i}.txt").write_text(f"Content {i}")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)
    orchestrator.process_files(str(work_dir / "*.txt"))

    captured = capsys.readouterr()
    # Check summary line
    assert "Processed 3 files:" in captured.out
    assert "3 planned" in captured.out
    assert "0 failed" in captured.out
    assert "0 skipped" in captured.out


def test_summary_mixed_results(mock_config, work_dir, capsys):
    """Test summary with mixed success/failure/skipped results."""
    for i in range(5):
        (work_dir / f"file_{i}.txt").write_text(f"Content {i}")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)

    # Mock strategy with different outcomes
    call_count = [0]
    original_get_suggestions = TextOnlyStrategy.get_suggestions

    def mock_get_suggestions(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("Failure")
        elif call_count[0] == 4:
            return []  # Skip
        return original_get_suggestions(self, *args, **kwargs)

    with patch.object(TextOnlyStrategy, "get_suggestions", mock_get_suggestions):
        orchestrator.process_files(str(work_dir / "*.txt"))

    captured = capsys.readouterr()
    assert orchestrator.renamed_count == 3
    assert orchestrator.failed_count == 1
    assert orchestrator.skipped_count == 1
    assert "Processed 5 files:" in captured.out
    assert "3 planned" in captured.out
    assert "1 failed" in captured.out
    assert "1 skipped" in captured.out


def test_continue_on_error_remaining_files_process(mock_config, work_dir, capsys):
    """Test that when one file fails, remaining files still process."""
    for i in range(5):
        (work_dir / f"file_{i}.txt").write_text(f"Content {i}")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)

    # Mock strategy to fail on file 2 and 3
    call_count = [0]
    original_get_suggestions = TextOnlyStrategy.get_suggestions

    def mock_get_suggestions(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] in (2, 3):
            raise RuntimeError(f"Failure {call_count[0]}")
        return original_get_suggestions(self, *args, **kwargs)

    with patch.object(TextOnlyStrategy, "get_suggestions", mock_get_suggestions):
        orchestrator.process_files(str(work_dir / "*.txt"))

    # Files 0, 1, 3, 4 should succeed (indices), files 1, 2 should fail
    assert orchestrator.renamed_count == 3
    assert orchestrator.failed_count == 2
    assert orchestrator.skipped_count == 0


def test_svg_conversion_failure_increments_failed_count(mock_config, work_dir, capsys):
    """Test that SVG conversion failure increments failed_count."""
    svg_file = work_dir / "test.svg"
    svg_file.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>'
    )

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)

    # Mock _convert_svg to return (None, None) indicating failure
    with patch.object(orchestrator, "_convert_svg", return_value=(None, None)):
        orchestrator.process_files(str(svg_file))

    assert orchestrator.renamed_count == 0
    assert orchestrator.failed_count == 1
    assert orchestrator.skipped_count == 0


def test_dispatcher_returns_none_increments_skipped(mock_config, work_dir, capsys):
    """Test that when dispatcher returns None, skipped_count increments."""
    test_file = work_dir / "test.txt"
    test_file.write_text("Content")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)

    # Mock dispatcher to return None
    with patch.object(orchestrator.dispatcher, "process", return_value=None):
        orchestrator.process_files(str(test_file))

    assert orchestrator.renamed_count == 0
    assert orchestrator.failed_count == 0
    assert orchestrator.skipped_count == 1


def test_actual_rename_updates_counts(mock_config, work_dir, capsys):
    """Test that actual renames (not dry-run) update counts correctly."""
    for i in range(3):
        (work_dir / f"file_{i}.txt").write_text(f"Content {i}")

    # Not dry-run
    orchestrator = RenameOrchestrator(mock_config, dry_run=False)
    orchestrator.process_files(str(work_dir / "*.txt"))

    captured = capsys.readouterr()
    assert orchestrator.renamed_count == 3
    assert orchestrator.failed_count == 0
    assert orchestrator.skipped_count == 0
    assert "Processed 3 files:" in captured.out
    assert "3 renamed" in captured.out  # Not "planned"


def test_no_summary_for_zero_files(mock_config, work_dir, capsys):
    """Test that no summary is printed when no files match pattern."""
    orchestrator = RenameOrchestrator(mock_config, dry_run=True)
    orchestrator.process_files(str(work_dir / "*.nonexistent"))

    captured = capsys.readouterr()
    # No summary should be printed
    assert "Processed" not in captured.out


def test_hidden_files_skipped_not_counted(mock_config, work_dir, capsys):
    """Test that hidden files (dotfiles) are skipped and not counted."""
    # Create regular and hidden files
    (work_dir / "visible.txt").write_text("Visible")
    (work_dir / ".hidden.txt").write_text("Hidden")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)
    orchestrator.process_files(str(work_dir / "*.txt"))

    # Only 1 file should be processed (hidden file filtered out before processing)
    assert orchestrator.renamed_count == 1
    assert orchestrator.failed_count == 0
    assert orchestrator.skipped_count == 0


def test_zero_byte_files_skipped_not_counted(mock_config, work_dir, capsys):
    """Test that zero-byte files are skipped and not counted."""
    # Create regular and zero-byte files
    (work_dir / "normal.txt").write_text("Content")
    (work_dir / "empty.txt").write_text("")

    orchestrator = RenameOrchestrator(mock_config, dry_run=True)
    orchestrator.process_files(str(work_dir / "*.txt"))

    # Only 1 file should be processed (zero-byte filtered out)
    assert orchestrator.renamed_count == 1
    assert orchestrator.failed_count == 0
    assert orchestrator.skipped_count == 0
