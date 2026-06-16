"""Format and classify Groq / LLM API errors for the agent runner."""

import json
import re
from typing import Any


def _extract_failed_generation(text: str) -> str | None:
    marker = "'failed_generation':"
    idx = text.find(marker)
    if idx < 0:
        marker = '"failed_generation":'
        idx = text.find(marker)
    if idx < 0:
        return None
    rest = text[idx + len(marker) :].lstrip()
    if not rest:
        return None
    quote = rest[0]
    if quote not in ("'", '"'):
        return None
    out: list[str] = []
    i = 1
    while i < len(rest):
        ch = rest[i]
        if ch == "\\" and i + 1 < len(rest):
            nxt = rest[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            else:
                out.append(nxt)
            i += 2
            continue
        if ch == quote:
            return "".join(out).strip()
        out.append(ch)
        i += 1
    return "".join(out).strip() or None


def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "rate limit" in text or "429" in text or "too many requests" in text


def is_retryable_llm_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        is_rate_limit_error(exc)
        or "tool_use_failed" in text
        or "failed to call a function" in text
    )


def retry_delay_seconds(exc: Exception, attempt: int) -> float:
    """Exponential backoff for rate limits; immediate retry for format errors."""
    if is_rate_limit_error(exc):
        return float(min(30, 2**attempt))
    return 0.0


def format_llm_error(exc: Exception) -> str:
    """Turn raw API exceptions into a short user-facing message."""
    text = str(exc)
    if is_rate_limit_error(exc):
        return "Groq rate limit reached. Wait a moment and try again."

    if not ("tool_use_failed" in text.lower() or "failed to call a function" in text.lower()):
        return text

    partial = _extract_failed_generation(text)
    if partial:
        snippet = partial[:600] + ("…" if len(partial) > 600 else "")
        return (
            "The model hit a formatting error while writing the answer. "
            f"Partial response: {snippet}"
        )

    return (
        "The model hit a formatting error while writing the answer. "
        "Try rephrasing (e.g. include today's date for live scores) or run again."
    )


def normalize_tool_args(args: Any) -> dict:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"raw": args}
    return {"value": args}
