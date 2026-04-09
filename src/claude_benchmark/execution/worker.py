"""Worker function for executing single benchmark runs.

Pulls runs from the queue, invokes Claude Code CLI as an async subprocess,
writes results atomically for resume safety.
"""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import anthropic
import anyio

from claude_benchmark.execution.client import create_client, resolve_model_id
from claude_benchmark.execution.cost import MODEL_PRICING
from claude_benchmark.execution.parallel import BenchmarkRun, RunResult

logger = logging.getLogger(__name__)

# Use npx to invoke Claude Code CLI reliably.  Resolving a bare ``claude``
# binary via ``shutil.which`` is fragile: the binary lives inside an npx
# cache directory and the PATH seen by a subprocess may differ from an
# interactive shell.  ``npx`` is always available via nvm and handles
# package resolution itself.
_NPX_CLAUDE_PACKAGE = "@anthropic-ai/claude-code@latest"


_WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": "Write content to a file in the current directory",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path (relative)"},
            "content": {"type": "string", "description": "File content"},
        },
        "required": ["path", "content"],
    },
}

_MAX_TOOL_ITERATIONS = 10
_RATE_LIMIT_MAX_RETRIES = 5
_RATE_LIMIT_BASE_DELAY = 2.0  # seconds

_TRANSIENT_PATTERNS = [
    "too many tokens",
    "rate limit",
    "rate_limit",
    "overloaded",
    "529",
    "too many requests",
    "capacity",
    "please wait",
]

_AUTH_ERROR_PATTERNS = [
    "expired",
    "expiredtoken",
    "the sso session associated with this profile has expired",
    "the sso token associated with this profile has expired",
    "unable to locate credentials",
    "invalidclienttokenid",
    "unauthorizedaccess",
    "could not resolve credentials",
    "security token included in the request is expired",
    "no credentials",
    "not authorized to perform",
]


def is_transient_error(error_msg: str | None) -> bool:
    """Check if an error message indicates a transient/retryable failure."""
    if not error_msg:
        return False
    lower = error_msg.lower()
    return any(pat in lower for pat in _TRANSIENT_PATTERNS)


def is_auth_error(exc_or_msg: Exception | str | None) -> bool:
    """Check if an error indicates expired or missing AWS credentials.

    Inspects exception types first (most reliable), then falls back
    to string pattern matching on the error message.

    Args:
        exc_or_msg: An exception instance, error message string, or None.

    Returns:
        True if the error is an authentication/credential failure.
    """
    if exc_or_msg is None:
        return False

    # Check exception type first (most reliable)
    if isinstance(exc_or_msg, Exception):
        if isinstance(exc_or_msg, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
            return True
        try:
            from botocore.exceptions import (
                CredentialRetrievalError,
                NoCredentialsError,
                SSOError,
                TokenRetrievalError,
            )

            if isinstance(
                exc_or_msg,
                (SSOError, NoCredentialsError, TokenRetrievalError, CredentialRetrievalError),
            ):
                return True
        except ImportError:
            pass
        msg = str(exc_or_msg)
    else:
        msg = exc_or_msg

    lower = msg.lower()
    return any(pat in lower for pat in _AUTH_ERROR_PATTERNS)


def _clean_env() -> dict[str, str]:
    """Build a subprocess environment with ``CLAUDECODE`` removed.

    The Claude Code CLI refuses to start when it detects the ``CLAUDECODE``
    variable (set by a parent Claude Code session).  Stripping it allows the
    benchmark to invoke the CLI as a nested subprocess.
    """
    return {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}


def _execute_via_api_sync(
    run: BenchmarkRun,
    work_dir: Path,
    output_dir: Path,
    task_prompt: str,
    system_prompt: str,
) -> RunResult:
    """Execute a run via the Anthropic API with temperature support.

    Uses the Messages API directly so we can pass temperature.
    Provides a write_file tool so the model can write code to disk.
    """
    start_time = time.monotonic()

    model_id = resolve_model_id(run.model, use_gocode=run.use_gocode)
    client = create_client(use_gocode=run.use_gocode)

    messages = [{"role": "user", "content": task_prompt}]
    total_input = 0
    total_output = 0

    try:
        for _ in range(_MAX_TOOL_ITERATIONS):
            # Retry loop for rate-limit (429) errors with exponential backoff
            last_exc: Exception | None = None
            for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
                try:
                    create_kwargs: dict = dict(
                        model=model_id,
                        max_tokens=4096,
                        system=system_prompt,
                        tools=[_WRITE_FILE_TOOL],
                        messages=messages,
                    )
                    if run.temperature is not None:
                        create_kwargs["temperature"] = run.temperature
                    response = client.messages.create(**create_kwargs)
                    break  # success
                except (anthropic.RateLimitError, anthropic.InternalServerError) as rate_exc:
                    last_exc = rate_exc
                    if attempt >= _RATE_LIMIT_MAX_RETRIES:
                        raise
                    delay = _RATE_LIMIT_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Rate limited on %s (attempt %d/%d), retrying in %.1fs",
                        run.result_key, attempt + 1, _RATE_LIMIT_MAX_RETRIES, delay,
                    )
                    time.sleep(delay)

            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            # Process tool use blocks
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses or response.stop_reason == "end_turn":
                break

            # Execute each tool call
            tool_results = []
            for tool_use in tool_uses:
                if tool_use.name == "write_file":
                    path_val = tool_use.input.get("path")
                    content_val = tool_use.input.get("content")
                    if not path_val or content_val is None:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": "Error: write_file requires 'path' and 'content' parameters",
                            "is_error": True,
                        })
                        continue
                    file_path = work_dir / path_val
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content_val, encoding="utf-8")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"Wrote {path_val}",
                    })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"Unknown tool: {tool_use.name}",
                        "is_error": True,
                    })

            # Append assistant response and tool results for next turn
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        # Copy files from work_dir to output_dir
        for item in work_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, output_dir / item.name)
            elif item.is_dir() and not item.name.startswith("."):
                shutil.copytree(item, output_dir / item.name, dirs_exist_ok=True)

        duration = time.monotonic() - start_time
        total_tokens = total_input + total_output

        pricing = MODEL_PRICING.get(run.model, MODEL_PRICING["sonnet"])
        cost = (
            (total_input / 1_000_000) * pricing["input"]
            + (total_output / 1_000_000) * pricing["output"]
        )

        return RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_tokens,
            cost=cost,
            duration_seconds=duration,
        )

    except Exception as exc:
        duration = time.monotonic() - start_time
        error_msg = str(exc)
        if is_auth_error(exc):
            error_msg = f"aws_credentials_expired: {exc}"
        return RunResult(
            run=run,
            status="failure",
            error=error_msg,
            output_dir=output_dir,
            duration_seconds=duration,
        )


async def execute_single_run(run: BenchmarkRun) -> RunResult:
    """Execute a single benchmark run by invoking Claude Code CLI.

    Creates an isolated output directory, runs the Claude Code CLI via
    ``npx`` with the task prompt passed as a positional argument (``-p``
    mode), and captures output/metrics.

    Uses ``anyio.open_process()`` as an async context manager so the
    process gets terminated on cancellation (per RESEARCH.md Pitfall 4).

    Args:
        run: The BenchmarkRun to execute.

    Returns:
        RunResult with status, metrics, and optional error.
    """
    start_time = time.monotonic()

    # Create output directory for persisting results
    output_dir = run.results_dir / run.result_key.replace(".json", "")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create an isolated temp directory OUTSIDE the repo for CLI execution.
    # This prevents Claude Code from discovering the git root and writing
    # files at the repo root (which leaks solutions across tasks).
    work_dir = Path(tempfile.mkdtemp(prefix="claude_benchmark_"))

    # Copy task starter files into the temp work directory so the CLI
    # can find them (e.g. starter.py for refactor/bug-fix tasks).
    task_def = None
    claudemd_rules_content = ""
    try:
        from claude_benchmark.tasks.loader import load_task

        task_def = load_task(run.task_dir)

        if task_def.starter_code:
            starter_src = run.task_dir / task_def.starter_code
            if starter_src.exists():
                shutil.copy2(starter_src, work_dir / starter_src.name)

        if task_def.starter_files:
            for starter_file in task_def.starter_files:
                src = run.task_dir / starter_file
                if src.is_file():
                    shutil.copy2(src, work_dir / starter_file)
                elif src.is_dir():
                    shutil.copytree(src, work_dir / starter_file, dirs_exist_ok=True)

        if task_def.claudemd_rules:
            rules_path = run.task_dir / task_def.claudemd_rules
            if rules_path.exists():
                claudemd_rules_content = rules_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to load starter files for %s: %s", run.result_key, exc)

    # Read task prompt: try prompt.md first, then .md files, then task.toml
    task_prompt_path = run.task_dir / "prompt.md"
    if task_prompt_path.exists():
        task_prompt = task_prompt_path.read_text()
    else:
        md_files = list(run.task_dir.glob("*.md"))
        if md_files:
            task_prompt = md_files[0].read_text()
        else:
            # Load prompt from task.toml
            task_toml_path = run.task_dir / "task.toml"
            if task_toml_path.exists():
                import tomllib

                with open(task_toml_path, "rb") as f:
                    task_data = tomllib.load(f)
                task_prompt = task_data.get("prompt", "")
                if not task_prompt:
                    return RunResult.failure(run, error=f"No prompt in task.toml at {run.task_dir}")
            else:
                return RunResult.failure(run, error=f"No prompt file found in {run.task_dir}")

    # Append prompt_rules from task definition (used by instruction tasks)
    if task_def and task_def.prompt_rules:
        rules_text = "\n".join(f"- {rule}" for rule in task_def.prompt_rules)
        task_prompt = task_prompt.rstrip() + "\n\nRules:\n" + rules_text

    # Append expected_files instruction so Claude knows to write to disk
    if task_def and task_def.expected_files:
        files_list = ", ".join(f"`{f}`" for f in task_def.expected_files)
        task_prompt = task_prompt.rstrip() + f"\n\nWrite your solution to {files_list}."

    # Build Claude Code CLI command via npx (avoids PATH resolution issues)
    cmd = [
        "npx",
        _NPX_CLAUDE_PACKAGE,
        "--print",
        "--dangerously-skip-permissions",
        "--model",
        run.model,
        "--output-format",
        "json",
    ]

    # Inject profile content and claudemd rules as appended system prompts
    if run.profile_path and run.profile_path.exists():
        profile_content = run.profile_path.read_text(encoding="utf-8")
        if profile_content.strip():
            cmd.extend(["--append-system-prompt", profile_content])

    if claudemd_rules_content.strip():
        cmd.extend(["--append-system-prompt", claudemd_rules_content])

    # Inject experiment variant system prompt extra (Phase 1 prompt variants)
    if run.system_prompt_extra:
        cmd.extend(["--append-system-prompt", run.system_prompt_extra])

    # Use Anthropic API directly for experiment runs (variant_label set),
    # temperature overrides, or when prompt_prefix is present.
    # Reasons: (1) CLI arg parser chokes on large/special-char prefixes
    # (e.g. context-padding starting with "---") by misinterpreting them as
    # option flags.  (2) All variants within an experiment must use the same
    # execution path to avoid confounding treatment effects with path differences.
    if run.temperature is not None or run.prompt_prefix or run.variant_label or run.use_gocode:
        system_parts = []
        if run.profile_path and run.profile_path.exists():
            profile_content = run.profile_path.read_text(encoding="utf-8").strip()
            if profile_content:
                system_parts.append(profile_content)
        if claudemd_rules_content.strip():
            system_parts.append(claudemd_rules_content.strip())
        if run.system_prompt_extra:
            system_parts.append(run.system_prompt_extra.strip())
        system_prompt = "\n\n".join(system_parts) if system_parts else ""
        api_task_prompt = task_prompt
        if run.prompt_prefix:
            api_task_prompt = run.prompt_prefix + api_task_prompt
        try:
            return await anyio.to_thread.run_sync(
                lambda: _execute_via_api_sync(run, work_dir, output_dir, api_task_prompt, system_prompt)
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # Prepend experiment variant prompt prefix to task prompt
    if run.prompt_prefix:
        task_prompt = run.prompt_prefix + task_prompt

    # Task prompt is the positional argument (last)
    cmd.append(task_prompt)

    try:
        # Use open_process() for proper cancellation handling.
        # Pass a cleaned env (CLAUDECODE stripped) so the CLI can
        # run even when the benchmark is launched from inside a
        # Claude Code session.
        # Run in work_dir (temp dir outside repo) to prevent file leaks.
        async with await anyio.open_process(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(work_dir),
            env=_clean_env(),
        ) as process:
            # Read stdout and stderr concurrently
            stdout_chunks: list[bytes] = []
            stderr_chunks: list[bytes] = []

            assert process.stdout is not None
            assert process.stderr is not None

            async with anyio.create_task_group() as tg:

                async def read_stdout() -> None:
                    async for chunk in process.stdout:
                        stdout_chunks.append(chunk)

                async def read_stderr() -> None:
                    async for chunk in process.stderr:
                        stderr_chunks.append(chunk)

                tg.start_soon(read_stdout)
                tg.start_soon(read_stderr)

            await process.wait()

            # Copy generated files from temp work_dir back to output_dir
            # so scoring and result collection can find them.
            for item in work_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, output_dir / item.name)
                elif item.is_dir() and not item.name.startswith("."):
                    shutil.copytree(item, output_dir / item.name, dirs_exist_ok=True)

            stdout_text = b"".join(stdout_chunks).decode(errors="replace")
            stderr_text = b"".join(stderr_chunks).decode(errors="replace")

            duration = time.monotonic() - start_time

            if process.returncode != 0:
                error_msg = stderr_text.strip() or f"Exit code {process.returncode}"
                return RunResult(
                    run=run,
                    status="failure",
                    error=error_msg,
                    output_dir=output_dir,
                    duration_seconds=duration,
                )

            # Parse token usage from JSON output if available
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            cost = 0.0

            try:
                output_data = json.loads(stdout_text)
                if isinstance(output_data, dict):
                    usage = output_data.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    total_tokens = input_tokens + output_tokens
            except (json.JSONDecodeError, TypeError):
                pass  # Non-JSON output, metrics unavailable

            # Compute cost from token usage
            if input_tokens or output_tokens:
                pricing = MODEL_PRICING.get(run.model, MODEL_PRICING["sonnet"])
                cost = (
                    (input_tokens / 1_000_000) * pricing["input"]
                    + (output_tokens / 1_000_000) * pricing["output"]
                )

            return RunResult(
                run=run,
                status="success",
                output_dir=output_dir,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                duration_seconds=duration,
            )

    except Exception as exc:
        duration = time.monotonic() - start_time
        error_msg = str(exc)
        if is_auth_error(exc):
            error_msg = f"aws_credentials_expired: {exc}"
        return RunResult(
            run=run,
            status="failure",
            error=error_msg,
            output_dir=output_dir,
            duration_seconds=duration,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def write_result_atomic(result: RunResult) -> None:
    """Write a run result to disk atomically using temp file + rename.

    Uses the POSIX atomic rename pattern: write to a temporary file in
    the same directory, then rename to the final path. This ensures
    resume detection never sees a partially-written file.

    Args:
        result: The RunResult to persist.

    Raises:
        Exception: Re-raises any write error after cleaning up the temp file.
    """
    result_path = result.run.result_path
    result_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=result_path.parent, suffix=".tmp")
    try:
        with open(fd, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        Path(tmp_path).rename(result_path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
