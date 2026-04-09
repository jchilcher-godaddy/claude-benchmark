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
    use_gocode: bool = False


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
