"""Core single-run execution engine using Claude Code SDK.

Provides execute_run() which invokes Claude Code against a task in an isolated
workspace and captures the results as a structured RunResult.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from claude_code_sdk import ClaudeCodeOptions, query

from claude_benchmark.engine.collector import collect_result
from claude_benchmark.engine.workspace import capture_workspace_files
from claude_benchmark.results.schema import RunResult, TokenUsage

DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes per run
DEFAULT_MAX_TURNS = 50


async def execute_run(
    workspace_dir: Path,
    prompt: str,
    model: str,
    run_number: int,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> RunResult:
    """Execute a single benchmark run via Claude Code SDK.

    Invokes Claude Code with the given prompt in the workspace directory.
    The workspace should already contain CLAUDE.md and any task fixtures
    (created by create_workspace). Claude Code loads CLAUDE.md automatically
    from the cwd.

    Args:
        workspace_dir: Isolated temp workspace with CLAUDE.md and task fixtures.
        prompt: The task prompt to send to Claude.
        model: Model alias ("haiku", "sonnet", "opus") or full model name.
        run_number: Which run this is (1-indexed).
        timeout_seconds: Wall-clock timeout (default 300s).

    Returns:
        RunResult with token usage, timing, output files, and success status.
        On failure, returns RunResult with success=False and error message.
    """
    start_time = time.monotonic()
    messages: list = []

    try:
        async def _run() -> None:
            async for message in query(
                prompt=prompt,
                options=ClaudeCodeOptions(
                    model=model,
                    cwd=str(workspace_dir),
                    permission_mode="bypassPermissions",
                    max_turns=DEFAULT_MAX_TURNS,
                ),
            ):
                messages.append(message)

        await asyncio.wait_for(_run(), timeout=timeout_seconds)

    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start_time
        return RunResult(
            run_number=run_number,
            success=False,
            wall_clock_seconds=elapsed,
            error=f"Timeout after {timeout_seconds}s",
        )
    except Exception as e:
        elapsed = time.monotonic() - start_time
        return RunResult(
            run_number=run_number,
            success=False,
            wall_clock_seconds=elapsed,
            error=str(e),
        )

    elapsed = time.monotonic() - start_time

    # Collect structured result from messages
    result_data = collect_result(messages)

    # Capture output files from workspace
    output_files = capture_workspace_files(workspace_dir)

    # Build token usage if available
    usage = None
    if result_data.get("usage"):
        u = result_data["usage"]
        usage = TokenUsage(
            input_tokens=u.get("input_tokens", 0),
            output_tokens=u.get("output_tokens", 0),
            cache_creation_input_tokens=u.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=u.get("cache_read_input_tokens", 0),
        )

    return RunResult(
        run_number=run_number,
        success=result_data.get("success", False),
        wall_clock_seconds=elapsed,
        duration_ms=result_data.get("duration_ms", 0),
        duration_api_ms=result_data.get("duration_api_ms", 0),
        total_cost_usd=result_data.get("total_cost_usd"),
        num_turns=result_data.get("num_turns", 0),
        session_id=result_data.get("session_id"),
        usage=usage,
        output_files=output_files,
        error=result_data.get("error"),
    )
