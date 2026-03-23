"""Tests for cross-platform filename sanitization (§8)."""

from onomatool.sanitizer import sanitize_filename


def test_clean_filename_unchanged():
    """Clean filenames pass through unchanged."""
    assert sanitize_filename("hello_world") == "hello_world"
    assert sanitize_filename("my-file.txt") == "my-file.txt"


def test_windows_illegal_chars_replaced():
    """Windows-illegal characters are replaced with underscore."""
    assert sanitize_filename("file<name>.txt") == "file_name_.txt"
    assert sanitize_filename("file:name") == "file_name"
    assert sanitize_filename("path/to\\file") == "path_to_file"
    assert sanitize_filename("what?*") == "what__"


def test_reserved_names_prefixed():
    """Windows reserved names get an underscore prefix."""
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("PRN.txt") == "_PRN.txt"
    assert sanitize_filename("NUL") == "_NUL"
    assert sanitize_filename("COM1") == "_COM1"
    assert sanitize_filename("LPT3.log") == "_LPT3.log"


def test_leading_trailing_dots_stripped():
    """Leading/trailing dots and spaces are stripped."""
    assert sanitize_filename("..hidden") == "hidden"
    assert sanitize_filename("  spaces  ") == "spaces"
    assert sanitize_filename("...dots...") == "dots"


def test_control_chars_replaced():
    """Control characters are replaced with underscore."""
    assert sanitize_filename("file\x00name") == "file_name"
    assert sanitize_filename("tab\there") == "tab_here"


def test_max_length_enforced():
    """Filenames exceeding 255 bytes are truncated."""
    long_name = "a" * 300
    result = sanitize_filename(long_name)
    assert len(result.encode("utf-8")) <= 255


def test_max_length_preserves_extension():
    """Long filenames with extensions preserve the extension."""
    long_name = "a" * 300 + ".txt"
    result = sanitize_filename(long_name)
    assert result.endswith(".txt")
    assert len(result.encode("utf-8")) <= 255


def test_empty_after_sanitize():
    """Completely invalid names fall back to 'unnamed'."""
    assert sanitize_filename("...") == "unnamed"
    assert sanitize_filename("   ") == "unnamed"


def test_unicode_preserved():
    """Unicode characters in filenames are preserved."""
    assert sanitize_filename("café_résumé") == "café_résumé"
    assert sanitize_filename("日本語ファイル") == "日本語ファイル"
