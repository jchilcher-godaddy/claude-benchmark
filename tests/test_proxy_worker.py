"""Tests for proxy execution path in worker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_benchmark.execution.parallel import BenchmarkRun
from claude_benchmark.execution.worker import _execute_via_proxy_sync


def _make_run(model: str = "sonnet", temperature: float | None = None) -> BenchmarkRun:
    results_dir = Path(tempfile.mkdtemp())
    return BenchmarkRun(
        task_name="test-task",
        profile_name="empty",
        model=model,
        run_number=1,
        task_dir=Path("/tmp/tasks/test-task"),
        profile_path=Path("/tmp/profiles/empty.md"),
        results_dir=results_dir,
        use_direct_api=True,
        temperature=temperature,
    )


def _mock_completion(content: str = "Done", tool_calls=None, finish_reason="stop"):
    """Create a mock OpenAI chat completion response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    message.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": None,
    }

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    # Explicit defaults so the cache-aware reader (which uses getattr with a
    # default of None) doesn't pick up a stray MagicMock as a cache count.
    usage.cache_creation_input_tokens = 0
    usage.cache_read_input_tokens = 0
    usage.model_extra = None
    usage.prompt_tokens_details = None

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _mock_tool_call(path: str, content: str):
    """Create a mock tool call for write_file."""
    tc = MagicMock()
    tc.id = "call_123"
    tc.function.name = "write_file"
    tc.function.arguments = json.dumps({"path": path, "content": content})
    return tc


class TestExecuteViaProxy:
    @patch("claude_benchmark.execution.worker.create_proxy_client")
    @patch("claude_benchmark.execution.proxy_auth.get_token_manager")
    def test_single_turn_completion(self, mock_get_mgr, mock_create_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_completion("Hello!")
        mock_create_client.return_value = mock_client

        run = _make_run()
        work_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())

        result = _execute_via_proxy_sync(
            run, work_dir, output_dir, "Write hello", ""
        )

        assert result.status == "success"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.cache_creation_input_tokens == 0
        assert result.cache_read_input_tokens == 0
        assert result.total_tokens == 150

    @patch("claude_benchmark.execution.worker.create_proxy_client")
    @patch("claude_benchmark.execution.proxy_auth.get_token_manager")
    def test_cache_tokens_captured_when_present(self, mock_get_mgr, mock_create_client):
        """LiteLLM/OpenAI-compat proxy passes through cache tokens via usage."""
        completion = _mock_completion("Hello!")
        completion.usage.cache_creation_input_tokens = 1000
        completion.usage.cache_read_input_tokens = 5000

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = completion
        mock_create_client.return_value = mock_client

        run = _make_run()
        work_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())

        result = _execute_via_proxy_sync(
            run, work_dir, output_dir, "Write hello", ""
        )

        assert result.status == "success"
        assert result.cache_creation_input_tokens == 1000
        assert result.cache_read_input_tokens == 5000
        # total_tokens now includes cache categories
        assert result.total_tokens == 100 + 50 + 1000 + 5000
        # Sonnet pricing: 100 fresh in × $3/M + 50 out × $15/M
        # + 1000 cw × $3.75/M + 5000 cr × $0.30/M
        expected_cost = (
            (100 / 1_000_000) * 3.0
            + (50 / 1_000_000) * 15.0
            + (1000 / 1_000_000) * 3.75
            + (5000 / 1_000_000) * 0.30
        )
        assert abs(result.cost - expected_cost) < 1e-9

    @patch("claude_benchmark.execution.worker.create_proxy_client")
    @patch("claude_benchmark.execution.proxy_auth.get_token_manager")
    def test_multi_turn_tool_calling(self, mock_get_mgr, mock_create_client):
        tool_call = _mock_tool_call("solution.py", "print('hello')")

        tool_response = _mock_completion(tool_calls=[tool_call], finish_reason="tool_calls")
        tool_response.choices[0].message.model_dump.return_value = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": tool_call.function.arguments},
                }
            ],
        }
        final_response = _mock_completion("Done writing file.")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [tool_response, final_response]
        mock_create_client.return_value = mock_client

        run = _make_run()
        work_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())

        result = _execute_via_proxy_sync(
            run, work_dir, output_dir, "Write a python file", ""
        )

        assert result.status == "success"
        assert (output_dir / "solution.py").exists()
        assert (output_dir / "solution.py").read_text() == "print('hello')"
        assert result.input_tokens == 200
        assert result.output_tokens == 100

    @patch("claude_benchmark.execution.worker.create_proxy_client")
    @patch("claude_benchmark.execution.proxy_auth.get_token_manager")
    def test_rate_limit_retry(self, mock_get_mgr, mock_create_client):
        import openai

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        mock_resp.json.return_value = {"error": {"message": "rate limited"}}

        rate_err = openai.RateLimitError(
            message="rate limited",
            response=mock_resp,
            body={"error": {"message": "rate limited"}},
        )
        mock_client.chat.completions.create.side_effect = [
            rate_err,
            _mock_completion("Success after retry"),
        ]
        mock_create_client.return_value = mock_client

        run = _make_run()
        work_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())

        with patch("claude_benchmark.execution.worker.time.sleep"):
            result = _execute_via_proxy_sync(
                run, work_dir, output_dir, "test prompt", ""
            )

        assert result.status == "success"
        assert mock_client.chat.completions.create.call_count == 2

    @patch("claude_benchmark.execution.worker.create_proxy_client")
    @patch("claude_benchmark.execution.proxy_auth.get_token_manager")
    def test_auth_error_triggers_refresh(self, mock_get_mgr, mock_create_client):
        import openai

        mock_mgr = MagicMock()
        mock_get_mgr.return_value = mock_mgr

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.headers = {}
        mock_resp.json.return_value = {"error": {"message": "invalid token"}}

        auth_err = openai.AuthenticationError(
            message="invalid token",
            response=mock_resp,
            body={"error": {"message": "invalid token"}},
        )
        mock_client.chat.completions.create.side_effect = [
            auth_err,
            _mock_completion("Success after refresh"),
        ]

        fresh_client = MagicMock()
        fresh_client.chat.completions.create.return_value = _mock_completion("Refreshed!")
        mock_create_client.side_effect = [mock_client, fresh_client]

        run = _make_run()
        work_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())

        result = _execute_via_proxy_sync(
            run, work_dir, output_dir, "test prompt", ""
        )

        assert result.status == "success"
        mock_mgr.invalidate.assert_called_once()

    @patch("claude_benchmark.execution.worker.create_proxy_client")
    @patch("claude_benchmark.execution.proxy_auth.get_token_manager")
    def test_system_prompt_passed(self, mock_get_mgr, mock_create_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_completion("Done")
        mock_create_client.return_value = mock_client

        run = _make_run()
        work_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())

        _execute_via_proxy_sync(
            run, work_dir, output_dir, "task", "You are a code reviewer."
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "You are a code reviewer."}
        assert messages[1] == {"role": "user", "content": "task"}

    @patch("claude_benchmark.execution.worker.create_proxy_client")
    @patch("claude_benchmark.execution.proxy_auth.get_token_manager")
    def test_temperature_passed(self, mock_get_mgr, mock_create_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_completion("Done")
        mock_create_client.return_value = mock_client

        run = _make_run(temperature=0.7)
        work_dir = Path(tempfile.mkdtemp())
        output_dir = Path(tempfile.mkdtemp())

        _execute_via_proxy_sync(
            run, work_dir, output_dir, "task", ""
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7
