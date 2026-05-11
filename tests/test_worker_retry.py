"""Tests for rate-limit retry logic in worker._execute_via_api_sync."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class FakeBenchmarkRun:
    """Minimal BenchmarkRun-like object for testing."""

    model: str = "sonnet"
    temperature: float = 0.5
    result_key: str = "sonnet/empty/task-1/run-1"
    task_dir: Path = field(default_factory=lambda: Path("/tmp/fake-task"))
    results_dir: Path = field(default_factory=lambda: Path("/tmp/fake-results"))
    profile_path: Path | None = None
    system_prompt_extra: str | None = None
    prompt_prefix: str | None = None
    use_direct_api: bool = False
    follow_up_prompts: list[str] | None = None


@dataclass
class FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 20


@dataclass
class FakeTextBlock:
    type: str = "text"
    text: str = "Hello"


@dataclass
class FakeResponse:
    content: list[Any] = field(default_factory=lambda: [FakeTextBlock()])
    usage: FakeUsage = field(default_factory=FakeUsage)
    stop_reason: str = "end_turn"


class TestRateLimitRetry:
    """Verify retry logic around client.messages.create for 429 errors."""

    def test_succeeds_after_retries(self, tmp_path: Path) -> None:
        """API call succeeds on 3rd attempt after two 429 errors."""
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(results_dir=tmp_path)
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        # Fail twice with RateLimitError, then succeed
        rate_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        mock_client.messages.create.side_effect = [
            rate_err,
            rate_err,
            FakeResponse(),
        ]

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
            patch("claude_benchmark.execution.worker.time.sleep") as mock_sleep,
            patch("claude_benchmark.execution.worker._RATE_LIMIT_BASE_DELAY", 0.01),
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "success"
        assert mock_client.messages.create.call_count == 3
        assert mock_sleep.call_count == 2

    def test_fails_after_max_retries(self, tmp_path: Path) -> None:
        """API call fails permanently after exhausting all retries."""
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(results_dir=tmp_path)
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        rate_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        # All attempts fail
        mock_client.messages.create.side_effect = rate_err

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
            patch("claude_benchmark.execution.worker.time.sleep"),
            patch("claude_benchmark.execution.worker._RATE_LIMIT_BASE_DELAY", 0.01),
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError
            mock_anthropic_mod.AuthenticationError = anthropic.AuthenticationError
            mock_anthropic_mod.PermissionDeniedError = anthropic.PermissionDeniedError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "failure"
        assert "rate limited" in result.error

    def test_non_rate_limit_error_not_retried(self, tmp_path: Path) -> None:
        """Non-429 errors are not retried."""
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(results_dir=tmp_path)
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = ValueError("bad input")

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
            patch("claude_benchmark.execution.worker.time.sleep") as mock_sleep,
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError
            mock_anthropic_mod.AuthenticationError = anthropic.AuthenticationError
            mock_anthropic_mod.PermissionDeniedError = anthropic.PermissionDeniedError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "failure"
        assert "bad input" in result.error
        assert mock_client.messages.create.call_count == 1
        assert mock_sleep.call_count == 0


class TestIsTransientError:
    """Verify is_transient_error classifies error messages correctly."""

    def test_too_many_tokens_is_transient(self) -> None:
        from claude_benchmark.execution.worker import is_transient_error

        assert is_transient_error("Too many tokens, please wait before trying again") is True

    def test_rate_limit_is_transient(self) -> None:
        from claude_benchmark.execution.worker import is_transient_error

        assert is_transient_error("rate limit exceeded") is True

    def test_overloaded_is_transient(self) -> None:
        from claude_benchmark.execution.worker import is_transient_error

        assert is_transient_error("service overloaded") is True

    def test_permanent_error_not_transient(self) -> None:
        from claude_benchmark.execution.worker import is_transient_error

        assert is_transient_error("bad input") is False

    def test_none_not_transient(self) -> None:
        from claude_benchmark.execution.worker import is_transient_error

        assert is_transient_error(None) is False


class TestInternalServerErrorRetry:
    """Verify InternalServerError (529 overloaded) is retried like RateLimitError."""

    def test_internal_server_error_retried(self, tmp_path: Path) -> None:
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(results_dir=tmp_path)
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        overloaded_err = anthropic.InternalServerError(
            message="overloaded",
            response=MagicMock(status_code=529, headers={}),
            body=None,
        )
        mock_client.messages.create.side_effect = [
            overloaded_err,
            FakeResponse(),
        ]

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
            patch("claude_benchmark.execution.worker.time.sleep") as mock_sleep,
            patch("claude_benchmark.execution.worker._RATE_LIMIT_BASE_DELAY", 0.01),
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "success"
        assert mock_client.messages.create.call_count == 2
        assert mock_sleep.call_count == 1


class TestMultiTurnConversation:
    """Verify multi-turn follow_up_prompts support in _execute_via_api_sync."""

    def test_single_turn_no_follow_ups(self, tmp_path: Path) -> None:
        """Without follow_up_prompts, runs a single turn and returns turn_count=1."""
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(results_dir=tmp_path)
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        mock_client.messages.create.return_value = FakeResponse()

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "success"
        assert result.turn_count == 1
        assert mock_client.messages.create.call_count == 1

    def test_two_turn_with_one_follow_up(self, tmp_path: Path) -> None:
        """One follow_up_prompt results in two API calls and turn_count=2."""
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(
            results_dir=tmp_path,
            follow_up_prompts=["Review your solution and fix any issues."],
        )
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        mock_client.messages.create.return_value = FakeResponse()

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "success"
        assert result.turn_count == 2
        assert mock_client.messages.create.call_count == 2
        assert result.input_tokens == 20  # 10 + 10
        assert result.output_tokens == 40  # 20 + 20

    def test_three_turn_with_two_follow_ups(self, tmp_path: Path) -> None:
        """Two follow_up_prompts results in three API calls and turn_count=3."""
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(
            results_dir=tmp_path,
            follow_up_prompts=[
                "Review your solution.",
                "Now add edge case handling.",
            ],
        )
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        mock_client.messages.create.return_value = FakeResponse()

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "success"
        assert result.turn_count == 3
        assert mock_client.messages.create.call_count == 3
        assert result.input_tokens == 30
        assert result.output_tokens == 60

    def test_follow_up_messages_include_conversation_history(self, tmp_path: Path) -> None:
        """Follow-up turns pass the full conversation history to the API."""
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(
            results_dir=tmp_path,
            follow_up_prompts=["Fix the bugs."],
        )
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        mock_client.messages.create.return_value = FakeResponse()

        captured_messages = []

        def capture_create(**kwargs):
            captured_messages.append([m.copy() for m in kwargs["messages"]])
            return FakeResponse()

        mock_client.messages.create.side_effect = capture_create

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "success"
        assert len(captured_messages) == 2

        # First call: just the initial user message
        assert len(captured_messages[0]) == 1
        assert captured_messages[0][0]["role"] == "user"
        assert captured_messages[0][0]["content"] == "test prompt"

        # Second call: initial user + assistant response + follow-up user
        assert len(captured_messages[1]) == 3
        assert captured_messages[1][0]["role"] == "user"
        assert captured_messages[1][1]["role"] == "assistant"
        assert captured_messages[1][2]["role"] == "user"
        assert captured_messages[1][2]["content"] == "Fix the bugs."

    def test_follow_up_error_on_second_turn(self, tmp_path: Path) -> None:
        """Error during a follow-up turn is caught and returns failure."""
        import anthropic

        from claude_benchmark.execution.worker import _execute_via_api_sync

        run = FakeBenchmarkRun(
            results_dir=tmp_path,
            follow_up_prompts=["Review your solution."],
        )
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            FakeResponse(),
            ValueError("API exploded on follow-up"),
        ]

        with (
            patch("claude_benchmark.execution.worker.create_client", return_value=mock_client),
            patch("claude_benchmark.execution.worker.anthropic") as mock_anthropic_mod,
        ):
            mock_anthropic_mod.RateLimitError = anthropic.RateLimitError
            mock_anthropic_mod.InternalServerError = anthropic.InternalServerError
            mock_anthropic_mod.AuthenticationError = anthropic.AuthenticationError
            mock_anthropic_mod.PermissionDeniedError = anthropic.PermissionDeniedError

            result = _execute_via_api_sync(
                run, work_dir, output_dir, "test prompt", "system"
            )

        assert result.status == "failure"
        assert "API exploded on follow-up" in result.error
