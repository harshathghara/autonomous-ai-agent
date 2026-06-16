"""Tests for LLM error formatting and tool-arg normalization."""

from agent.llm_errors import (
    format_llm_error,
    is_retryable_llm_error,
    is_rate_limit_error,
    normalize_tool_args,
    retry_delay_seconds,
)


def test_normalize_tool_args_dict():
    assert normalize_tool_args({"query": "cricket"}) == {"query": "cricket"}


def test_normalize_tool_args_json_string():
    assert normalize_tool_args('{"query": "cricket"}') == {"query": "cricket"}


def test_is_retryable_tool_use_failed():
    exc = Exception(
        "Error code: 400 - {'error': {'code': 'tool_use_failed', 'message': 'Failed to call a function.'}}"
    )
    assert is_retryable_llm_error(exc) is True


def test_format_llm_error_includes_partial_generation():
    exc = Exception(
        "Error code: 400 - {'error': {'code': 'tool_use_failed', "
        "'failed_generation': 'India are 368/3 at stumps.'}}"
    )
    msg = format_llm_error(exc)
    assert "formatting error" in msg
    assert "368/3" in msg


def test_is_rate_limit_error():
    exc = Exception("Error code: 429 - rate limit exceeded")
    assert is_rate_limit_error(exc) is True
    assert is_retryable_llm_error(exc) is True
    assert retry_delay_seconds(exc, 1) == 2.0
