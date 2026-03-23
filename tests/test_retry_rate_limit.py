import time
from unittest.mock import Mock

import pytest

import onomatool.llm_integration as llm_mod
from onomatool.llm_integration import (
    _apply_rate_limit,
    _call_provider_with_retry,
    _is_transient_error,
    get_suggestions,
)

# --- Mock Providers for Testing ---


class TransientErrorProvider:
    """Mock provider that raises transient errors then succeeds."""

    def __init__(self, fail_count: int):
        self.fail_count = fail_count
        self.call_count = 0

    def get_suggestions(
        self, messages, pydantic_model, json_schema, model, verbose_level
    ):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            # Simulate OpenAI APIStatusError with 503
            from openai import APIStatusError

            raise APIStatusError(
                message="Service Unavailable",
                response=Mock(status_code=503),
                body=None,
            )
        return ["success_one", "success_two", "success_three"]

    def supports_images(self):
        return True


class PermanentErrorProvider:
    """Mock provider that raises a permanent (non-transient) error."""

    def __init__(self):
        self.call_count = 0

    def get_suggestions(
        self, messages, pydantic_model, json_schema, model, verbose_level
    ):
        self.call_count += 1
        raise RuntimeError("Permanent error: invalid API key")

    def supports_images(self):
        return True


class SuccessProvider:
    """Mock provider that always succeeds."""

    def __init__(self):
        self.call_count = 0

    def get_suggestions(
        self, messages, pydantic_model, json_schema, model, verbose_level
    ):
        self.call_count += 1
        return ["file_one", "file_two", "file_three"]

    def supports_images(self):
        return True


# --- Retry Tests ---


def test_tc_ret_001_max_retries_zero_fails_immediately():
    """TC-RET-001: max_retries=0 fails immediately."""
    provider = TransientErrorProvider(fail_count=1)
    messages = [{"role": "user", "content": "test"}]
    pydantic_model = Mock()
    json_schema = {}
    model = "gpt-4o"

    with pytest.raises(Exception):
        _call_provider_with_retry(
            provider,
            messages,
            pydantic_model,
            json_schema,
            model,
            verbose_level=0,
            max_retries=0,
            retry_delay=0.1,
        )

    assert provider.call_count == 1


def test_tc_ret_002_transient_error_retried_up_to_max():
    """TC-RET-002: Transient error retried up to max."""
    provider = TransientErrorProvider(fail_count=2)
    messages = [{"role": "user", "content": "test"}]
    pydantic_model = Mock()
    json_schema = {}
    model = "gpt-4o"

    result = _call_provider_with_retry(
        provider,
        messages,
        pydantic_model,
        json_schema,
        model,
        verbose_level=0,
        max_retries=3,
        retry_delay=0.01,
    )

    assert result == ["success_one", "success_two", "success_three"]
    assert provider.call_count == 3  # Failed twice, succeeded on third


def test_tc_ret_003_permanent_error_not_retried():
    """TC-RET-003: Permanent error not retried."""
    provider = PermanentErrorProvider()
    messages = [{"role": "user", "content": "test"}]
    pydantic_model = Mock()
    json_schema = {}
    model = "gpt-4o"

    with pytest.raises(RuntimeError, match="Permanent error"):
        _call_provider_with_retry(
            provider,
            messages,
            pydantic_model,
            json_schema,
            model,
            verbose_level=0,
            max_retries=3,
            retry_delay=0.01,
        )

    assert provider.call_count == 1  # Only called once


def test_tc_ret_004_exponential_backoff_timing():
    """TC-RET-004: Exponential backoff timing."""
    provider = TransientErrorProvider(fail_count=3)
    messages = [{"role": "user", "content": "test"}]
    pydantic_model = Mock()
    json_schema = {}
    model = "gpt-4o"
    retry_delay = 0.1

    start = time.monotonic()
    result = _call_provider_with_retry(
        provider,
        messages,
        pydantic_model,
        json_schema,
        model,
        verbose_level=0,
        max_retries=3,
        retry_delay=retry_delay,
    )
    elapsed = time.monotonic() - start

    assert result == ["success_one", "success_two", "success_three"]
    assert provider.call_count == 4

    # Expected delays: 0.1 * 2^0 + 0.1 * 2^1 + 0.1 * 2^2 = 0.1 + 0.2 + 0.4 = 0.7
    expected_min = 0.7
    expected_max = 1.0  # Allow some overhead
    assert expected_min <= elapsed <= expected_max, f"elapsed={elapsed:.2f}s"


def test_tc_ret_005_retry_attempts_logged_at_warning(caplog):
    """TC-RET-005: Retry attempts logged at WARNING."""
    provider = TransientErrorProvider(fail_count=2)
    messages = [{"role": "user", "content": "test"}]
    pydantic_model = Mock()
    json_schema = {}
    model = "gpt-4o"

    with caplog.at_level("WARNING"):
        _call_provider_with_retry(
            provider,
            messages,
            pydantic_model,
            json_schema,
            model,
            verbose_level=0,
            max_retries=3,
            retry_delay=0.01,
        )

    # Should have 2 warning messages for the 2 failures
    warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert len(warnings) == 2
    assert "LLM call failed" in warnings[0].message
    assert "retrying in" in warnings[0].message


# --- Rate Limit Tests ---


def test_tc_rl_001_rate_limit_delay_inserts_pause():
    """TC-RL-001: rate_limit_delay inserts pause between calls."""
    # Reset module-level _last_call_time
    llm_mod._last_call_time = 0.0

    config = {
        "default_provider": "mock",
        "naming_convention": "snake_case",
        "rate_limit_delay": 0.3,
        "max_retries": 0,
    }

    start = time.monotonic()
    # First call - no delay
    get_suggestions("content1", verbose_level=0, config=config)
    # Second call - should wait ~0.3s
    get_suggestions("content2", verbose_level=0, config=config)
    # Third call - should wait ~0.3s
    get_suggestions("content3", verbose_level=0, config=config)
    elapsed = time.monotonic() - start

    # Expected: 2 delays of 0.3s each = 0.6s minimum
    expected_min = 0.6
    expected_max = 1.0
    assert expected_min <= elapsed <= expected_max, f"elapsed={elapsed:.2f}s"

    # Cleanup
    llm_mod._last_call_time = 0.0


def test_tc_rl_002_rate_limit_delay_zero_has_no_effect():
    """TC-RL-002: rate_limit_delay=0 has no effect."""
    # Reset module-level _last_call_time
    llm_mod._last_call_time = 0.0

    config = {
        "default_provider": "mock",
        "naming_convention": "snake_case",
        "rate_limit_delay": 0.0,
        "max_retries": 0,
    }

    start = time.monotonic()
    get_suggestions("content1", verbose_level=0, config=config)
    get_suggestions("content2", verbose_level=0, config=config)
    get_suggestions("content3", verbose_level=0, config=config)
    elapsed = time.monotonic() - start

    # Should complete almost instantly
    assert elapsed < 0.1, f"elapsed={elapsed:.2f}s"

    # Cleanup
    llm_mod._last_call_time = 0.0


def test_tc_rl_003_rate_limiting_is_provider_agnostic():
    """TC-RL-003: Rate limiting works regardless of provider."""
    # Reset module-level _last_call_time
    llm_mod._last_call_time = 0.0

    # Test with _apply_rate_limit directly
    delay = 0.2

    # First call - set timestamp
    llm_mod._last_call_time = time.monotonic()

    # Second call - should wait
    start = time.monotonic()
    _apply_rate_limit(delay, verbose_level=0)
    elapsed = time.monotonic() - start

    expected_min = 0.15  # Allow some timing variance
    expected_max = 0.3
    assert expected_min <= elapsed <= expected_max, f"elapsed={elapsed:.2f}s"

    # Cleanup
    llm_mod._last_call_time = 0.0


def test_is_transient_error_openai_timeout():
    """Test that OpenAI timeout errors are considered transient."""
    from openai import APITimeoutError

    err = APITimeoutError(request=Mock())
    assert _is_transient_error(err) is True


def test_is_transient_error_openai_connection():
    """Test that OpenAI connection errors are considered transient."""
    from openai import APIConnectionError

    err = APIConnectionError(request=Mock())
    assert _is_transient_error(err) is True


def test_is_transient_error_openai_status_500():
    """Test that OpenAI 500+ status errors are considered transient."""
    from openai import APIStatusError

    err = APIStatusError(
        message="Server Error",
        response=Mock(status_code=503),
        body=None,
    )
    assert _is_transient_error(err) is True


def test_is_transient_error_openai_status_429():
    """Test that OpenAI 429 rate limit errors are considered transient."""
    from openai import APIStatusError

    err = APIStatusError(
        message="Rate Limit",
        response=Mock(status_code=429),
        body=None,
    )
    assert _is_transient_error(err) is True


def test_is_transient_error_openai_status_400():
    """Test that OpenAI 400 errors are NOT considered transient."""
    from openai import APIStatusError

    err = APIStatusError(
        message="Bad Request",
        response=Mock(status_code=400),
        body=None,
    )
    assert _is_transient_error(err) is False


def test_is_transient_error_google_timeout():
    """Test that Google timeout string errors are considered transient."""
    err = Exception("Request timeout occurred")
    assert _is_transient_error(err) is True


def test_is_transient_error_google_rate_limit():
    """Test that Google rate limit string errors are considered transient."""
    err = Exception("Rate limit exceeded")
    assert _is_transient_error(err) is True


def test_is_transient_error_permanent():
    """Test that permanent errors are NOT considered transient."""
    err = RuntimeError("Invalid API key")
    assert _is_transient_error(err) is False
