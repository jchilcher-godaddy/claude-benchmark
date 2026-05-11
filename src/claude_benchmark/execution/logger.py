"""Streaming log-line output for CI/pipe environments.

Provides a non-interactive progress output that prints one timestamped line
per event (START, DONE, FAIL). Used when the terminal is not interactive
(piped output, CI environments). Implements the same ProgressCallback protocol
as Dashboard so the orchestrator can use either interchangeably.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any


class LogLineOutput:
    """Non-interactive log-line output implementing the ProgressCallback protocol.

    Prints one timestamped line per event to stdout. Suitable for CI systems,
    piped output, and log file capture.

    Format::

        [HH:MM:SS] START model | profile | task | run N
        [HH:MM:SS] DONE  model | profile | task | run N | 1234 tok | $0.0012
        [HH:MM:SS] FAIL  model | profile | task | run N | error message
    """

    def __init__(self) -> None:
        self._scoring_phase_start: float = 0.0

    @staticmethod
    def _timestamp() -> str:
        """Return current time formatted as HH:MM:SS."""
        return datetime.now().strftime("%H:%M:%S")

    def worker_started(self, worker_id: int, run: Any) -> None:
        """Print a START line when a worker begins a run.

        Args:
            worker_id: The worker slot index.
            run: A BenchmarkRun with model, profile_name, task_name, run_number.
        """
        ts = self._timestamp()
        print(
            f"[{ts}] START {run.model} | {run.profile_name} | "
            f"{run.task_name} | run {run.run_number}"
        )

    def run_completed(self, worker_id: int, run: Any, result: Any) -> None:
        """Print a DONE line when a run completes successfully.

        Args:
            worker_id: The worker slot index.
            run: The BenchmarkRun that completed.
            result: The RunResult with total_tokens and cost.
        """
        ts = self._timestamp()
        print(
            f"[{ts}] DONE  {run.model} | {run.profile_name} | "
            f"{run.task_name} | run {run.run_number} | "
            f"{result.total_tokens} tok | ${result.cost:.4f}"
        )

    def run_failed(self, worker_id: int, run: Any, error: Exception) -> None:
        """Print a FAIL line when a run fails.

        Args:
            worker_id: The worker slot index.
            run: The BenchmarkRun that failed.
            error: The exception that caused the failure.
        """
        ts = self._timestamp()
        print(
            f"[{ts}] FAIL  {run.model} | {run.profile_name} | "
            f"{run.task_name} | run {run.run_number} | {error}"
        )

    # ------------------------------------------------------------------
    # ScoringProgressCallback protocol methods
    # ------------------------------------------------------------------

    # Display labels for scoring phase names
    _SCORING_PHASE_LABELS: dict[str, str] = {
        "static": "Static analysis",
        "llm": "LLM judging",
        "composite": "Compositing",
    }

    def scoring_started(self, phase: str, total: int, *, workers: int = 0) -> None:
        """Print a [SCORING] start line for the given phase.

        Args:
            phase: Phase identifier (``"static"``, ``"llm"``, or ``"composite"``).
            total: Number of items to score in this phase.
            workers: Number of concurrent workers for this phase.
        """
        self._scoring_phase_start = time.monotonic()
        ts = self._timestamp()
        label = self._SCORING_PHASE_LABELS.get(phase, phase)
        worker_info = f", {workers} workers" if workers > 1 else ""
        print(f"[{ts}] [SCORING] {label}: starting ({total} runs{worker_info})")

    def scoring_progress(
        self, phase: str, completed: int, total: int, run_key: str, *, failed: int = 0
    ) -> None:
        """Print a [SCORING] progress line, throttled for large batches.

        Prints every Nth item (where N keeps output to roughly 10 lines
        per phase) or always prints the final item.

        Args:
            phase: Phase identifier (``"static"``, ``"llm"``, or ``"composite"``).
            completed: Number of items completed so far.
            total: Total number of items in this phase.
            run_key: Unique key identifying the current run being scored.
            failed: Number of items that failed scoring so far.
        """
        # Throttle: print every Nth item or the last item
        step = max(1, total // 10)
        if completed % step != 0 and completed != total:
            return

        ts = self._timestamp()
        label = self._SCORING_PHASE_LABELS.get(phase, phase)
        elapsed = time.monotonic() - self._scoring_phase_start
        throughput = f"{completed / elapsed:.1f} runs/s" if elapsed > 0 else ""
        failed_info = f" | {failed} failed" if failed > 0 else ""
        print(f"[{ts}] [SCORING] {label}: {completed}/{total} | {throughput} | {run_key}{failed_info}")

    def scoring_completed(self, phase: str) -> None:
        """Print a [SCORING] completion line for the given phase.

        Args:
            phase: Phase identifier (``"static"``, ``"llm"``, or ``"composite"``).
        """
        ts = self._timestamp()
        label = self._SCORING_PHASE_LABELS.get(phase, phase)
        elapsed = time.monotonic() - self._scoring_phase_start
        print(f"[{ts}] [SCORING] {label}: complete ({elapsed:.1f}s)")

    def summary(
        self,
        total: int,
        succeeded: int,
        failed: int,
        cost: float,
        elapsed: float,
    ) -> None:
        """Print a completion summary line.

        Args:
            total: Total number of runs.
            succeeded: Number of successful runs.
            failed: Number of failed runs.
            cost: Total cost in USD.
            elapsed: Total elapsed time in seconds.
        """
        print(
            f"\nCompleted: {succeeded}/{total} | "
            f"Failed: {failed} | "
            f"Cost: ${cost:.2f} | "
            f"Time: {elapsed:.0f}s"
        )
