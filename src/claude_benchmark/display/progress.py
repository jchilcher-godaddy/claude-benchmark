"""Rich-based progress display for benchmark execution.

Shows a compact updating progress line during execution.
Format: [N/total] model | profile | task | run X/Y | elapsed
"""

from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.text import Text


class ProgressDisplay:
    """Rich Live-based progress display for benchmark execution."""

    def __init__(self, total: int, quiet: bool = False):
        self.total = total
        self.quiet = quiet
        self.console = Console()
        self._live: Live | None = None
        self._current = 0

    def __enter__(self):
        if not self.quiet:
            self._live = Live(console=self.console, refresh_per_second=4)
            self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.__exit__(*args)

    def update(
        self,
        model: str,
        profile: str,
        task: str,
        run_num: int,
        total_runs: int,
        elapsed_seconds: float,
    ):
        """Update the progress line."""
        self._current += 1
        if self._live:
            text = Text(
                f"[{self._current}/{self.total}] {model} | {profile} | {task} "
                f"| run {run_num}/{total_runs} | {elapsed_seconds:.0f}s"
            )
            self._live.update(text)

    def complete(
        self,
        model: str,
        profile: str,
        task: str,
        num_runs: int,
        avg_seconds: float,
        avg_tokens: float,
    ):
        """Print completion line for a task group (printed permanently, not overwritten)."""
        if not self.quiet:
            token_str = (
                f"{avg_tokens / 1000:.1f}k"
                if avg_tokens >= 1000
                else f"{avg_tokens:.0f}"
            )
            self.console.print(
                f"  [green]\u2713[/green] {model} | {profile} | {task} "
                f"| {num_runs} runs | avg {avg_seconds:.0f}s | avg {token_str} tokens"
            )
