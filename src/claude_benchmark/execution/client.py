"""Anthropic API client factory.

Centralizes client creation so the --gocode flag only needs
one code path for switching between Bedrock and direct API.
Also provides pre-flight credential validation and interactive
SSO re-authentication for the Bedrock path.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time

import anthropic

logger = logging.getLogger(__name__)

# Short model name -> Bedrock cross-region model ID
BEDROCK_MODEL_MAP: dict[str, str] = {
    "sonnet": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "haiku": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "opus": "us.anthropic.claude-opus-4-6-v1",
}

# Short model name -> standard Anthropic model ID (GoCode endpoint)
GOCODE_MODEL_MAP: dict[str, str] = {
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
    "opus": "claude-opus-4-6",
}


def create_client(use_gocode: bool = False) -> anthropic.Anthropic | anthropic.AnthropicBedrock:
    """Create an Anthropic API client for the appropriate backend.

    Args:
        use_gocode: If True, use the GoCode (standard Anthropic) endpoint
            configured via ANTHROPIC_BASE_URL and GOCODE_API_TOKEN env vars.
            If False, use AWS Bedrock (default).

    Returns:
        An Anthropic or AnthropicBedrock client instance.

    Raises:
        RuntimeError: If use_gocode is True but required env vars are missing.
    """
    if use_gocode:
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        api_key = os.environ.get("GOCODE_API_TOKEN") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if not base_url or not api_key:
            raise RuntimeError(
                "--gocode requires ANTHROPIC_BASE_URL and GOCODE_API_TOKEN "
                "(or ANTHROPIC_AUTH_TOKEN) environment variables"
            )
        return anthropic.Anthropic(base_url=base_url, api_key=api_key)
    return anthropic.AnthropicBedrock()


def resolve_model_id(short_name: str, use_gocode: bool = False) -> str:
    """Map a short model name to the appropriate model ID.

    Args:
        short_name: Short model name (e.g. "sonnet", "haiku", "opus").
        use_gocode: If True, return standard Anthropic model ID.
            If False, return Bedrock model ID.

    Returns:
        The resolved model ID string, or short_name unchanged if not mapped.
    """
    model_map = GOCODE_MODEL_MAP if use_gocode else BEDROCK_MODEL_MAP
    return model_map.get(short_name, short_name)


def validate_gocode_env() -> list[str]:
    """Check that required GoCode environment variables are set.

    Returns:
        List of missing variable names (empty if all present).
    """
    missing = []
    if not os.environ.get("ANTHROPIC_BASE_URL"):
        missing.append("ANTHROPIC_BASE_URL")
    if not (os.environ.get("GOCODE_API_TOKEN") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        missing.append("GOCODE_API_TOKEN (or ANTHROPIC_AUTH_TOKEN)")
    return missing


def validate_bedrock_credentials() -> str | None:
    """Pre-flight check for valid AWS credentials.

    Attempts to resolve credentials through the boto3 session
    (the same credential chain that ``AnthropicBedrock`` uses internally).

    Returns:
        None if credentials are valid, or an error message string.
    """
    try:
        import boto3

        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials is None:
            return "No AWS credentials found"
        # Force credential resolution — triggers SSO token refresh check
        frozen = credentials.get_frozen_credentials()
        if not frozen.access_key:
            return "AWS credentials incomplete (no access key)"
        return None
    except Exception as exc:
        return f"AWS credentials expired or invalid: {exc}"


def attempt_sso_login(console: object, timeout: int = 300, poll_interval: int = 5) -> bool:
    """Wait for the user to refresh AWS credentials, polling until valid or timeout.

    Instead of running ``aws sso login`` as a blocking subprocess (which can
    hang invisibly when the dashboard obscures the prompt), this displays a
    persistent, highly visible message and polls for credential validity.
    The user runs ``aws sso login`` in another terminal at their convenience.

    Args:
        console: A ``rich.console.Console`` instance for terminal output.
        timeout: Maximum seconds to wait for valid credentials (default 300).
        poll_interval: Seconds between credential checks (default 5).

    Returns:
        True if credentials became valid before timeout, False otherwise.
    """
    profile = os.environ.get("AWS_PROFILE")
    login_cmd = "aws sso login"
    if profile:
        login_cmd += f" --profile {profile}"

    console.print()
    console.print("[red bold]" + "=" * 60 + "[/red bold]")
    console.print("[red bold]  AWS CREDENTIALS EXPIRED — BENCHMARK PAUSED[/red bold]")
    console.print("[red bold]" + "=" * 60 + "[/red bold]")
    console.print()
    console.print(f"  Run this in another terminal:  [bold cyan]{login_cmd}[/bold cyan]")
    console.print()
    console.print(f"  Waiting up to {timeout // 60}m for credentials to refresh...")
    console.print(f"  The benchmark will resume automatically once logged in.")
    console.print()

    deadline = time.monotonic() + timeout
    checks = 0
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        checks += 1
        error = validate_bedrock_credentials()
        if error is None:
            console.print("[green bold]  Credentials refreshed — resuming benchmark.[/green bold]")
            console.print()
            return True
        remaining = int(deadline - time.monotonic())
        if remaining > 0 and checks % 6 == 0:
            # Reminder every ~30s so it stays visible
            mins, secs = divmod(remaining, 60)
            console.print(f"  [dim]Still waiting... {mins}m{secs}s remaining. "
                          f"Run: {login_cmd}[/dim]")

    console.print("[red bold]  Timed out waiting for credentials. "
                  "Remaining runs will be marked as failed.[/red bold]")
    console.print()
    return False
