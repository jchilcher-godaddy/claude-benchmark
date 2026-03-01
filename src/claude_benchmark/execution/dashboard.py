"""Rich Live terminal dashboard for interactive benchmark progress display.

Provides a Docker-build-style live-updating dashboard showing overall progress
(completion count, percentage, ETA) and per-worker status lines (task name,
profile name, model name). Implements the ProgressCallback protocol so the
orchestrator can drive the display.

In non-TTY environments (pipes, CI), automatically falls back to LogLineOutput
for streaming log lines. TTY detection is automatic via Rich Console.is_terminal.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from rich.console import Console, Group
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

if TYPE_CHECKING:
    from rich.live import Live


class Dashboard:
    """Rich Live dashboard implementing the ProgressCallback protocol.

    Shows an overall progress bar with completion count, percentage, and ETA,
    plus per-worker lines displaying task name, profile name, and model name.
    Completed runs show a checkmark (success) or X (failure) icon.

    Usage::

        dashboard = Dashboard(total_runs=100, concurrency=3)
        await dashboard.run_with_display(execute_fn)

    Where ``execute_fn`` is an async callable that accepts a progress callback.
    """

    # Display labels for scoring phase names
    _SCORING_PHASE_LABELS: dict[str, str] = {
        "static": "Static analysis",
        "llm": "LLM judging",
        "composite": "Compositing",
    }

    def __init__(self, total_runs: int, concurrency: int) -> None:
        self.console = Console()
        self.total_runs = total_runs
        self.concurrency = concurrency
        self.completed: int = 0
        self.failed: int = 0
        self.workers: dict[int, str] = {}
        self.start_time: float = time.monotonic()

        # Scoring phase display state
        self.scoring_phase: str | None = None
        self.scoring_total: int = 0
        self.scoring_completed_count: int = 0
        self.scoring_current_run: str = ""

        self.progress = Progress(
            TextColumn("[bold blue]Overall"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[bold]{task.percentage:.0f}%"),
            TimeRemainingColumn(),
        )
        self.overall_task = self.progress.add_task(
            "Running", total=total_runs
        )

        # Scoring-phase Rich Progress bar (separate from execution progress)
        self._scoring_progress = Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[bold]{task.percentage:.0f}%"),
        )
        self._scoring_task_id: int | None = None
        self._scoring_display_active: bool = False

        # Reference to active Live display for triggering updates
        self._live: Live | None = None

    def _render(self) -> Group:
        """Build the dashboard renderable: progress bar + worker status table.

        When a scoring phase is active (``self.scoring_phase`` is set),
        an additional line is appended showing scoring progress.
        """
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Worker", width=10)
        table.add_column("Status")
        for wid in range(self.concurrency):
            status = self.workers.get(wid, "[dim]idle[/dim]")
            table.add_row(f"Worker {wid}", status)

        if self.scoring_phase is not None:
            from rich.text import Text

            scoring_line = Text.from_markup(
                f"[bold cyan]Scoring:[/bold cyan] {self.scoring_phase} "
                f"{self.scoring_completed_count}/{self.scoring_total}"
                f" | {self.scoring_current_run}"
            )
            return Group(self.progress, table, scoring_line)

        return Group(self.progress, table)

    def _render_scoring(self) -> Group:
        """Build a scoring-only renderable: progress bar + current run label.

        Used during the scoring phase (after execution) so the stale worker
        table is not shown.
        """
        from rich.text import Text

        parts: list = [self._scoring_progress]
        if self.scoring_current_run:
            parts.append(
                Text.from_markup(
                    f"  [dim]{self.scoring_current_run}[/dim]"
                )
            )
        return Group(*parts)

    def _refresh_live(self) -> None:
        """Trigger a Live display update if active."""
        if self._live is not None:
            if self._scoring_display_active:
                self._live.update(self._render_scoring())
            else:
                self._live.update(self._render())

    def worker_started(self, worker_id: int, run: Any) -> None:
        """Record that a worker has started a new benchmark run.

        Args:
            worker_id: The worker slot index.
            run: A BenchmarkRun with task_name, profile_name, and model attrs.
        """
        self.workers[worker_id] = (
            f"{run.task_name} | {run.profile_name} | {run.model}"
        )
        self._refresh_live()

    def run_completed(self, worker_id: int, run: Any, result: Any) -> None:
        """Record a successfully completed run.

        Args:
            worker_id: The worker slot index.
            run: The BenchmarkRun that completed.
            result: The RunResult from the run.
        """
        self.completed += 1
        self.progress.update(self.overall_task, completed=self.completed)
        self.workers[worker_id] = f"[green]\u2713[/green] {run.task_name}"
        self._refresh_live()

    def run_failed(self, worker_id: int, run: Any, error: Exception) -> None:
        """Record a failed run.

        Args:
            worker_id: The worker slot index.
            run: The BenchmarkRun that failed.
            error: The exception that caused the failure.
        """
        self.completed += 1
        self.failed += 1
        self.progress.update(self.overall_task, completed=self.completed)
        self.workers[worker_id] = f"[red]\u2717[/red] {run.task_name}"
        self._refresh_live()

    # ------------------------------------------------------------------
    # ScoringProgressCallback protocol methods
    # ------------------------------------------------------------------

    def scoring_started(self, phase: str, total: int) -> None:
        """Signal that a scoring phase has begun.

        Updates the dashboard to show the current scoring phase name and
        total item count.  Creates (or resets) a task on the scoring
        progress bar so it starts fresh for each phase.

        Args:
            phase: Phase identifier (``"static"``, ``"llm"``, or ``"composite"``).
            total: Number of items to score in this phase.
        """
        display_label = self._SCORING_PHASE_LABELS.get(phase, phase)
        self.scoring_phase = display_label
        self.scoring_total = total
        self.scoring_completed_count = 0
        self.scoring_current_run = ""

        # Reset the Rich Progress bar for this phase
        if self._scoring_task_id is not None:
            self._scoring_progress.remove_task(self._scoring_task_id)
        self._scoring_task_id = self._scoring_progress.add_task(
            display_label, total=total
        )
        self._refresh_live()

    def scoring_progress(
        self, phase: str, completed: int, total: int, run_key: str
    ) -> None:
        """Update the dashboard with per-item scoring progress.

        Args:
            phase: Phase identifier (``"static"``, ``"llm"``, or ``"composite"``).
            completed: Number of items completed so far.
            total: Total number of items in this phase.
            run_key: Unique key identifying the current run being scored.
        """
        self.scoring_completed_count = completed
        self.scoring_current_run = run_key

        # Advance the Rich Progress bar
        if self._scoring_task_id is not None:
            self._scoring_progress.update(
                self._scoring_task_id, completed=completed
            )
        self._refresh_live()

    def scoring_completed(self, phase: str) -> None:
        """Signal that a scoring phase has finished.

        Marks the scoring progress task as complete and clears the phase
        state from the dashboard.

        Args:
            phase: Phase identifier (``"static"``, ``"llm"``, or ``"composite"``).
        """
        if self._scoring_task_id is not None:
            self._scoring_progress.update(
                self._scoring_task_id,
                completed=self.scoring_total,
            )
        self.scoring_phase = None
        self.scoring_current_run = ""
        self._refresh_live()

    def summary(
        self,
        total: int,
        succeeded: int,
        failed: int,
        cost: float,
        elapsed: float,
    ) -> None:
        """Print a final summary line after all runs complete.

        Args:
            total: Total number of runs.
            succeeded: Number of successful runs.
            failed: Number of failed runs.
            cost: Total cost in USD.
            elapsed: Total elapsed time in seconds.
        """
        self.console.print(
            f"\nCompleted: {succeeded}/{total} | "
            f"Failed: {failed} | "
            f"Cost: ${cost:.2f} | "
            f"Time: {elapsed:.0f}s"
        )

    async def run_with_display(
        self,
        execute_fn: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        """Run the execution function with the appropriate display mode.

        If the console is an interactive terminal, uses Rich Live for a
        live-updating dashboard. Otherwise, falls back to LogLineOutput
        for streaming log lines suitable for CI/pipe environments.

        Args:
            execute_fn: An async callable that accepts a progress callback
                implementing worker_started, run_completed, and run_failed.
        """
        if self.console.is_terminal:
            from rich.live import Live

            with Live(
                self._render(),
                console=self.console,
                refresh_per_second=4,
                transient=True,
            ) as live:
                self._live = live
                try:
                    await execute_fn(self)
                finally:
                    live.update(self._render())
                    self._live = None
        else:
            # Non-TTY fallback: delegate to LogLineOutput
            from claude_benchmark.execution.logger import LogLineOutput

            fallback = LogLineOutput()
            await execute_fn(fallback)

    def run_scoring_with_display(
        self,
        score_fn: Callable[..., Any],
    ) -> Any:
        """Run the scoring function inside a fresh Live context.

        Opens a new Rich ``Live`` display so that scoring progress is
        visible after the execution-phase ``Live`` has already exited.
        The scoring callbacks (``scoring_started``, ``scoring_progress``,
        ``scoring_completed``) drive the display via ``_refresh_live``.

        Args:
            score_fn: A callable that accepts a
                :class:`~claude_benchmark.scoring.pipeline.ScoringProgressCallback`
                and returns the scoring result.

        Returns:
            Whatever ``score_fn`` returns (typically a
            ``(results, aggregation)`` tuple).
        """
        from rich.live import Live

        self._scoring_display_active = True
        with Live(
            self._render_scoring(),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        ) as live:
            self._live = live
            try:
                return score_fn(self)
            finally:
                self._live = None
                self._scoring_display_active = False
