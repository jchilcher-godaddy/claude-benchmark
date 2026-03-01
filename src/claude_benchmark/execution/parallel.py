"""Orchestrator for bounded parallel benchmark execution.

Builds a run matrix from tasks x profiles x models x reps and distributes
runs to workers via an async queue with AnyIO task groups and CapacityLimiter.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Protocol, runtime_checkable

from anyio import CapacityLimiter, create_task_group

from claude_benchmark.execution.cost import CostTracker


@dataclass
class BenchmarkRun:
    """A single benchmark run to execute.

    Represents one combination of task x profile x model x repetition.
    """

    task_name: str
    profile_name: str
    model: str
    run_number: int
    task_dir: Path
    profile_path: Path
    results_dir: Path

    @property
    def result_key(self) -> str:
        """Unique key matching the results directory convention.

        Format: ``{model}/{profile}/{task}/run-{N}``
        Must match the convention used by resume.py for detection.
        """
        return f"{self.model}/{self.profile_name}/{self.task_name}/run-{self.run_number}"

    @property
    def result_path(self) -> Path:
        """Full filesystem path for this run's result JSON file."""
        return self.results_dir / f"{self.result_key}.json"


@dataclass
class RunResult:
    """Result of executing a single benchmark run."""

    run: BenchmarkRun
    status: str  # "success" or "failure"
    error: str | None = None
    output_dir: Path | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    duration_seconds: float = 0.0
    scores: dict | None = None

    def to_dict(self) -> dict:
        """Serialize all fields for JSON writing, converting Path to str."""
        return {
            "task_name": self.run.task_name,
            "profile_name": self.run.profile_name,
            "model": self.run.model,
            "run_number": self.run.run_number,
            "result_key": self.run.result_key,
            "status": self.status,
            "error": self.error,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "duration_seconds": self.duration_seconds,
            "scores": self.scores,
        }

    @classmethod
    def failure(cls, run: BenchmarkRun, error: str) -> RunResult:
        """Create a failure result with the given error message."""
        return cls(run=run, status="failure", error=error)


@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for receiving progress updates from the orchestrator."""

    def worker_started(self, worker_id: int, run: BenchmarkRun) -> None: ...
    def run_completed(self, worker_id: int, run: BenchmarkRun, result: RunResult) -> None: ...
    def run_failed(self, worker_id: int, run: BenchmarkRun, error: Exception) -> None: ...


def build_run_matrix(
    tasks: list,
    profiles: list,
    models: list[str],
    reps: int,
    results_dir: Path,
) -> list[BenchmarkRun]:
    """Build cartesian product of tasks x profiles x models x reps.

    Args:
        tasks: Task objects with ``.name`` and ``.path`` attributes.
        profiles: Profile objects with ``.name`` and ``.path`` attributes.
        models: List of model name strings (e.g. ``["haiku", "sonnet"]``).
        reps: Number of repetitions per combination.
        results_dir: Base results directory for this benchmark session.

    Returns:
        Flat list of BenchmarkRun instances covering all combinations.
    """
    runs: list[BenchmarkRun] = []
    for task, profile, model in product(tasks, profiles, models):
        for rep in range(1, reps + 1):
            runs.append(
                BenchmarkRun(
                    task_name=task.name,
                    profile_name=profile.name,
                    model=model,
                    run_number=rep,
                    task_dir=task.path,
                    profile_path=profile.path,
                    results_dir=results_dir,
                )
            )
    return runs


async def run_benchmark_parallel(
    runs: list[BenchmarkRun],
    concurrency: int = 3,
    cost_tracker: CostTracker | None = None,
    progress: ProgressCallback | None = None,
) -> list[RunResult]:
    """Execute benchmark runs in parallel with bounded concurrency.

    Uses AnyIO task groups with a CapacityLimiter to gate concurrency
    to exactly ``concurrency`` workers running simultaneously. Runs are
    distributed via an asyncio.Queue.

    Workers continue executing remaining runs when one run fails.
    When cost cap is reached, in-flight workers finish but no new runs
    are queued.

    Args:
        runs: List of BenchmarkRun instances to execute.
        concurrency: Maximum number of simultaneous workers.
        cost_tracker: Optional tracker for cost cap enforcement.
        progress: Optional callback for progress notifications.

    Returns:
        List of RunResult instances (both successes and failures).
    """
    from claude_benchmark.execution.worker import execute_single_run, write_result_atomic

    limiter = CapacityLimiter(concurrency)
    queue: asyncio.Queue[BenchmarkRun] = asyncio.Queue()
    results: list[RunResult] = []

    # Load queue
    for run in runs:
        await queue.put(run)

    async def worker(worker_id: int) -> None:
        while True:
            # Check cost cap before taking next item
            if cost_tracker and cost_tracker.cap_reached:
                return

            try:
                run = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            async with limiter:
                if progress:
                    progress.worker_started(worker_id, run)
                try:
                    result = await execute_single_run(run)
                    results.append(result)
                    if cost_tracker:
                        cost_tracker.add(result.cost)
                    if progress:
                        progress.run_completed(worker_id, run, result)
                    write_result_atomic(result)
                except Exception as exc:
                    failed = RunResult.failure(run, error=str(exc))
                    results.append(failed)
                    write_result_atomic(failed)
                    if progress:
                        progress.run_failed(worker_id, run, exc)

    async with create_task_group() as tg:
        for i in range(concurrency):
            tg.start_soon(worker, i)

    return results
