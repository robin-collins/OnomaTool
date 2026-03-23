"""Performance benchmark tests.

TEST_SPECS §21: 4 tests TC-PERF-001 to TC-PERF-004, all marked @pytest.mark.slow.
- Conflict resolution: 1000 files < 100ms
- Token counting: < 500ms
- File collector: 10K files < 2s
- Config loading: < 50ms
"""

import time

import pytest

from onomatool.config import get_config
from onomatool.conflict_resolver import resolve_conflict
from onomatool.file_collector import collect_files
from onomatool.llm_integration import count_text_tokens, count_tokens_for_messages


@pytest.mark.slow
class TestPerformanceBenchmarks:
    """Performance benchmark tests — all marked @pytest.mark.slow."""

    def test_conflict_resolution_1000_files(self):
        """TC-PERF-001: Conflict resolution with 1000 existing files completes in < 100ms.

        resolve_conflict must handle large sets of existing filenames efficiently.
        """
        existing_names = [f"document_{i}.pdf" for i in range(1000)]

        start = time.perf_counter()
        result = resolve_conflict("document_1.pdf", existing_names)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result not in existing_names
        assert result.startswith("document_1")
        assert result.endswith(".pdf")
        assert elapsed_ms < 100, (
            f"Conflict resolution took {elapsed_ms:.1f}ms (limit: 100ms)"
        )

    def test_token_counting_performance(self):
        """TC-PERF-002: Token counting for a large text completes in < 500ms.

        count_text_tokens and count_tokens_for_messages should handle
        realistically large inputs efficiently. First call warms up tiktoken
        encoding cache, so we measure the second call.
        """
        # ~120K chars, similar to MAX_CONTENT_CHARS
        large_text = "This is a sample sentence for token counting. " * 2500

        # Warm up tiktoken encoding cache (first load is slow)
        count_text_tokens("warmup", "gpt-4o")

        start = time.perf_counter()
        token_count = count_text_tokens(large_text, "gpt-4o")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert token_count > 0
        assert elapsed_ms < 500, (
            f"count_text_tokens took {elapsed_ms:.1f}ms (limit: 500ms)"
        )

        # Also test count_tokens_for_messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": large_text},
        ]

        start = time.perf_counter()
        msg_tokens = count_tokens_for_messages(messages, "gpt-4o")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert msg_tokens > token_count  # messages add overhead tokens
        assert elapsed_ms < 500, (
            f"count_tokens_for_messages took {elapsed_ms:.1f}ms (limit: 500ms)"
        )

    def test_file_collector_10k_files(self, tmp_path):
        """TC-PERF-003: File collector handles 10K files in < 2s.

        collect_files with a glob pattern over a directory containing
        10,000 files should complete within the time budget.
        """
        # Create 10K small files
        for i in range(10_000):
            (tmp_path / f"file_{i:05d}.txt").write_text(f"content {i}")

        pattern = str(tmp_path / "*.txt")

        start = time.perf_counter()
        files = collect_files(pattern)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(files) == 10_000
        assert elapsed_ms < 2000, (
            f"File collector took {elapsed_ms:.1f}ms (limit: 2000ms)"
        )

    def test_config_loading_performance(self, tmp_path):
        """TC-PERF-004: Config loading completes in < 50ms.

        Loading and validating a config file through the Pydantic model
        should be fast enough for CLI startup.
        """
        # Write a realistic config file
        config_file = tmp_path / ".onomarc"
        config_file.write_text(
            "[]\n"  # empty TOML is valid
            "config_version = 1\n"
            'default_provider = "openai"\n'
            'openai_api_key = "sk-test-key-12345"\n'
            'naming_convention = "snake_case"\n'
            'llm_model = "gpt-4o"\n'
            "min_filename_words = 5\n"
            "max_filename_words = 15\n"
            "max_retries = 2\n"
            "retry_delay = 1.0\n"
            "rate_limit_delay = 0.5\n"
        )

        start = time.perf_counter()
        config = get_config(str(config_file))
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert config["default_provider"] == "openai"
        assert elapsed_ms < 50, f"Config loading took {elapsed_ms:.1f}ms (limit: 50ms)"
