"""CLI command for judge calibration: score known-quality code to find the best judge model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from claude_benchmark.calibration.degrader import generate_calibration_samples
from claude_benchmark.calibration.metrics import CRITERIA_NAMES, compute_calibration_report
from claude_benchmark.calibration.runner import run_calibration

console = Console()


def _discover_task_dirs(task_filter: list[str] | None = None) -> list[Path]:
    """Discover task directories from builtin and custom dirs."""
    search_dirs = [Path("tasks/builtin"), Path("tasks/custom")]
    task_dirs: list[Path] = []

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for child in sorted(search_dir.iterdir()):
            if child.is_dir() and (child / "task.toml").exists():
                if task_filter is None or child.name in task_filter:
                    task_dirs.append(child)

    return task_dirs


def calibrate(
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Comma-separated judge models to calibrate (default: haiku,sonnet,opus)",
    ),
    reps: Optional[int] = typer.Option(
        None,
        "--reps",
        "-r",
        help="Repetitions per model (overrides per-model defaults)",
    ),
    task: Optional[str] = typer.Option(
        None,
        "--task",
        "-t",
        help="Comma-separated task names to use (default: all builtin tasks)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write JSON report to this path",
    ),
    concurrency: int = typer.Option(
        5,
        "--concurrency",
        "-c",
        help="Max parallel API calls",
    ),
) -> None:
    """Calibrate LLM judge models by scoring known-quality code samples.

    Scores reference solutions and degraded versions with each candidate model,
    measures variance and discrimination, and recommends the best judge.
    """
    # Parse models
    models = [m.strip() for m in model.split(",")] if model else None

    # Parse task filter
    task_filter = [t.strip() for t in task.split(",")] if task else None

    # Discover tasks
    task_dirs = _discover_task_dirs(task_filter)
    if not task_dirs:
        console.print("[red]Error:[/red] No tasks found", highlight=False)
        raise typer.Exit(1)

    # Generate samples
    console.print(f"Discovering tasks... found {len(task_dirs)} tasks")
    samples = generate_calibration_samples(task_dirs)
    if not samples:
        console.print("[red]Error:[/red] No calibration samples generated (no reference solutions?)", highlight=False)
        raise typer.Exit(1)

    tiers = {"gold": 0, "mild": 0, "severe": 0}
    for s in samples:
        tiers[s.tier] += 1
    console.print(
        f"Generated {len(samples)} samples: "
        f"{tiers['gold']} gold, {tiers['mild']} mild, {tiers['severe']} severe"
    )

    # Build reps_per_model
    reps_per_model = None
    if reps is not None:
        effective_models = models or ["haiku", "sonnet", "opus"]
        reps_per_model = {m: reps for m in effective_models}

    # Compute total API calls
    effective_models = models or ["haiku", "sonnet", "opus"]
    if reps_per_model:
        total_calls = sum(len(samples) * reps_per_model.get(m, 5) for m in effective_models)
    else:
        from claude_benchmark.calibration.runner import DEFAULT_REPS
        total_calls = sum(len(samples) * DEFAULT_REPS.get(m, 5) for m in effective_models)

    console.print(
        f"Models: {', '.join(effective_models)} | "
        f"Total API calls: {total_calls} | Concurrency: {concurrency}"
    )
    console.print()

    # Run calibration with progress bar
    from rich.progress import Progress

    with Progress(console=console) as progress:
        bar = progress.add_task("Scoring samples...", total=total_calls)

        def progress_cb(completed: int, total: int) -> None:
            progress.update(bar, completed=completed)

        cal_results = run_calibration(
            samples=samples,
            models=models,
            reps_per_model=reps_per_model,
            concurrency=concurrency,
            progress_callback=progress_cb,
        )

    # Compute metrics
    report = compute_calibration_report(cal_results)

    # Display results
    _print_summary_table(report)
    _print_criterion_table(report)
    _print_inter_rater(report)
    _print_recommendation(report)

    # Write JSON if requested
    if output:
        _write_json_report(output, report, cal_results)
        console.print(f"\nJSON report written to: {output}")


def _print_summary_table(report) -> None:
    table = Table(title="Judge Calibration Summary")
    table.add_column("Model", style="bold")
    table.add_column("Determinism %", justify="right")
    table.add_column("Variance", justify="right")
    table.add_column("Discrimination (d)", justify="right")
    table.add_column("Gold Mean", justify="right")
    table.add_column("Mild Mean", justify="right")
    table.add_column("Severe Mean", justify="right")
    table.add_column("Tier Corr", justify="right")
    table.add_column("Score", justify="right", style="bold")

    for mm in sorted(report.model_metrics.values(), key=lambda m: -m.recommendation_score):
        table.add_row(
            mm.model,
            f"{mm.pct_deterministic:.0f}%",
            f"{mm.mean_variance:.3f}",
            f"{mm.discrimination_d:.2f}",
            f"{mm.gold_mean:.1f}",
            f"{mm.mild_mean:.1f}",
            f"{mm.severe_mean:.1f}",
            f"{mm.tier_rank_correlation:.2f}",
            f"{mm.recommendation_score:.2f}",
        )

    console.print()
    console.print(table)


def _print_criterion_table(report) -> None:
    table = Table(title="Per-Criterion Discrimination (Cohen's d)")
    table.add_column("Model", style="bold")
    for criterion in CRITERIA_NAMES:
        table.add_column(criterion, justify="right")

    for mm in sorted(report.model_metrics.values(), key=lambda m: -m.recommendation_score):
        row = [mm.model]
        for criterion in CRITERIA_NAMES:
            d = mm.per_criterion_discrimination.get(criterion, 0.0)
            row.append(f"{d:.2f}")
        table.add_row(*row)

    console.print()
    console.print(table)


def _print_inter_rater(report) -> None:
    console.print(
        f"\nInter-rater agreement (avg pairwise Spearman r): "
        f"[bold]{report.inter_rater_agreement:.3f}[/bold]"
    )


def _print_recommendation(report) -> None:
    console.print(
        f"\n[bold green]Recommendation:[/bold green] {report.reasoning}"
    )


def _write_json_report(path: Path, report, cal_results) -> None:
    data = {
        "recommended_model": report.recommended_model,
        "reasoning": report.reasoning,
        "inter_rater_agreement": report.inter_rater_agreement,
        "models": {},
        "metadata": {
            "started_at": cal_results.started_at,
            "finished_at": cal_results.finished_at,
            "total_results": len(cal_results.results),
            "successful": sum(1 for r in cal_results.results if r.score is not None),
            "failed": sum(1 for r in cal_results.results if r.score is None),
        },
    }

    for mm in report.model_metrics.values():
        data["models"][mm.model] = {
            "recommendation_score": round(mm.recommendation_score, 3),
            "mean_variance": round(mm.mean_variance, 4),
            "pct_deterministic": round(mm.pct_deterministic, 1),
            "discrimination_d": round(mm.discrimination_d, 3),
            "per_criterion_discrimination": {
                k: round(v, 3) for k, v in mm.per_criterion_discrimination.items()
            },
            "gold_mean": round(mm.gold_mean, 2),
            "mild_mean": round(mm.mild_mean, 2),
            "severe_mean": round(mm.severe_mean, 2),
            "tier_rank_correlation": round(mm.tier_rank_correlation, 3),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
