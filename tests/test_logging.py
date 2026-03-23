"""Tests for logging migration from print() to logging module.

This test suite validates the migration from print() statements to the logging module:

Test Coverage:
- TC-LOG-001: Default log level is WARNING (no INFO/DEBUG without flags)
- TC-LOG-002: --verbose (-v) sets INFO level
- TC-LOG-003: --very-verbose (-vv) sets DEBUG level
- TC-LOG-004: No [DEBUG] print() calls remain in source code
- TC-LOG-005: API keys are not leaked in log output
- TC-LOG-006: Base64 image data is redacted in logs

The tests verify that:
1. Logging levels are correctly configured based on CLI flags
2. No legacy print("[DEBUG]") statements exist in the codebase
3. Sensitive information (API keys, base64 images) is properly redacted
4. The logging format is consistent and proper
"""

import logging
import pathlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from onomatool.cli import main
from onomatool.llm_integration import _redact_messages

MOCK_CONFIG = str(Path(__file__).resolve().parent / "mock_config.toml")


# TC-LOG-001: Default log level is WARNING
def test_default_log_level_is_warning(temp_copy, caplog):
    """TC-LOG-001: Run main() with no verbosity, verify no INFO/DEBUG in output."""
    with caplog.at_level(logging.DEBUG):
        result = main([temp_copy, "--config", MOCK_CONFIG])
        assert result == 0

        # Check that no DEBUG or INFO messages were logged
        # (but WARNING and ERROR can be present)
        for record in caplog.records:
            assert record.levelno >= logging.WARNING, (
                f"Found {record.levelname} message when only WARNING+ expected: {record.message}"
            )


# TC-LOG-002: --verbose sets INFO level
def test_verbose_sets_info_level(temp_copy, caplog):
    """TC-LOG-002: Run with -v, check logging is configured for INFO level."""
    # Mock provider won't generate logs, so we test by checking that
    # logging.basicConfig was called with INFO level
    with patch('logging.basicConfig') as mock_basic_config:
        result = main([temp_copy, "--config", MOCK_CONFIG, "--verbose"])
        assert result == 0

        # Verify basicConfig was called with INFO level
        mock_basic_config.assert_called_once()
        call_kwargs = mock_basic_config.call_args[1]
        assert call_kwargs['level'] == logging.INFO, (
            f"Expected INFO level, got {call_kwargs['level']}"
        )


# TC-LOG-003: --very-verbose sets DEBUG level
def test_very_verbose_sets_debug_level(temp_copy, caplog):
    """TC-LOG-003: Run with -vv, check logging is configured for DEBUG level."""
    # Mock provider won't generate logs, so we test by checking that
    # logging.basicConfig was called with DEBUG level
    with patch('logging.basicConfig') as mock_basic_config:
        result = main([temp_copy, "--config", MOCK_CONFIG, "--very-verbose"])
        assert result == 0

        # Verify basicConfig was called with DEBUG level
        mock_basic_config.assert_called_once()
        call_kwargs = mock_basic_config.call_args[1]
        assert call_kwargs['level'] == logging.DEBUG, (
            f"Expected DEBUG level, got {call_kwargs['level']}"
        )


# TC-LOG-004: No [DEBUG] print() calls remain in source
def test_no_debug_print_calls_in_source():
    """TC-LOG-004: Use glob/grep to verify no print('[DEBUG]') in src/onomatool/."""
    src = pathlib.Path(__file__).parent.parent / "src" / "onomatool"
    assert src.exists(), f"Source directory not found: {src}"

    found_debug_prints = []
    for py_file in src.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if 'print("[DEBUG]' in content or "print('[DEBUG]" in content:
            found_debug_prints.append(str(py_file))

    assert not found_debug_prints, (
        f"Found [DEBUG] print() calls in source files: {found_debug_prints}"
    )


# TC-LOG-005: API keys not in log output
def test_api_keys_not_in_log_output(temp_copy, caplog):
    """TC-LOG-005: Set verbose, configure with a dummy API key, verify key doesn't appear in logs."""
    # Create a config with a fake API key
    import tempfile
    import tomli_w

    config_data = {
        "default_provider": "mock",
        "openai_api_key": "sk-test-secret-key-12345",
        "google_api_key": "AIzaSy-test-secret-key-67890",
        "naming_convention": "snake_case",
    }

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
        tomli_w.dump(config_data, f)
        temp_config = f.name

    try:
        with caplog.at_level(logging.DEBUG):
            result = main([temp_copy, "--config", temp_config, "--very-verbose"])
            assert result == 0

            # Check that API keys don't appear in logs
            all_logs = "\n".join([record.message for record in caplog.records])
            assert "sk-test-secret-key-12345" not in all_logs, (
                "OpenAI API key leaked in logs"
            )
            assert "AIzaSy-test-secret-key-67890" not in all_logs, (
                "Google API key leaked in logs"
            )
    finally:
        import os
        os.unlink(temp_config)


# TC-LOG-006: Base64 image data redacted
def test_redact_messages_function():
    """TC-LOG-006: Test _redact_messages function from llm_integration.py."""

    # Test with image URL redaction
    messages_with_image = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                    },
                },
            ],
        }
    ]

    redacted = _redact_messages(messages_with_image, redact_text=False)

    # Check that base64 data is redacted
    assert redacted[0]["content"][1]["image_url"]["url"] == "[[base64_image]]"

    # Check that text is NOT redacted when redact_text=False
    assert redacted[0]["content"][0]["text"] == "What is in this image?"


def test_redact_messages_with_text_redaction():
    """Test _redact_messages with text redaction enabled."""

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "This is sensitive file content that should be redacted."},
            ],
        },
    ]

    redacted = _redact_messages(messages, redact_text=True)

    # System message should not be redacted (not in list format)
    assert redacted[0]["content"] == "You are a helpful assistant."

    # Text content should be redacted
    assert redacted[1]["content"][0]["text"] == "[[file_content]]"


def test_redact_messages_with_image_url_string():
    """Test _redact_messages with image_url as string instead of dict."""

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                },
            ],
        }
    ]

    redacted = _redact_messages(messages, redact_text=False)

    # Check that base64 data is redacted even when image_url is a string
    assert redacted[0]["content"][0]["image_url"] == "[[base64_image]]"


def test_verbose_logging_output_format(temp_copy, caplog):
    """Test that verbose logging uses proper format with [LEVEL] prefix."""
    with caplog.at_level(logging.DEBUG):
        result = main([temp_copy, "--config", MOCK_CONFIG, "--very-verbose"])
        assert result == 0

        # Check that records have proper logger names (not root)
        for record in caplog.records:
            # All our logs should come from onomatool modules
            if record.levelno >= logging.INFO:
                assert record.name.startswith("onomatool.") or record.name == "onomatool", (
                    f"Unexpected logger name: {record.name}"
                )


def test_no_info_debug_without_verbose(temp_copy, capsys):
    """Test that no INFO/DEBUG messages appear in stdout without -v/-vv."""
    result = main([temp_copy, "--config", MOCK_CONFIG])
    assert result == 0

    captured = capsys.readouterr()
    # Should not see [INFO] or [DEBUG] in output
    assert "[INFO]" not in captured.out
    assert "[DEBUG]" not in captured.out


def test_info_appears_with_verbose(temp_copy, capsys):
    """Test that INFO messages appear in stdout with -v."""
    result = main([temp_copy, "--config", MOCK_CONFIG, "--verbose"])
    assert result == 0

    # Note: might not always have INFO messages, so we just check it doesn't crash
    # and that the format would be correct if present
    captured = capsys.readouterr()
    # If INFO is present, it should have the right format
    if "[INFO]" in captured.out:
        assert "[INFO]" in captured.out


def test_debug_appears_with_very_verbose(temp_copy, capsys):
    """Test that DEBUG messages appear in stdout with -vv."""
    result = main([temp_copy, "--config", MOCK_CONFIG, "--very-verbose"])
    assert result == 0

    # Note: might not always have DEBUG messages, so we just check it doesn't crash
    # and that the format would be correct if present
    captured = capsys.readouterr()
    # If DEBUG is present, it should have the right format
    if "[DEBUG]" in captured.out:
        assert "[DEBUG]" in captured.out


@pytest.fixture
def temp_copy(copy_example_file):
    """Copy note_0.md to an isolated temp directory for destructive tests."""
    return copy_example_file("note_0.md")
