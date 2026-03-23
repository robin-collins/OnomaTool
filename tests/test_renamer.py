from onomatool.renamer import rename_file


def test_rename_file_success(tmp_path, monkeypatch):
    src = tmp_path / "original.txt"
    src.write_text("data")
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    rename_file(str(src), "renamed.txt")
    assert not src.exists()
    assert (tmp_path / "renamed.txt").exists()


def test_rename_file_conflict(tmp_path, monkeypatch):
    src = tmp_path / "original.txt"
    src.write_text("data")
    (tmp_path / "renamed.txt").write_text("other")
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    rename_file(str(src), "renamed.txt")
    assert not src.exists()
    assert (tmp_path / "renamed_2.txt").exists()


def test_rename_file_extension_preserved(tmp_path, monkeypatch):
    src = tmp_path / "original.md"
    src.write_text("data")
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    rename_file(str(src), "renamed.txt")
    # Should preserve .md extension
    assert (tmp_path / "renamed.md").exists()


# Edge case tests (§2.3)


def test_content_preserved(tmp_path):
    """TC-RN-001: File content is preserved after rename."""
    src = tmp_path / "original.txt"
    src.write_text("important data 12345")
    rename_file(str(src), "new_name.txt")
    renamed = tmp_path / "new_name.txt"
    assert renamed.exists()
    assert renamed.read_text() == "important data 12345"


def test_unicode_filename(tmp_path):
    """TC-RN-002: Unicode filenames are handled."""
    src = tmp_path / "café.txt"
    src.write_text("data")
    rename_file(str(src), "renamed.txt")
    assert (tmp_path / "renamed.txt").exists()
    assert not src.exists()


def test_rename_preserves_binary_content(tmp_path):
    """TC-RN-003: Binary file content is preserved after rename."""
    src = tmp_path / "image.png"
    binary_data = bytes(range(256))
    src.write_bytes(binary_data)
    rename_file(str(src), "new_image.png")
    renamed = tmp_path / "new_image.png"
    assert renamed.exists()
    assert renamed.read_bytes() == binary_data
