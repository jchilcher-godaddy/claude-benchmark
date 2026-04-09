"""Tests for AWS credential expiration detection and re-authentication flow."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from claude_benchmark.execution.client import validate_bedrock_credentials
from claude_benchmark.execution.parallel import BenchmarkRun, RunResult, run_benchmark_parallel
from claude_benchmark.execution.worker import is_auth_error, is_transient_error
from claude_benchmark.scoring.errors import is_deterministic_llm_error, LLMJudgeError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    task_name: str = "task-1",
    run_number: int = 1,
    results_dir: Path | None = None,
) -> BenchmarkRun:
    return BenchmarkRun(
        task_name=task_name,
        profile_name="empty",
        model="sonnet",
        run_number=run_number,
        task_dir=Path("/tmp/tasks") / task_name,
        profile_path=Path("/tmp/profiles/empty/CLAUDE.md"),
        results_dir=results_dir or Path("/tmp/results"),
    )


# ---------------------------------------------------------------------------
# is_auth_error — exception type detection
# ---------------------------------------------------------------------------


class TestIsAuthErrorExceptionTypes:
    """is_auth_error correctly identifies auth-related exception types."""

    def test_none_returns_false(self) -> None:
        assert is_auth_error(None) is False

    def test_anthropic_authentication_error(self) -> None:
        exc = anthropic.AuthenticationError(
            message="auth failed",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )
        assert is_auth_error(exc) is True

    def test_anthropic_permission_denied_error(self) -> None:
        exc = anthropic.PermissionDeniedError(
            message="forbidden",
            response=MagicMock(status_code=403, headers={}),
            body=None,
        )
        assert is_auth_error(exc) is True

    def test_botocore_no_credentials_error(self) -> None:
        try:
            from botocore.exceptions import NoCredentialsError

            exc = NoCredentialsError()
            assert is_auth_error(exc) is True
        except ImportError:
            pytest.skip("botocore not installed")

    def test_botocore_sso_error(self) -> None:
        try:
            from botocore.exceptions import SSOError

            exc = SSOError(msg="The SSO session has expired")
            assert is_auth_error(exc) is True
        except ImportError:
            pytest.skip("botocore not installed")

    def test_generic_exception_not_auth(self) -> None:
        assert is_auth_error(ValueError("something else")) is False

    def test_rate_limit_not_auth(self) -> None:
        exc = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        assert is_auth_error(exc) is False


# ---------------------------------------------------------------------------
# is_auth_error — string pattern detection
# ---------------------------------------------------------------------------


class TestIsAuthErrorStringPatterns:
    """is_auth_error correctly matches common AWS auth error message patterns."""

    @pytest.mark.parametrize(
        "msg",
        [
            "The SSO session associated with this profile has expired",
            "The SSO token associated with this profile has expired",
            "Unable to locate credentials",
            "ExpiredTokenException: The security token included in the request is expired",
            "InvalidClientTokenId: Bad token",
            "Could not resolve credentials",
            "No credentials found",
            "UnauthorizedAccess: You are not authorized",
        ],
    )
    def test_auth_patterns_detected(self, msg: str) -> None:
        assert is_auth_error(msg) is True

    @pytest.mark.parametrize(
        "msg",
        [
            "rate limit exceeded",
            "too many requests",
            "overloaded",
            "connection timeout",
            "internal server error",
        ],
    )
    def test_non_auth_patterns_rejected(self, msg: str) -> None:
        assert is_auth_error(msg) is False

    def test_empty_string_returns_false(self) -> None:
        assert is_auth_error("") is False


# ---------------------------------------------------------------------------
# is_auth_error vs is_transient_error — no overlap
# ---------------------------------------------------------------------------


class TestAuthTransientNoOverlap:
    """Auth errors and transient errors should not overlap."""

    def test_auth_string_not_transient(self) -> None:
        msg = "The SSO session associated with this profile has expired"
        assert is_auth_error(msg) is True
        assert is_transient_error(msg) is False

    def test_transient_string_not_auth(self) -> None:
        msg = "rate limit exceeded"
        assert is_transient_error(msg) is True
        assert is_auth_error(msg) is False


# ---------------------------------------------------------------------------
# validate_bedrock_credentials
# ---------------------------------------------------------------------------


class TestValidateBedrockCredentials:
    """validate_bedrock_credentials pre-flight check."""

    def test_valid_credentials_returns_none(self) -> None:
        mock_frozen = MagicMock()
        mock_frozen.access_key = "AKIAIOSFODNN7EXAMPLE"
        mock_creds = MagicMock()
        mock_creds.get_frozen_credentials.return_value = mock_frozen

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = mock_creds

        with patch("boto3.Session", return_value=mock_session):
            assert validate_bedrock_credentials() is None

    def test_no_credentials_returns_error(self) -> None:
        mock_session = MagicMock()
        mock_session.get_credentials.return_value = None

        with patch("boto3.Session", return_value=mock_session):
            result = validate_bedrock_credentials()
            assert result is not None
            assert "No AWS credentials found" in result

    def test_expired_raises_returns_error(self) -> None:
        try:
            from botocore.exceptions import SSOError

            mock_session = MagicMock()
            mock_session.get_credentials.side_effect = SSOError(
                msg="The SSO session has expired"
            )

            with patch("boto3.Session", return_value=mock_session):
                result = validate_bedrock_credentials()
                assert result is not None
                assert "expired" in result.lower()
        except ImportError:
            pytest.skip("botocore not installed")

    def test_incomplete_credentials_returns_error(self) -> None:
        mock_frozen = MagicMock()
        mock_frozen.access_key = ""
        mock_creds = MagicMock()
        mock_creds.get_frozen_credentials.return_value = mock_frozen

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = mock_creds

        with patch("boto3.Session", return_value=mock_session):
            result = validate_bedrock_credentials()
            assert result is not None
            assert "incomplete" in result.lower()


# ---------------------------------------------------------------------------
# Scoring errors — auth errors treated as deterministic
# ---------------------------------------------------------------------------


class TestScoringAuthDeterministic:
    """Auth errors should be treated as deterministic (no retry) in scoring."""

    def test_auth_prefix_is_deterministic(self) -> None:
        exc = LLMJudgeError("aws_credentials_expired: SSO token expired")
        assert is_deterministic_llm_error(exc) is True

    def test_normal_error_not_deterministic(self) -> None:
        exc = LLMJudgeError("API timeout after 120s")
        assert is_deterministic_llm_error(exc) is False


# ---------------------------------------------------------------------------
# Orchestrator auth handler integration
# ---------------------------------------------------------------------------


class TestOrchestratorAuthHandler:
    """run_benchmark_parallel invokes on_auth_error and handles the result."""

    async def test_auth_handler_called_and_retry_on_success(self, tmp_path: Path) -> None:
        """When auth handler returns True, the failed run is retried."""
        call_count = 0

        async def fake_execute(run: BenchmarkRun) -> RunResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return RunResult(
                    run=run,
                    status="failure",
                    error="aws_credentials_expired: SSO token expired",
                    output_dir=tmp_path,
                )
            return RunResult(
                run=run,
                status="success",
                output_dir=tmp_path,
            )

        handler = MagicMock(return_value=True)
        runs = [_make_run(results_dir=tmp_path)]

        with (
            patch("claude_benchmark.execution.worker.execute_single_run", side_effect=fake_execute),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            results = await run_benchmark_parallel(
                runs, concurrency=1, on_auth_error=handler,
            )

        handler.assert_called_once()
        assert call_count == 2  # original + retry
        assert len(results) == 1
        assert results[0].status == "success"

    async def test_auth_handler_failure_drains_queue(self, tmp_path: Path) -> None:
        """When auth handler returns False, remaining runs are drained."""

        async def fake_execute(run: BenchmarkRun) -> RunResult:
            return RunResult(
                run=run,
                status="failure",
                error="aws_credentials_expired: SSO token expired",
                output_dir=tmp_path,
            )

        handler = MagicMock(return_value=False)
        runs = [_make_run(run_number=i, results_dir=tmp_path) for i in range(1, 4)]

        with (
            patch("claude_benchmark.execution.worker.execute_single_run", side_effect=fake_execute),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            results = await run_benchmark_parallel(
                runs, concurrency=1, on_auth_error=handler,
            )

        # Handler called once (first failure), remaining 2 runs drained
        handler.assert_called_once()
        assert len(results) == 3
        assert all(r.status == "failure" for r in results)
        assert all("aws_credentials_expired" in r.error for r in results)

    async def test_no_handler_drains_queue_on_auth_error(self, tmp_path: Path) -> None:
        """Without auth handler, auth errors drain the queue immediately."""

        async def fake_execute(run: BenchmarkRun) -> RunResult:
            return RunResult(
                run=run,
                status="failure",
                error="aws_credentials_expired: SSO token expired",
                output_dir=tmp_path,
            )

        runs = [_make_run(run_number=i, results_dir=tmp_path) for i in range(1, 4)]

        with (
            patch("claude_benchmark.execution.worker.execute_single_run", side_effect=fake_execute),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            results = await run_benchmark_parallel(
                runs, concurrency=1, on_auth_error=None,
            )

        assert len(results) == 3
        assert all(r.status == "failure" for r in results)
