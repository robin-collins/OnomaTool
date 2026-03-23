from onomatool.conflict_resolver import resolve_conflict


def test_no_conflict():
    assert resolve_conflict("file.txt", ["other.txt"]) == "file.txt"


def test_single_conflict():
    assert resolve_conflict("file.txt", ["file.txt"]) == "file_2.txt"


def test_multiple_conflicts():
    existing = ["file.txt", "file_2.txt", "file_3.txt"]
    assert resolve_conflict("file.txt", existing) == "file_4.txt"


def test_conflict_with_number_suffix():
    existing = ["file.txt", "file_2.txt", "file_3.txt", "file_4.txt"]
    assert resolve_conflict("file.txt", existing) == "file_5.txt"


# Edge case tests (§2.2)


def test_no_extension():
    """TC-CR-001: File without extension gets numeric suffix."""
    assert resolve_conflict("README", ["README"]) == "README_2"


def test_dotfile():
    """TC-CR-002: Dotfiles resolve correctly."""
    assert resolve_conflict(".gitignore", [".gitignore"]) == ".gitignore_2"


def test_multiple_dots():
    """TC-CR-003: Files with multiple dots preserve all but last as base."""
    assert resolve_conflict("archive.tar.gz", ["archive.tar.gz"]) == "archive.tar_2.gz"


def test_1000_conflicts():
    """TC-CR-004: Performance with many conflicts."""
    existing = ["file.txt"] + [f"file_{i}.txt" for i in range(2, 1001)]
    result = resolve_conflict("file.txt", existing)
    assert result == "file_1001.txt"


def test_empty_existing_list():
    """TC-CR-005: Empty existing list returns desired name unchanged."""
    assert resolve_conflict("anything.pdf", []) == "anything.pdf"
