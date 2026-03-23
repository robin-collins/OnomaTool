"""Security invariant tests (§20)."""

import inspect

from onomatool.llm_integration import MAX_CONTENT_CHARS, MAX_TOKENS, is_image_file


def test_content_truncation_limit():
    """TC-SEC-001: MAX_CONTENT_CHARS is set and reasonable."""
    assert MAX_CONTENT_CHARS == 120_000


def test_max_tokens_limit():
    """TC-SEC-002: MAX_TOKENS limits LLM response size."""
    assert MAX_TOKENS == 100


def test_svg_guard():
    """TC-SEC-003: SVG files are detected as images (must be converted to PNG first)."""
    assert is_image_file("test.svg") is True
    assert is_image_file("test.SVG") is True


def test_svg_raw_rejection():
    """TC-SEC-004: Raw SVG sent to LLM raises RuntimeError."""
    import pytest

    from onomatool.llm_integration import get_suggestions

    config = {"default_provider": "mock", "naming_convention": "snake_case"}
    with pytest.raises(RuntimeError, match="Raw SVG"):
        get_suggestions("content", file_path="test.svg", config=config)


def test_shutil_move_used():
    """TC-SEC-005: renamer uses shutil.move (not os.rename) for cross-device safety."""
    from onomatool import renamer

    source = inspect.getsource(renamer.rename_file)
    assert "shutil.move" in source


def test_extension_always_preserved():
    """TC-SEC-006: rename_file preserves original extension."""
    from onomatool import renamer

    source = inspect.getsource(renamer.rename_file)
    assert "os.path.splitext(original_path)" in source


def test_conflict_resolution_prevents_overwrite():
    """TC-SEC-007: Conflict resolver never returns an existing name."""
    from onomatool.conflict_resolver import resolve_conflict

    existing = ["file.txt", "file_2.txt"]
    result = resolve_conflict("file.txt", existing)
    assert result not in existing
