"""Benchmark orchestrator: runs the full model x profile x task x run matrix.

Sequential execution (parallel execution deferred to Phase 5).
Each run gets a fresh isolated workspace.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from claude_benchmark.display.progress import ProgressDisplay
from claude_benchmark.display.summary import print_summary
from claude_benchmark.engine.runner import execute_run
from claude_benchmark.engine.workspace import cleanup_workspace, create_workspace
from claude_benchmark.results.aggregator import compute_aggregate
from claude_benchmark.results.schema import AggregateResult, BenchmarkManifest
from claude_benchmark.results.storage import (
    create_results_directory,
    save_aggregate,
    save_manifest,
    save_run_result,
)
from claude_benchmark.tasks.schema import TaskDefinition

logger = logging.getLogger(__name__)


async def run_benchmark_matrix(
    tasks: list[TaskDefinition],
    task_dirs: dict[str, Path],
    profiles: list[Path],
    models: list[str],
    runs_per: int,
    quiet: bool = False,
    keep_workspaces: bool = False,
) -> Path:
    """Execute the full benchmark matrix: model x profile x task x run.

    Runs sequentially (parallel execution is Phase 5).
    Each run gets a fresh isolated workspace.

    Returns the results directory path.
    """
    results_dir = create_results_directory()
    total_runs = len(tasks) * len(profiles) * len(models) * runs_per
    all_aggregates: list[AggregateResult] = []

    with ProgressDisplay(total=total_runs, quiet=quiet) as progress:
        for model in models:
            for profile in profiles:
                profile_name = profile.stem
                for task in tasks:
                    run_results = []

                    for run_num in range(1, runs_per + 1):
                        # Create isolated workspace
                        workspace = create_workspace(
                            task_dir=task_dirs[task.name],
                            profile_path=profile,
                            task=task,
                        )

                        try:
                            # Execute the run
                            result = await execute_run(
                                workspace_dir=workspace,
                                prompt=task.prompt,
                                model=model,
                                run_number=run_num,
                            )
                            run_results.append(result)

                            # Save individual run result
                            save_run_result(
                                results_dir,
                                model,
                                profile_name,
                                task.name,
                                run_num,
                                result,
                            )

                            # Update progress
                            progress.update(
                                model=model,
                                profile=profile_name,
                                task=task.name,
                                run_num=run_num,
                                total_runs=runs_per,
                                elapsed_seconds=result.wall_clock_seconds,
                            )

                            if not result.success:
                                logger.warning(
                                    "Run %d failed for %s/%s/%s: %s",
                                    run_num,
                                    model,
                                    profile_name,
                                    task.name,
                                    result.error,
                                )

                        finally:
                            if not keep_workspaces:
                                cleanup_workspace(workspace)
                            else:
                                logger.info("Keeping workspace: %s", workspace)

                    # Compute and save aggregate for this combination
                    aggregate = compute_aggregate(
                        run_results, task.name, profile_name, model
                    )
                    save_aggregate(
                        results_dir, model, profile_name, task.name, aggregate
                    )
                    all_aggregates.append(aggregate)

                    # Print completion line
                    avg_time = (
                        aggregate.wall_clock.mean if aggregate.wall_clock else 0
                    )
                    avg_tokens = (
                        aggregate.output_tokens.mean
                        if aggregate.output_tokens
                        else 0
                    )
                    progress.complete(
                        model=model,
                        profile=profile_name,
                        task=task.name,
                        num_runs=aggregate.total_runs,
                        avg_seconds=avg_time,
                        avg_tokens=avg_tokens,
                    )

    # Print summary table
    print_summary(all_aggregates, quiet=quiet)

    # Save manifest
    manifest = BenchmarkManifest(
        timestamp=datetime.now(),
        models=models,
        profiles=[p.stem for p in profiles],
        tasks=[t.name for t in tasks],
        runs_per_combination=runs_per,
        total_combinations=len(tasks) * len(profiles) * len(models),
        total_runs=total_runs,
    )
    save_manifest(results_dir, manifest)

    return results_dir
