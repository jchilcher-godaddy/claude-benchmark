"""Dry-run preview for benchmark execution.

Shows the full run matrix, estimated costs, and per-model breakdown
before actual execution begins. Used by the ``run`` CLI command to
give users a chance to review and confirm the execution plan.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from claude_benchmark.execution.cost import CostTracker
    from claude_benchmark.execution.parallel import BenchmarkRun


def show_dry_run(
    runs: list[BenchmarkRun],
    cost_tracker: CostTracker,
    concurrency: int,
    skipped_count: int = 0,
) -> None:
    """Display a pre-execution summary of the benchmark plan.

    Shows task/profile/model counts, total runs, concurrency level,
    estimated cost, optional cost cap, and a per-model breakdown table.

    Args:
        runs: List of BenchmarkRun instances to execute.
        cost_tracker: CostTracker for cost estimation and cap display.
        concurrency: Number of parallel workers.
        skipped_count: Number of runs skipped due to resume (already completed).
    """
    console = Console()

    # Extract unique sets
    tasks = {r.task_name for r in runs}
    profiles = {r.profile_name for r in runs}
    models = {r.model for r in runs}

    # Compute reps from runs
    combos = len(tasks) * len(profiles) * len(models)
    reps = len(runs) // combos if combos > 0 else len(runs)

    # Print banner
    console.print()
    console.print("[bold]Benchmark Plan[/bold]")
    console.print(f"  Tasks:       {len(tasks)}")
    console.print(f"  Profiles:    {len(profiles)}")
    console.print(f"  Models:      {len(models)}")
    console.print(f"  Reps:        {reps}")
    console.print(f"  Total runs:  {len(runs)}")
    console.print(f"  Concurrency: {concurrency}")
    console.print()

    # Estimated cost
    estimated = cost_tracker.estimate_total_cost(runs)
    console.print(f"  Estimated cost: ${estimated:.2f}")
    if cost_tracker.max_cost is not None:
        console.print(f"  Cost cap:       ${cost_tracker.max_cost:.2f}")
    console.print()

    # Per-model breakdown table
    model_counts: Counter[str] = Counter()
    for r in runs:
        model_counts[r.model] += 1

    table = Table(title="Runs by Model")
    table.add_column("Model", style="cyan")
    table.add_column("Runs", justify="right")
    table.add_column("Est. Cost", justify="right", style="green")

    for model in sorted(models):
        count = model_counts[model]
        model_runs = [r for r in runs if r.model == model]
        model_cost = cost_tracker.estimate_total_cost(model_runs)
        table.add_row(model, str(count), f"${model_cost:.2f}")

    console.print(table)

    # Resume info
    if skipped_count > 0:
        console.print(
            f"\n  Skipped (already completed): {skipped_count}"
        )


def confirm_or_abort() -> None:
    """Prompt the user for confirmation; abort if declined.

    Uses ``typer.confirm`` which raises ``typer.Abort()`` when the user
    declines. Called separately from ``show_dry_run`` so the ``--yes``
    flag can skip the prompt entirely.
    """
    typer.confirm("Proceed?", abort=True)
