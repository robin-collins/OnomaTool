import os

from onomatool.file_collector import collect_files


def test_collect_files_basic(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("1")
    f2.write_text("2")
    files = collect_files(str(tmp_path / "*.txt"))
    assert set(map(os.path.basename, files)) == {"a.txt", "b.txt"}


def test_collect_files_recursive(tmp_path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "c.txt").write_text("3")
    files = collect_files(str(tmp_path / "**/*.txt"))
    assert any("c.txt" in f for f in files)


def test_collect_files_no_match(tmp_path):
    files = collect_files(str(tmp_path / "*.nomatch"))
    assert files == []


# Edge case tests (§2.6)


def test_symlink_to_file_included(tmp_path):
    """TC-FC-001: Symlinks to real files are included (os.path.isfile returns True)."""
    real_file = tmp_path / "real.txt"
    real_file.write_text("data")
    link = tmp_path / "link.txt"
    link.symlink_to(real_file)
    files = collect_files(str(tmp_path / "*.txt"))
    basenames = {os.path.basename(f) for f in files}
    assert "real.txt" in basenames
    assert "link.txt" in basenames


def test_broken_symlink_filtered(tmp_path):
    """TC-FC-002: Broken symlinks are filtered out."""
    link = tmp_path / "broken.txt"
    link.symlink_to(tmp_path / "nonexistent.txt")
    files = collect_files(str(tmp_path / "*.txt"))
    assert files == []


def test_directory_filtered(tmp_path):
    """TC-FC-003: Directories matching glob are filtered out."""
    # Create a directory that could match *.txt pattern
    (tmp_path / "folder.txt").mkdir()
    (tmp_path / "real.txt").write_text("data")
    files = collect_files(str(tmp_path / "*.txt"))
    assert len(files) == 1
    assert os.path.basename(files[0]) == "real.txt"
