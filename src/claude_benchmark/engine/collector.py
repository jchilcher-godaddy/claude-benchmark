"""Result collection from Claude Code SDK messages.

Processes the stream of messages from query() and extracts structured data
including token usage, cost, duration, and success/error status.
"""

from __future__ import annotations

from typing import Any


def collect_result(messages: list[Any]) -> dict[str, Any]:
    """Extract structured result data from SDK messages.

    Processes the list of messages accumulated from the claude_code_sdk.query()
    async generator. Looks for a ResultMessage (identified by having a 'subtype'
    attribute) to extract timing, usage, cost, and status information.

    Args:
        messages: List of message objects yielded by query().
            Expected types: UserMessage, AssistantMessage, SystemMessage, ResultMessage.

    Returns:
        Dict with keys: success, wall_clock_seconds, duration_ms, duration_api_ms,
        total_cost_usd, num_turns, session_id, usage (dict), result_text, error.
    """
    # Find the ResultMessage -- it has subtype, duration_ms, is_error, etc.
    result_msg = None
    for msg in messages:
        if hasattr(msg, "subtype") and hasattr(msg, "duration_ms"):
            result_msg = msg

    if result_msg is None:
        return {
            "success": False,
            "wall_clock_seconds": 0.0,
            "duration_ms": 0,
            "duration_api_ms": 0,
            "total_cost_usd": None,
            "num_turns": 0,
            "session_id": None,
            "usage": None,
            "result_text": None,
            "error": "No result message received",
        }

    # Extract usage data from the result message
    usage = None
    if result_msg.usage:
        raw_usage = result_msg.usage
        usage = {
            "input_tokens": raw_usage.get("input_tokens", 0),
            "output_tokens": raw_usage.get("output_tokens", 0),
            "cache_creation_input_tokens": raw_usage.get(
                "cache_creation_input_tokens", 0
            ),
            "cache_read_input_tokens": raw_usage.get("cache_read_input_tokens", 0),
        }

    # Determine success/error from result message
    is_error = getattr(result_msg, "is_error", False)
    error = None
    if is_error:
        error = getattr(result_msg, "result", None) or "Unknown error from Claude Code"

    return {
        "success": not is_error,
        "duration_ms": getattr(result_msg, "duration_ms", 0),
        "duration_api_ms": getattr(result_msg, "duration_api_ms", 0),
        "total_cost_usd": getattr(result_msg, "total_cost_usd", None),
        "num_turns": getattr(result_msg, "num_turns", 0),
        "session_id": getattr(result_msg, "session_id", None),
        "usage": usage,
        "result_text": getattr(result_msg, "result", None),
        "error": error,
    }
