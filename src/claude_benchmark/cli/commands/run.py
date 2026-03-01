"""CLI run command: execute benchmarks with parallel workers.

Wires the parallel execution engine, dashboard, cost tracking,
resume support, and filter flags into a single ``claude-benchmark run``
command.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from claude_benchmark.execution.cost import CostTracker
from claude_benchmark.execution.filters import filter_runs
from claude_benchmark.execution.parallel import build_run_matrix, run_benchmark_parallel
from claude_benchmark.execution.preview import confirm_or_abort, show_dry_run
from claude_benchmark.execution.resume import detect_completed_runs, filter_remaining_runs
from claude_benchmark.profiles.loader import discover_profiles, resolve_profile
from claude_benchmark.tasks.registry import TaskRegistry

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class _TaskProxy:
    """Lightweight adapter giving TaskDefinition a .path attribute for build_run_matrix."""

    name: str
    path: Path


@dataclass
class _ProfileProxy:
    """Lightweight adapter giving Profile a .name attribute for build_run_matrix."""

    name: str
    path: Path


def _load_tasks(
    task_filter: list[str] | None,
) -> list[_TaskProxy]:
    """Load tasks from the registry and return proxy objects.

    Args:
        task_filter: If provided, only include tasks with these names.

    Returns:
        List of _TaskProxy objects with .name and .path attributes.
    """
    builtin_dir = Path("tasks/builtin")
    custom_dir = Path("tasks/custom")
    search_dirs: list[Path] = []
    if builtin_dir.exists():
        search_dirs.append(builtin_dir)
    if custom_dir.exists():
        search_dirs.append(custom_dir)

    if not search_dirs:
        console.print(
            "[red]Error:[/red] No task directories found (tasks/builtin or tasks/custom)",
            highlight=False,
        )
        raise typer.Exit(1)

    registry = TaskRegistry.from_directories(*search_dirs)

    if task_filter:
        selected = []
        for name in task_filter:
            task = registry.by_name(name)
            if task is None:
                console.print(
                    f"[red]Error:[/red] Task not found: '{name}'",
                    highlight=False,
                )
                raise typer.Exit(1)
            selected.append(task)
    else:
        selected = registry.all

    if not selected:
        console.print(
            "[red]Error:[/red] No tasks found to run", highlight=False
        )
        raise typer.Exit(1)

    # Build task_dir mapping by scanning directories
    task_dirs: dict[str, Path] = {}
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for child in sorted(search_dir.iterdir()):
            if child.is_dir() and (child / "task.toml").exists():
                from claude_benchmark.tasks.loader import load_task

                try:
                    loaded = load_task(child)
                    task_dirs[loaded.name] = child
                except Exception:
                    pass

    # Build proxy objects
    proxies = []
    for task in selected:
        task_dir = task_dirs.get(task.name)
        if task_dir is None:
            console.print(
                f"[red]Error:[/red] Cannot find task directory for: '{task.name}'",
                highlight=False,
            )
            raise typer.Exit(1)
        proxies.append(_TaskProxy(name=task.name, path=task_dir))

    return proxies


def _load_profiles(
    profile_filter: list[str] | None,
) -> list[_ProfileProxy]:
    """Load profiles and return proxy objects.

    If profile_filter is provided, resolve those specific profiles.
    Otherwise, discover all profiles from the default profiles directory.

    Args:
        profile_filter: If provided, profile names/paths to resolve.

    Returns:
        List of _ProfileProxy objects with .name and .path attributes.
    """
    if profile_filter:
        proxies = []
        for name in profile_filter:
            try:
                profile = resolve_profile(name)
                proxies.append(
                    _ProfileProxy(name=profile.slug, path=profile.path)
                )
            except Exception as e:
                console.print(
                    f"[red]Error:[/red] Profile not found: '{name}' ({e})",
                    highlight=False,
                )
                raise typer.Exit(1)
        return proxies

    # Discover all profiles
    profiles = discover_profiles()
    if not profiles:
        console.print(
            "[red]Error:[/red] No profiles found in profiles/ directory",
            highlight=False,
        )
        raise typer.Exit(1)

    return [
        _ProfileProxy(name=p.slug, path=p.path) for p in profiles
    ]


def _write_manifest(
    results_dir: Path,
    models: list[str],
    profiles: list[str],
    tasks: list[str],
    reps: int,
    total_runs: int,
) -> None:
    """Write manifest.json so ``claude-benchmark report`` can discover results.

    The ``find_latest_results`` function in the reporting loader scans for
    subdirectories containing ``manifest.json``.  Without this file the
    ``report`` command fails with "No benchmark results found" unless the
    user passes ``--results-dir`` explicitly.

    Args:
        results_dir: The results directory for this benchmark session.
        models: List of model names used.
        profiles: List of profile names used.
        tasks: List of task names used.
        reps: Number of repetitions per combination.
        total_runs: Total number of runs (including resumed).
    """
    manifest_path = results_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Merge with existing manifest so previous-run models/profiles/tasks
    # are preserved when reusing --results-dir.
    existing: dict = {}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    combined_models = sorted(set(existing.get("models") or []) | set(models))
    combined_profiles = sorted(set(existing.get("profiles") or []) | set(profiles))
    combined_tasks = sorted(set(existing.get("tasks") or []) | set(tasks))

    manifest = {
        "timestamp": datetime.now().isoformat(),
        "models": combined_models,
        "profiles": combined_profiles,
        "tasks": combined_tasks,
        "runs_per_combination": reps,
        "total_combinations": len(combined_tasks) * len(combined_profiles) * len(combined_models),
        "total_runs": total_runs,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def run(
    # Concurrency control
    concurrency: int = typer.Option(
        3,
        "--concurrency",
        "-c",
        help="Number of parallel workers (default: 3)",
    ),
    # Cost control
    max_cost: Optional[float] = typer.Option(
        None,
        "--max-cost",
        help="Maximum total cost in USD. In-flight runs finish when cap reached.",
    ),
    # Filters (narrow the run matrix)
    task: Optional[list[str]] = typer.Option(
        None,
        "--task",
        "-t",
        help="Filter to specific task name(s)",
    ),
    profile: Optional[list[str]] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Filter to specific profile name(s)",
    ),
    model: Optional[list[str]] = typer.Option(
        None,
        "--model",
        "-m",
        help="Filter to specific model name(s)",
    ),
    # Execution control
    reps: int = typer.Option(
        3,
        "--reps",
        "-r",
        help="Number of repetitions per task/profile/model combo",
    ),
    results_dir: Optional[Path] = typer.Option(
        None,
        "--results-dir",
        help="Results directory. Reuse for resume support.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip dry-run confirmation prompt",
    ),
    # Dry run only
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show execution plan without running",
    ),
    # Scoring control
    skip_llm_judge: bool = typer.Option(
        False,
        "--skip-llm-judge",
        help="Skip LLM-as-judge scoring. Computes partial composite from static analysis only.",
    ),
    strict_scoring: bool = typer.Option(
        False,
        "--strict-scoring",
        help="Fail run if any scorer errors (for CI). Default: graceful degradation.",
    ),
) -> None:
    """Run benchmark tasks against CLAUDE.md profiles with parallel execution."""
    # 1. Load tasks
    task_proxies = _load_tasks(task)

    # 2. Load profiles
    profile_proxies = _load_profiles(profile)

    # 3. Default models if not specified
    models = model if model else ["sonnet"]

    # 4. Generate results_dir if not specified
    if results_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        results_dir = Path(f"results/{timestamp}")

    # 5. Build run matrix
    matrix = build_run_matrix(
        tasks=task_proxies,
        profiles=profile_proxies,
        models=models,
        reps=reps,
        results_dir=results_dir,
    )

    # 6. Apply filters (for narrowing within the already-loaded matrix)
    filtered = filter_runs(
        matrix,
        task_names=task,
        profile_names=profile,
        model_names=model,
    )

    # 7. Check for resume
    skipped_count = 0
    if results_dir.exists():
        completed = detect_completed_runs(results_dir)
        if completed:
            skipped_count = len(filtered) - len(
                filter_remaining_runs(filtered, completed)
            )
            filtered = filter_remaining_runs(filtered, completed)
            console.print(
                f"Resuming: {skipped_count} runs already completed, "
                f"{len(filtered)} remaining"
            )

    # 8. If no runs remaining
    if not filtered:
        console.print("All runs already completed.")
        raise typer.Exit(0)

    # 9. Create CostTracker
    cost_tracker = CostTracker(max_cost=max_cost)

    # 10. Show dry-run preview
    show_dry_run(filtered, cost_tracker, concurrency, skipped_count=skipped_count)

    # 11. If --dry-run, exit after preview
    if dry_run:
        raise typer.Exit(0)

    # 12. If not --yes, prompt for confirmation
    if not yes:
        confirm_or_abort()

    # 13. Create progress output based on terminal type
    start_time = time.monotonic()

    from claude_benchmark.execution.dashboard import Dashboard
    from claude_benchmark.execution.logger import LogLineOutput

    is_tty = Console().is_terminal

    if is_tty:
        dashboard = Dashboard(total_runs=len(filtered), concurrency=concurrency)

        async def _execute_with_dashboard() -> list:
            async def _run_fn(progress_cb):
                return await run_benchmark_parallel(
                    filtered,
                    concurrency=concurrency,
                    cost_tracker=cost_tracker,
                    progress=progress_cb,
                )

            results = []

            async def _wrapped(progress_cb):
                nonlocal results
                results = await _run_fn(progress_cb)

            await dashboard.run_with_display(_wrapped)
            return results

        try:
            results = asyncio.run(_execute_with_dashboard())
        except KeyboardInterrupt:
            elapsed = time.monotonic() - start_time
            _write_manifest(
                results_dir=results_dir,
                models=models,
                profiles=[p.name for p in profile_proxies],
                tasks=[t.name for t in task_proxies],
                reps=reps,
                total_runs=skipped_count,  # Only count already-written results
            )
            console.print(
                f"\n[yellow]Interrupted.[/yellow] Partial results in: {results_dir}"
            )
            console.print(
                f"  Elapsed: {elapsed:.0f}s | Cost: ${cost_tracker.total_cost:.2f}"
            )
            raise typer.Exit(1)
    else:
        log_output = LogLineOutput()

        async def _execute_log_mode() -> list:
            return await run_benchmark_parallel(
                filtered,
                concurrency=concurrency,
                cost_tracker=cost_tracker,
                progress=log_output,
            )

        try:
            results = asyncio.run(_execute_log_mode())
        except KeyboardInterrupt:
            elapsed = time.monotonic() - start_time
            _write_manifest(
                results_dir=results_dir,
                models=models,
                profiles=[p.name for p in profile_proxies],
                tasks=[t.name for t in task_proxies],
                reps=reps,
                total_runs=skipped_count,
            )
            console.print(
                f"\n[yellow]Interrupted.[/yellow] Partial results in: {results_dir}"
            )
            console.print(
                f"  Elapsed: {elapsed:.0f}s | Cost: ${cost_tracker.total_cost:.2f}"
            )
            raise typer.Exit(1)

    # 14. Score all results
    from claude_benchmark.scoring.pipeline import score_all_runs

    if is_tty:
        def _do_scoring(progress_cb):
            return score_all_runs(
                results, skip_llm=skip_llm_judge,
                strict=strict_scoring, progress=progress_cb,
            )
        results, aggregation = dashboard.run_scoring_with_display(_do_scoring)
    else:
        results, aggregation = score_all_runs(
            results, skip_llm=skip_llm_judge,
            strict=strict_scoring, progress=log_output,
        )
    progress_output = dashboard if is_tty else log_output  # type: ignore[possibly-undefined]

    # 14c. Persist scored results back to disk
    from claude_benchmark.execution.worker import write_result_atomic

    for result in results:
        if result.scores:
            write_result_atomic(result)

    # Print scoring summary
    scored_count = sum(1 for r in results if r.scores and not r.scores.get("degraded"))
    degraded_count = sum(1 for r in results if r.scores and r.scores.get("degraded"))
    if scored_count or degraded_count:
        console.print(
            f"Scored: {scored_count} | Degraded: {degraded_count} | "
            f"LLM judge: {'skipped' if skip_llm_judge else 'enabled'}"
        )

    # 14b. Write manifest.json so `claude-benchmark report` can find results
    _write_manifest(
        results_dir=results_dir,
        models=models,
        profiles=[p.name for p in profile_proxies],
        tasks=[t.name for t in task_proxies],
        reps=reps,
        total_runs=len(results) + skipped_count,
    )

    # 15. Print final summary
    elapsed = time.monotonic() - start_time
    succeeded = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failure")
    if hasattr(progress_output, "summary"):
        progress_output.summary(
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            cost=cost_tracker.total_cost,
            elapsed=elapsed,
        )

    # Print per-variant aggregation summary if available
    if aggregation:
        console.print("\n[bold]Score Aggregation:[/bold]")
        for variant_key, agg_data in sorted(aggregation.items()):
            scores_agg = agg_data.get("scores", {})
            composite_agg = scores_agg.get("composite")
            if composite_agg:
                mean = composite_agg.get("mean", 0)
                ci_lower = composite_agg.get("ci_lower", 0)
                ci_upper = composite_agg.get("ci_upper", 0)
                console.print(
                    f"  {variant_key}: {mean:.1f} (95% CI: {ci_lower:.1f}-{ci_upper:.1f})"
                )

    console.print(f"\n[bold]Results:[/bold] {results_dir}")
