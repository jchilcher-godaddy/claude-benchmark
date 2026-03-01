"""Tests for the runner and collector modules.

Uses mocking to test the logic flow without making real API calls.
SDK query() is mocked as an async generator yielding test messages.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from claude_benchmark.engine.collector import collect_result
from claude_benchmark.engine.runner import execute_run
from claude_benchmark.results.schema import RunResult


# ---------------------------------------------------------------------------
# Mock message types matching the actual SDK dataclass structure
# ---------------------------------------------------------------------------


@dataclass
class MockResultMessage:
    """Mirrors claude_code_sdk.ResultMessage for testing."""

    subtype: str
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
    result: str | None = None


@dataclass
class MockAssistantMessage:
    """Mirrors claude_code_sdk.AssistantMessage for testing."""

    content: list[Any]
    model: str
    parent_tool_use_id: str | None = None


@dataclass
class MockTextBlock:
    """Mirrors claude_code_sdk.TextBlock for testing."""

    text: str


# ---------------------------------------------------------------------------
# Helper: build realistic mock messages
# ---------------------------------------------------------------------------


def make_success_result(
    duration_ms: int = 5000,
    duration_api_ms: int = 4200,
    num_turns: int = 3,
    total_cost_usd: float = 0.05,
    session_id: str = "sess-abc123",
    input_tokens: int = 1500,
    output_tokens: int = 800,
    cache_creation: int = 100,
    cache_read: int = 50,
    result_text: str = "Task completed successfully",
) -> MockResultMessage:
    return MockResultMessage(
        subtype="result",
        duration_ms=duration_ms,
        duration_api_ms=duration_api_ms,
        is_error=False,
        num_turns=num_turns,
        session_id=session_id,
        total_cost_usd=total_cost_usd,
        usage={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation,
            "cache_read_input_tokens": cache_read,
        },
        result=result_text,
    )


def make_error_result(
    error_text: str = "Something went wrong",
    duration_ms: int = 2000,
    session_id: str = "sess-err456",
) -> MockResultMessage:
    return MockResultMessage(
        subtype="result",
        duration_ms=duration_ms,
        duration_api_ms=1800,
        is_error=True,
        num_turns=1,
        session_id=session_id,
        total_cost_usd=0.01,
        usage={
            "input_tokens": 500,
            "output_tokens": 200,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
        result=error_text,
    )


def make_assistant_message(text: str = "Working on it...") -> MockAssistantMessage:
    return MockAssistantMessage(
        content=[MockTextBlock(text=text)],
        model="claude-sonnet-4-20250514",
    )


# ---------------------------------------------------------------------------
# Collector tests
# ---------------------------------------------------------------------------


class TestCollectResult:
    def test_collect_success_extracts_usage_cost_duration(self):
        """collect_result with a mock result message extracts usage, cost, duration."""
        messages = [
            make_assistant_message("Hello"),
            make_success_result(
                duration_ms=5000,
                duration_api_ms=4200,
                total_cost_usd=0.05,
                num_turns=3,
                session_id="sess-abc123",
                input_tokens=1500,
                output_tokens=800,
                cache_creation=100,
                cache_read=50,
            ),
        ]

        result = collect_result(messages)

        assert result["success"] is True
        assert result["duration_ms"] == 5000
        assert result["duration_api_ms"] == 4200
        assert result["total_cost_usd"] == 0.05
        assert result["num_turns"] == 3
        assert result["session_id"] == "sess-abc123"
        assert result["error"] is None

        usage = result["usage"]
        assert usage is not None
        assert usage["input_tokens"] == 1500
        assert usage["output_tokens"] == 800
        assert usage["cache_creation_input_tokens"] == 100
        assert usage["cache_read_input_tokens"] == 50

    def test_collect_no_result_message_returns_failure(self):
        """collect_result with no result message returns success=False."""
        messages = [
            make_assistant_message("Some text"),
            make_assistant_message("More text"),
        ]

        result = collect_result(messages)

        assert result["success"] is False
        assert result["error"] == "No result message received"
        assert result["usage"] is None

    def test_collect_empty_messages_returns_failure(self):
        """collect_result with empty list returns success=False."""
        result = collect_result([])

        assert result["success"] is False
        assert result["error"] == "No result message received"

    def test_collect_error_result_returns_error(self):
        """collect_result with error result message returns the error."""
        messages = [
            make_assistant_message("Starting"),
            make_error_result(error_text="Permission denied: cannot access file"),
        ]

        result = collect_result(messages)

        assert result["success"] is False
        assert result["error"] == "Permission denied: cannot access file"
        assert result["duration_ms"] == 2000
        assert result["session_id"] == "sess-err456"

    def test_collect_uses_last_result_message(self):
        """If multiple result messages exist, uses the last one."""
        messages = [
            make_success_result(duration_ms=1000, session_id="first"),
            make_success_result(duration_ms=5000, session_id="second"),
        ]

        result = collect_result(messages)

        assert result["session_id"] == "second"
        assert result["duration_ms"] == 5000

    def test_collect_result_with_no_usage(self):
        """collect_result handles result message with no usage data."""
        msg = MockResultMessage(
            subtype="result",
            duration_ms=3000,
            duration_api_ms=2500,
            is_error=False,
            num_turns=2,
            session_id="sess-no-usage",
            total_cost_usd=None,
            usage=None,
            result="Done",
        )

        result = collect_result([msg])

        assert result["success"] is True
        assert result["usage"] is None
        assert result["total_cost_usd"] is None


# ---------------------------------------------------------------------------
# Runner tests (mock SDK query)
# ---------------------------------------------------------------------------


async def _mock_query_success(**kwargs):
    """Async generator that yields a successful conversation."""
    yield make_assistant_message("Working on it...")
    yield make_success_result()


async def _mock_query_error(**kwargs):
    """Async generator that yields an error result."""
    yield make_assistant_message("Trying...")
    yield make_error_result(error_text="Failed to complete task")


async def _mock_query_exception(**kwargs):
    """Async generator that raises an exception."""
    raise RuntimeError("SDK connection failed")
    yield  # noqa: unreachable -- makes this an async generator


async def _mock_query_slow(**kwargs):
    """Async generator that takes too long (for timeout testing)."""
    await asyncio.sleep(10)  # Will be interrupted by timeout
    yield make_success_result()


class TestExecuteRun:
    @pytest.mark.asyncio
    async def test_success_returns_run_result(self, tmp_path):
        """execute_run with mocked successful SDK response returns RunResult with success=True."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test profile")
        (workspace / "solution.py").write_text("def hello(): return 'world'")

        with patch("claude_benchmark.engine.runner.query", side_effect=_mock_query_success):
            result = await execute_run(
                workspace_dir=workspace,
                prompt="Write hello world",
                model="sonnet",
                run_number=1,
            )

        assert isinstance(result, RunResult)
        assert result.success is True
        assert result.run_number == 1
        assert result.wall_clock_seconds > 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_success_has_token_usage(self, tmp_path):
        """Successful run includes token usage from SDK."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        with patch("claude_benchmark.engine.runner.query", side_effect=_mock_query_success):
            result = await execute_run(
                workspace_dir=workspace,
                prompt="Test prompt",
                model="haiku",
                run_number=1,
            )

        assert result.usage is not None
        assert result.usage.input_tokens == 1500
        assert result.usage.output_tokens == 800
        assert result.usage.cache_creation_input_tokens == 100
        assert result.usage.cache_read_input_tokens == 50

    @pytest.mark.asyncio
    async def test_success_captures_output_files(self, tmp_path):
        """Successful run captures workspace files (excluding CLAUDE.md)."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("profile")
        (workspace / "output.py").write_text("print('hello')")
        (workspace / "result.txt").write_text("done")

        with patch("claude_benchmark.engine.runner.query", side_effect=_mock_query_success):
            result = await execute_run(
                workspace_dir=workspace,
                prompt="Do something",
                model="sonnet",
                run_number=1,
            )

        assert "output.py" in result.output_files
        assert "result.txt" in result.output_files
        assert "CLAUDE.md" not in result.output_files

    @pytest.mark.asyncio
    async def test_success_has_timing_and_cost(self, tmp_path):
        """Successful run includes duration_ms, total_cost_usd, session_id, num_turns."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        with patch("claude_benchmark.engine.runner.query", side_effect=_mock_query_success):
            result = await execute_run(
                workspace_dir=workspace,
                prompt="Test",
                model="sonnet",
                run_number=1,
            )

        assert result.duration_ms == 5000
        assert result.duration_api_ms == 4200
        assert result.total_cost_usd == 0.05
        assert result.num_turns == 3
        assert result.session_id == "sess-abc123"

    @pytest.mark.asyncio
    async def test_sdk_exception_returns_failed_result(self, tmp_path):
        """execute_run with mocked SDK exception returns RunResult with success=False."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        with patch("claude_benchmark.engine.runner.query", side_effect=_mock_query_exception):
            result = await execute_run(
                workspace_dir=workspace,
                prompt="Test",
                model="sonnet",
                run_number=2,
            )

        assert isinstance(result, RunResult)
        assert result.success is False
        assert result.run_number == 2
        assert "SDK connection failed" in result.error
        assert result.wall_clock_seconds > 0

    @pytest.mark.asyncio
    async def test_timeout_returns_failed_result(self, tmp_path):
        """execute_run with mocked timeout returns RunResult with Timeout error."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        with patch("claude_benchmark.engine.runner.query", side_effect=_mock_query_slow):
            result = await execute_run(
                workspace_dir=workspace,
                prompt="Slow task",
                model="sonnet",
                run_number=3,
                timeout_seconds=1,  # 1 second timeout
            )

        assert isinstance(result, RunResult)
        assert result.success is False
        assert "Timeout" in result.error
        assert result.wall_clock_seconds >= 1.0

    @pytest.mark.asyncio
    async def test_passes_correct_model(self, tmp_path):
        """execute_run passes the model parameter to ClaudeCodeOptions."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        captured_options = {}

        async def mock_query(*, prompt, options=None, **kwargs):
            captured_options["model"] = options.model
            yield make_success_result()

        with patch("claude_benchmark.engine.runner.query", side_effect=mock_query):
            await execute_run(
                workspace_dir=workspace,
                prompt="Test",
                model="opus",
                run_number=1,
            )

        assert captured_options["model"] == "opus"

    @pytest.mark.asyncio
    async def test_passes_correct_cwd(self, tmp_path):
        """execute_run passes workspace_dir as cwd to ClaudeCodeOptions."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        captured_options = {}

        async def mock_query(*, prompt, options=None, **kwargs):
            captured_options["cwd"] = options.cwd
            yield make_success_result()

        with patch("claude_benchmark.engine.runner.query", side_effect=mock_query):
            await execute_run(
                workspace_dir=workspace,
                prompt="Test",
                model="sonnet",
                run_number=1,
            )

        assert captured_options["cwd"] == str(workspace)

    @pytest.mark.asyncio
    async def test_sets_bypass_permissions(self, tmp_path):
        """execute_run sets permission_mode to bypassPermissions."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        captured_options = {}

        async def mock_query(*, prompt, options=None, **kwargs):
            captured_options["permission_mode"] = options.permission_mode
            yield make_success_result()

        with patch("claude_benchmark.engine.runner.query", side_effect=mock_query):
            await execute_run(
                workspace_dir=workspace,
                prompt="Test",
                model="sonnet",
                run_number=1,
            )

        assert captured_options["permission_mode"] == "bypassPermissions"

    @pytest.mark.asyncio
    async def test_sets_max_turns(self, tmp_path):
        """execute_run sets max_turns to 50."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        captured_options = {}

        async def mock_query(*, prompt, options=None, **kwargs):
            captured_options["max_turns"] = options.max_turns
            yield make_success_result()

        with patch("claude_benchmark.engine.runner.query", side_effect=mock_query):
            await execute_run(
                workspace_dir=workspace,
                prompt="Test",
                model="sonnet",
                run_number=1,
            )

        assert captured_options["max_turns"] == 50

    @pytest.mark.asyncio
    async def test_wall_clock_is_accurate(self, tmp_path):
        """execute_run measures wall_clock_seconds accurately (within tolerance)."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        async def mock_query_with_delay(*, prompt, options=None, **kwargs):
            await asyncio.sleep(0.2)
            yield make_success_result()

        with patch("claude_benchmark.engine.runner.query", side_effect=mock_query_with_delay):
            result = await execute_run(
                workspace_dir=workspace,
                prompt="Test",
                model="sonnet",
                run_number=1,
            )

        # Should be at least 0.2s (the delay) but not too much more
        assert result.wall_clock_seconds >= 0.15  # allow small tolerance
        assert result.wall_clock_seconds < 1.0  # should not take more than 1s

    @pytest.mark.asyncio
    async def test_error_result_from_sdk(self, tmp_path):
        """execute_run with SDK error result returns RunResult with error details."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "CLAUDE.md").write_text("test")

        with patch("claude_benchmark.engine.runner.query", side_effect=_mock_query_error):
            result = await execute_run(
                workspace_dir=workspace,
                prompt="Failing task",
                model="sonnet",
                run_number=1,
            )

        assert result.success is False
        assert result.error == "Failed to complete task"
        # Still gets timing and usage data from the result message
        assert result.duration_ms == 2000
        assert result.usage is not None
