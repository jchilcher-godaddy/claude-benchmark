"""CLI experiment command: run TOML-defined experiments with multiple variants."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from claude_benchmark.cli.discovery import discover_all_profiles, discover_all_tasks
from claude_benchmark.execution.cost import CostTracker
from claude_benchmark.execution.parallel import run_benchmark_parallel
from claude_benchmark.execution.preview import confirm_or_abort, show_dry_run
from claude_benchmark.execution.resume import detect_completed_runs, filter_remaining_runs
from claude_benchmark.experiments.loader import expand_experiment, load_experiment
from claude_benchmark.profiles.loader import discover_profiles, resolve_profile
from claude_benchmark.tasks.registry import TaskRegistry

console = Console()


@dataclass
class _TaskProxy:
    """Lightweight adapter giving TaskDefinition a .path attribute."""

    name: str
    path: Path


@dataclass
class _ProfileProxy:
    """Lightweight adapter giving Profile a .name attribute."""

    name: str
    path: Path


def _write_manifest(
    results_dir: Path,
    experiment_name: str,
    description: str,
    models: list[str],
    profiles: list[str],
    tasks: list[str],
    variants: list[str],
    reps: int,
    total_runs: int,
) -> None:
    """Write manifest.json for experiment results.

    Args:
        results_dir: The results directory for this experiment.
        experiment_name: Name of the experiment.
        description: Experiment description.
        models: List of model names used.
        profiles: List of profile names used.
        tasks: List of task names used.
        variants: List of variant labels.
        reps: Number of repetitions per variant.
        total_runs: Total number of runs.
    """
    manifest_path = results_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    combined_models = sorted(set(existing.get("models") or []) | set(models))
    combined_profiles = sorted(set(existing.get("profiles") or []) | set(profiles))
    combined_tasks = sorted(set(existing.get("tasks") or []) | set(tasks))
    combined_variants = sorted(set(existing.get("variants") or []) | set(variants))

    manifest = {
        "timestamp": datetime.now().isoformat(),
        "experiment_name": experiment_name,
        "description": description,
        "models": combined_models,
        "profiles": combined_profiles,
        "tasks": combined_tasks,
        "variants": combined_variants,
        "runs_per_combination": reps,
        "total_combinations": len(combined_tasks)
        * len(combined_profiles)
        * len(combined_models)
        * len(combined_variants),
        "total_runs": total_runs,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def experiment(
    config_path: Path = typer.Argument(
        ...,
        help="Path to TOML experiment configuration file",
    ),
    concurrency: int = typer.Option(
        3,
        "--concurrency",
        "-c",
        help="Number of parallel workers (default: 3)",
    ),
    max_cost: Optional[float] = typer.Option(
        None,
        "--max-cost",
        help="Maximum total cost in USD. In-flight runs finish when cap reached.",
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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show execution plan without running",
    ),
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
    retry_failures: bool = typer.Option(
        False,
        "--retry-failures",
        help="Re-run previously failed runs instead of skipping them on resume.",
    ),
    gocode: bool = typer.Option(
        False,
        "--gocode",
        help="Use GoCode API endpoint instead of AWS Bedrock. "
        "Requires ANTHROPIC_BASE_URL and GOCODE_API_TOKEN env vars.",
    ),
) -> None:
    """Run an experiment defined in a TOML configuration file.

    Experiments define multiple treatment arms (variants) that are executed
    across tasks, profiles, and models with statistical replication.
    """
    if gocode:
        from claude_benchmark.execution.client import validate_gocode_env

        missing = validate_gocode_env()
        if missing:
            console.print(f"[red]Error:[/red] --gocode requires: {', '.join(missing)}")
            raise typer.Exit(1)
    else:
        from claude_benchmark.execution.client import (
            attempt_sso_login,
            validate_bedrock_credentials,
        )

        cred_error = validate_bedrock_credentials()
        if cred_error:
            console.print(f"\n[yellow]AWS credential issue:[/yellow] {cred_error}")
            if attempt_sso_login(console):
                console.print()  # blank line before continuing
            else:
                console.print("[red]Cannot proceed without valid AWS credentials.[/red]")
                raise typer.Exit(1)

    # 1. Load experiment config
    if not config_path.exists():
        console.print(
            f"[red]Error:[/red] Config file not found: {config_path}",
            highlight=False,
        )
        raise typer.Exit(1)

    try:
        config = load_experiment(config_path)
    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to load experiment config: {e}",
            highlight=False,
        )
        raise typer.Exit(1)

    # 2. Discover tasks and profiles
    task_dirs = discover_all_tasks()
    profile_paths = discover_all_profiles()

    # 3. Validate that all referenced tasks and profiles exist
    missing_tasks = [t for t in config.defaults.tasks if t not in task_dirs]
    if missing_tasks:
        console.print(
            f"[red]Error:[/red] Tasks not found: {', '.join(missing_tasks)}",
            highlight=False,
        )
        raise typer.Exit(1)

    missing_profiles = [p for p in config.defaults.profiles if p not in profile_paths]
    if missing_profiles:
        console.print(
            f"[red]Error:[/red] Profiles not found: {', '.join(missing_profiles)}",
            highlight=False,
        )
        raise typer.Exit(1)

    # 3b. Collect all models across defaults and variant overrides
    all_models = sorted(
        set(config.defaults.models)
        | {m for v in config.variants if v.models for m in v.models}
    )

    # 4. Generate results_dir if not specified
    if results_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        results_dir = Path(f"results/experiment-{config.name}-{timestamp}")

    # 5. Expand experiment to BenchmarkRun list
    try:
        runs = expand_experiment(config, task_dirs, profile_paths, results_dir)
    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to expand experiment: {e}",
            highlight=False,
        )
        raise typer.Exit(1)

    # 5b. Apply gocode backend to all runs if specified
    if gocode:
        for r in runs:
            r.use_gocode = True

    # 6. Check for resume
    skipped_count = 0
    if results_dir.exists():
        completed = detect_completed_runs(results_dir, retry_failures=retry_failures)
        if completed:
            skipped_count = len(runs) - len(filter_remaining_runs(runs, completed))
            runs = filter_remaining_runs(runs, completed)
            console.print(
                f"Resuming: {skipped_count} runs already completed, "
                f"{len(runs)} remaining"
            )

    # 7. If no runs remaining
    if not runs:
        console.print("All runs already completed.")
        raise typer.Exit(0)

    # 8. Create CostTracker
    cost_tracker = CostTracker(max_cost=max_cost)

    # 9. Show dry-run preview
    console.print(f"[bold]Experiment:[/bold] {config.name}")
    if config.description:
        console.print(f"  {config.description}")
    console.print(
        f"[bold]Variants:[/bold] {', '.join(v.label for v in config.variants)}"
    )
    show_dry_run(runs, cost_tracker, concurrency, skipped_count=skipped_count)

    # 10. If --dry-run, exit after preview
    if dry_run:
        raise typer.Exit(0)

    # 11. If not --yes, prompt for confirmation
    if not yes:
        confirm_or_abort()

    # 12. Execute runs
    start_time = time.monotonic()

    from claude_benchmark.execution.dashboard import Dashboard
    from claude_benchmark.execution.logger import LogLineOutput

    is_tty = Console().is_terminal

    def _make_auth_handler(dashboard_ref=None):
        """Create auth error callback that pauses the dashboard for terminal interaction."""
        from claude_benchmark.execution.client import attempt_sso_login

        def handler(error_msg: str) -> bool:
            live = getattr(dashboard_ref, "_live", None) if dashboard_ref else None
            if live is not None:
                live.stop()
            console.print(f"\n[red bold]AWS credentials expired during experiment[/red bold]")
            console.print(f"[dim]{error_msg}[/dim]\n")
            success = attempt_sso_login(console)
            if live is not None:
                live.start()
            return success

        return handler

    if is_tty:
        dashboard = Dashboard(total_runs=len(runs), concurrency=concurrency)
        auth_handler = _make_auth_handler(dashboard_ref=dashboard)

        async def _execute_with_dashboard() -> list:
            async def _run_fn(progress_cb):
                return await run_benchmark_parallel(
                    runs,
                    concurrency=concurrency,
                    cost_tracker=cost_tracker,
                    progress=progress_cb,
                    on_auth_error=auth_handler,
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
                experiment_name=config.name,
                description=config.description,
                models=all_models,
                profiles=config.defaults.profiles,
                tasks=config.defaults.tasks,
                variants=[v.label for v in config.variants],
                reps=config.defaults.reps,
                total_runs=skipped_count,
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
        auth_handler = _make_auth_handler()

        async def _execute_log_mode() -> list:
            return await run_benchmark_parallel(
                runs,
                concurrency=concurrency,
                cost_tracker=cost_tracker,
                progress=log_output,
                on_auth_error=auth_handler,
            )

        try:
            results = asyncio.run(_execute_log_mode())
        except KeyboardInterrupt:
            elapsed = time.monotonic() - start_time
            _write_manifest(
                results_dir=results_dir,
                experiment_name=config.name,
                description=config.description,
                models=all_models,
                profiles=config.defaults.profiles,
                tasks=config.defaults.tasks,
                variants=[v.label for v in config.variants],
                reps=config.defaults.reps,
                total_runs=skipped_count,
            )
            console.print(
                f"\n[yellow]Interrupted.[/yellow] Partial results in: {results_dir}"
            )
            console.print(
                f"  Elapsed: {elapsed:.0f}s | Cost: ${cost_tracker.total_cost:.2f}"
            )
            raise typer.Exit(1)

    # 13. Score all results
    from claude_benchmark.scoring.pipeline import score_all_runs

    if is_tty:

        def _do_scoring(progress_cb):
            return score_all_runs(
                results,
                skip_llm=skip_llm_judge,
                strict=strict_scoring,
                progress=progress_cb,
            )

        results, aggregation = dashboard.run_scoring_with_display(_do_scoring)
    else:
        results, aggregation = score_all_runs(
            results,
            skip_llm=skip_llm_judge,
            strict=strict_scoring,
            progress=log_output,
        )
    progress_output = dashboard if is_tty else log_output  # type: ignore[possibly-undefined]

    # 14. Persist scored results back to disk
    from claude_benchmark.execution.worker import write_result_atomic

    for result in results:
        if result.scores:
            write_result_atomic(result)

    # 14b. Rescore previously completed but unscored runs (resume fix)
    if skipped_count > 0:
        from claude_benchmark.cli.commands.rescore import _load_results

        unscored = _load_results(
            results_dir, task_dirs, profile_paths, force=False,
        )
        if unscored:
            console.print(
                f"Rescoring {len(unscored)} previously completed but unscored runs..."
            )
            rescore_results, _ = score_all_runs(
                unscored,
                skip_llm=skip_llm_judge,
                strict=strict_scoring,
            )
            for r in rescore_results:
                if r.scores:
                    write_result_atomic(r)
            console.print(
                f"  Rescored {sum(1 for r in rescore_results if r.scores)} runs"
            )

    # Print scoring summary
    scored_count = sum(1 for r in results if r.scores and not r.scores.get("degraded"))
    degraded_count = sum(
        1 for r in results if r.scores and r.scores.get("degraded")
    )
    if scored_count or degraded_count:
        console.print(
            f"Scored: {scored_count} | Degraded: {degraded_count} | "
            f"LLM judge: {'skipped' if skip_llm_judge else 'enabled'}"
        )

    # 15. Write manifest.json
    _write_manifest(
        results_dir=results_dir,
        experiment_name=config.name,
        description=config.description,
        models=all_models,
        profiles=config.defaults.profiles,
        tasks=config.defaults.tasks,
        variants=[v.label for v in config.variants],
        reps=config.defaults.reps,
        total_runs=len(results) + skipped_count,
    )

    # 15b. Auto-intake into catalog
    try:
        from claude_benchmark.catalog.store import (
            default_catalog_path,
            intake_run,
            load_catalog,
            save_catalog,
        )

        cat_path = default_catalog_path()
        cat = load_catalog(cat_path)
        entry = intake_run(
            cat, results_dir, name=None,
            tags=[config.name], run_id=None, force=True,
        )
        save_catalog(cat, cat_path)
        console.print(f"  Cataloged as: [bold]{entry.run_id}[/bold] (tagged: {config.name})")
    except Exception:
        pass  # Don't fail the experiment if intake fails

    # 16. Print final summary
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
        console.print("\n[bold]Score Aggregation by Variant:[/bold]")
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

    # Print auth failure guidance if applicable
    auth_failures = [r for r in results if r.error and "aws_credentials_expired" in r.error]
    if auth_failures:
        console.print(
            f"\n[red bold]{len(auth_failures)} run(s) failed due to AWS credential errors.[/red bold]"
        )
        console.print("  To retry: [bold]aws sso login[/bold] then re-run with [bold]--retry-failures[/bold]")

    # 17. Auto-generate experiment report
    try:
        from claude_benchmark.reporting.experiment_generator import ExperimentReportGenerator
        from claude_benchmark.reporting.loader import load_manifest, load_results_dir

        console.print("\n[dim]...[/dim] Generating experiment report...", highlight=False)
        report_results = load_results_dir(results_dir)
        manifest = load_manifest(results_dir)
        report_path = results_dir / "report.html"

        exp_gen = ExperimentReportGenerator(results_dir, manifest=manifest)
        exp_gen.generate(
            report_path,
            results=report_results,
            llm_summary=not skip_llm_judge,
        )
        console.print(f"  [green]\u2713[/green] Report: {report_path.resolve()}", highlight=False)
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] Report generation failed: {e}", highlight=False)

    console.print(f"\n[bold]Results:[/bold] {results_dir}")
