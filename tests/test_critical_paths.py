"""Tests for critical paths identified in code review.

Covers: thread-safe rate limiting, undo filtering, prompt template validation,
conflict resolver bounds, path traversal sanitization, session ID validation,
custom exceptions, and tiktoken caching.
"""

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

MOCK_CONFIG = str(Path(__file__).resolve().parent / "mock_config.toml")


# --- Thread-safe rate limiter ---


class TestThreadSafeRateLimiter:
    """Test that rate limiter is thread-safe."""

    def test_rate_limit_lock_prevents_race(self):
        """Multiple threads calling _apply_rate_limit don't corrupt _last_call_time."""
        from onomatool.llm_integration import _apply_rate_limit, _rate_limit_lock

        errors = []

        def call_rate_limit():
            try:
                _apply_rate_limit(0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_rate_limit) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Rate limiter raised errors: {errors}"

    def test_rate_limit_with_zero_delay(self):
        """Zero delay should return immediately."""
        from onomatool.llm_integration import _apply_rate_limit

        start = time.monotonic()
        _apply_rate_limit(0.0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1


# --- Undo filtering ---


class TestUndoFiltering:
    """Test that undo only processes successful renames."""

    def test_undo_skips_error_entries(self, tmp_path):
        """Undo should skip entries with status='error'."""
        from onomatool.history import RenameHistory

        db_path = str(tmp_path / "test_history.db")
        history = RenameHistory(db_path)
        session_id = history.create_session(str(tmp_path))

        # Record one successful rename and one error
        src = tmp_path / "original.txt"
        dst = tmp_path / "renamed.txt"
        src.write_text("test")
        dst.write_text("test")

        history.record_rename(session_id, str(src), str(dst), status="ok")
        history.record_rename(session_id, str(src), str(src), status="error")

        results = history.undo_session(session_id)
        # Should only process the "ok" entry, not the "error" one
        assert len(results) == 1
        history.close()

    def test_undo_marks_as_undone(self, tmp_path):
        """Successfully undone renames should be marked as 'undone' in DB."""
        from onomatool.history import RenameHistory

        db_path = str(tmp_path / "test_history.db")
        history = RenameHistory(db_path)
        session_id = history.create_session(str(tmp_path))

        original = tmp_path / "original.txt"
        renamed = tmp_path / "renamed.txt"
        renamed.write_text("test")  # The "renamed" file exists

        history.record_rename(session_id, str(original), str(renamed))
        results = history.undo_session(session_id)

        assert any(r["status"] == "ok" for r in results)

        # Second undo should find no successful renames
        results2 = history.undo_session(session_id)
        assert any("No successful renames" in r.get("message", "") for r in results2)
        history.close()


# --- Prompt template validation ---


class TestPromptTemplateValidation:
    """Test that invalid prompt templates don't crash."""

    def test_user_prompt_with_unknown_placeholder(self):
        """Unknown {placeholder} in user_prompt should not raise KeyError."""
        from onomatool.prompts import get_user_prompt

        config = {
            "user_prompt": "Name this {unknown_key} file: {content}",
            "min_filename_words": 5,
            "max_filename_words": 15,
        }
        result = get_user_prompt("snake_case", "test content", config)
        assert "test content" in result

    def test_image_prompt_with_unknown_placeholder(self):
        """Unknown {placeholder} in image_prompt should not raise KeyError."""
        from onomatool.prompts import get_image_prompt

        config = {
            "image_prompt": "Analyze {bad_key} with {naming_convention}",
            "min_filename_words": 5,
            "max_filename_words": 15,
        }
        result = get_image_prompt("snake_case", config)
        assert "snake_case" in result

    def test_default_prompts_format_correctly(self):
        """Default prompts should format without errors."""
        from onomatool.prompts import get_image_prompt, get_user_prompt

        user = get_user_prompt("snake_case", "sample content")
        assert "sample content" in user

        image = get_image_prompt("camelCase")
        assert "camelCase" in image


# --- Conflict resolver bounds ---


class TestConflictResolverBounds:
    """Test conflict resolver upper bound and set optimization."""

    def test_set_lookup_performance(self):
        """Conflict resolver should use set for O(1) lookups."""
        from onomatool.conflict_resolver import resolve_conflict

        # Large list of existing files
        existing = [f"file_{i}.txt" for i in range(1000)]
        result = resolve_conflict("file_500.txt", existing)
        assert result == "file_500_2.txt"

    def test_upper_bound_raises(self):
        """Should raise after MAX_CONFLICT_ITERATIONS."""
        from onomatool.conflict_resolver import (
            MAX_CONFLICT_ITERATIONS,
            resolve_conflict,
        )
        from onomatool.exceptions import OnomaConflictError

        # Create a list that will exhaust the counter
        existing = ["test.txt"] + [f"test_{i}.txt" for i in range(2, MAX_CONFLICT_ITERATIONS + 3)]
        with pytest.raises(OnomaConflictError):
            resolve_conflict("test.txt", existing)


# --- Path traversal sanitization ---


class TestPathTraversalProtection:
    """Test sanitizer blocks path traversal attacks."""

    def test_dot_dot_in_middle(self):
        """Path traversal in middle of filename is neutralized."""
        from onomatool.sanitizer import sanitize_filename

        result = sanitize_filename("foo..bar")
        assert ".." not in result

    def test_unicode_fullwidth_slash(self):
        """Unicode fullwidth solidus is replaced."""
        from onomatool.sanitizer import sanitize_filename

        result = sanitize_filename("foo\uff0fbar")
        assert "\uff0f" not in result

    def test_unicode_fullwidth_backslash(self):
        """Unicode fullwidth reverse solidus is replaced."""
        from onomatool.sanitizer import sanitize_filename

        result = sanitize_filename("foo\uff3cbar")
        assert "\uff3c" not in result

    def test_leading_dots_still_stripped(self):
        """Leading dots are still stripped (existing behavior preserved)."""
        from onomatool.sanitizer import sanitize_filename

        result = sanitize_filename("..hidden")
        assert result == "hidden"


# --- Session ID validation ---


class TestSessionIDValidation:
    """Test --undo session ID validation."""

    def test_non_numeric_undo_returns_error(self):
        """--undo with non-numeric value should return error code 1."""
        from onomatool.cli import main

        result = main(["--undo", "abc"])
        assert result == 1

    def test_numeric_undo_accepted(self):
        """--undo with numeric value should be accepted (may fail on missing session)."""
        from onomatool.cli import main

        # Will return 0 even if session doesn't exist (just prints no results)
        result = main(["--undo", "99999"])
        assert result == 0


# --- Custom exceptions ---


class TestCustomExceptions:
    """Test custom exception hierarchy."""

    def test_exception_hierarchy(self):
        """All custom exceptions should inherit from OnomaError."""
        from onomatool.exceptions import (
            OnomaConfigError,
            OnomaConflictError,
            OnomaError,
            OnomaLLMError,
            OnomaProcessingError,
        )

        assert issubclass(OnomaConfigError, OnomaError)
        assert issubclass(OnomaLLMError, OnomaError)
        assert issubclass(OnomaProcessingError, OnomaError)
        assert issubclass(OnomaConflictError, OnomaError)
        assert issubclass(OnomaError, Exception)

    def test_exceptions_importable_from_package(self):
        """Exceptions should be importable from onomatool package."""
        from onomatool import (
            OnomaConfigError,
            OnomaConflictError,
            OnomaError,
            OnomaLLMError,
            OnomaProcessingError,
        )

        # Verify they're all exception classes
        for exc_cls in [OnomaError, OnomaConfigError, OnomaLLMError, OnomaProcessingError, OnomaConflictError]:
            assert issubclass(exc_cls, Exception)


# --- Tiktoken caching ---


class TestTiktokenCaching:
    """Test that tiktoken encoder is cached."""

    def test_encoder_cached(self):
        """Same model should return cached encoder."""
        from onomatool.llm_integration import _get_tiktoken_encoding

        enc1 = _get_tiktoken_encoding("gpt-4o")
        enc2 = _get_tiktoken_encoding("gpt-4o")
        assert enc1 is enc2

    def test_unknown_model_falls_back(self):
        """Unknown model should fall back to cl100k_base."""
        from onomatool.llm_integration import _get_tiktoken_encoding

        enc = _get_tiktoken_encoding("nonexistent-model-xyz")
        assert enc is not None


# --- SSL verification config ---


class TestSSLConfig:
    """Test allow_insecure_transport config flag."""

    def test_default_config_has_ssl_enabled(self):
        """Default config should not allow insecure transport."""
        from onomatool.config import DEFAULT_CONFIG

        assert DEFAULT_CONFIG.get("allow_insecure_transport") is False

    def test_config_model_accepts_flag(self):
        """Config model should accept allow_insecure_transport."""
        from onomatool.config import OnomatoolConfig

        config = OnomatoolConfig(allow_insecure_transport=True)
        assert config.allow_insecure_transport is True


# --- RenameHistory context manager ---


class TestHistoryContextManager:
    """Test RenameHistory __enter__/__exit__."""

    def test_context_manager_closes(self, tmp_path):
        """Context manager should close connection on exit."""
        from onomatool.history import RenameHistory

        db_path = str(tmp_path / "test.db")
        with RenameHistory(db_path) as history:
            history.create_session(str(tmp_path))
            assert history._conn is not None

        assert history._conn is None


# --- LLM JSON validation ---


class TestLLMJsonValidation:
    """Test LLM response validation."""

    def test_missing_suggestions_key_raises(self):
        """JSON response without 'suggestions' key should raise RuntimeError."""
        from unittest.mock import MagicMock

        from onomatool.llm_integration import OpenAIProvider

        provider = OpenAIProvider({"openai_api_key": "test"})

        mock_client = MagicMock()
        # First call (structured) fails
        mock_client.beta.chat.completions.parse.side_effect = Exception("not supported")
        # Second call (JSON) returns bad JSON
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"bad_key": "value"}'
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(provider, "_create_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="missing 'suggestions' key"):
                provider.get_suggestions(
                    [{"role": "user", "content": "test"}],
                    MagicMock,
                    {},
                    "gpt-4o",
                    0,
                )
