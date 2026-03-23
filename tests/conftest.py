"""Shared test fixtures for OnomaTool test suite."""

import shutil
import tempfile
from pathlib import Path

import pytest

# Absolute path to the read-only example files directory
EXAMPLE_FILES_DIR = Path(__file__).resolve().parent.parent / "example_files"

# Absolute path to test-specific config files
TEST_DIR = Path(__file__).resolve().parent
MOCK_CONFIG = str(TEST_DIR / "mock_config.toml")


@pytest.fixture
def example_files_dir():
    """Return the path to the read-only example_files directory.

    Use this for tests that only need to READ file contents.
    Do NOT modify files through this path.
    """
    return EXAMPLE_FILES_DIR


@pytest.fixture
def work_dir():
    """Create an isolated temporary directory for tests that modify files.

    Automatically cleaned up after the test completes.
    """
    temp_dir = tempfile.mkdtemp(prefix="onomatool_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def copy_example_file(work_dir):
    """Factory fixture that copies a file from example_files/ to the temp work_dir.

    Usage:
        def test_something(copy_example_file):
            file_path = copy_example_file("note_0.md")
            # file_path is now a writable copy in a temp directory
    """

    def _copy(filename):
        src = EXAMPLE_FILES_DIR / filename
        dst = work_dir / filename
        shutil.copy2(str(src), str(dst))
        return str(dst)

    return _copy
