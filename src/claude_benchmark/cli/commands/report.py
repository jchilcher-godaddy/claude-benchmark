"""CLI report command: generate HTML benchmark report."""
from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from claude_benchmark.reporting.exporter import export_raw_data
from claude_benchmark.reporting.generator import ReportGenerator
from claude_benchmark.reporting.loader import (
    filter_results,
    find_latest_results,
    load_results_dir,
    load_task_descriptions,
)
from claude_benchmark.reporting.regression import detect_all_regressions

console = Console()


def _step(msg: str) -> None:
    """Print a progress step indicator."""
    console.print(f"  [dim]...[/dim] {msg}", highlight=False)


def _done(msg: str) -> None:
    """Print a completed step indicator."""
    console.print(f"  [green]\u2713[/green] {msg}", highlight=False)


def report(
    results_dir: Optional[Path] = typer.Option(
        None, "--results-dir", help="Results directory (default: most recent)"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output path for HTML report"
    ),
    no_export: bool = typer.Option(
        False, "--no-export", help="Skip raw data export"
    ),
    no_open: bool = typer.Option(
        False, "--no-open", help="Don't open report in browser"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite without prompting"
    ),
    task: Optional[list[str]] = typer.Option(
        None, "--task", "-t", help="Filter to specific task(s)"
    ),
    profile: Optional[list[str]] = typer.Option(
        None, "--profile", "-p", help="Filter to specific profile(s)"
    ),
    model: Optional[list[str]] = typer.Option(
        None, "--model", "-m", help="Filter to specific model(s)"
    ),
    no_llm_summary: bool = typer.Option(
        False, "--no-llm-summary", help="Skip LLM-generated narrative summary"
    ),
) -> None:
    """Generate HTML benchmark report from results."""
    # 1. Resolve results directory
    if results_dir is None:
        results_dir = find_latest_results()
        if results_dir is None:
            console.print(
                "[red]Error:[/red] No benchmark results found. "
                "Run `claude-benchmark run` first.",
                highlight=False,
            )
            raise typer.Exit(1)

    # 2. Load results
    _step("Loading results...")
    try:
        results = load_results_dir(results_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}", highlight=False)
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}", highlight=False)
        raise typer.Exit(1)
    _done(
        f"Loaded {len(results.profiles)} profiles, "
        f"{len(results.tasks)} tasks, "
        f"{results.metadata.total_runs} runs"
    )

    # 3. Apply filters (if any provided)
    if task is not None or profile is not None or model is not None:
        results = filter_results(
            results,
            task_names=task,
            profile_names=profile,
            model_names=model,
        )
        if not results.profiles or not results.tasks:
            console.print(
                "[yellow]Warning:[/yellow] No data matches the specified filters.",
                highlight=False,
            )
            raise typer.Exit(1)
        _done(
            f"Filtered to {len(results.profiles)} profiles, "
            f"{len(results.tasks)} tasks"
        )

    # 4. Load task descriptions from task.toml files
    task_descriptions: dict[str, str] = {}
    for tasks_dir in [Path("tasks/builtin"), Path("tasks/custom")]:
        task_descriptions.update(load_task_descriptions(tasks_dir))

    # 5. Write results.json (archival; makes results directory self-contained)
    results_json_path = results_dir / "results.json"
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(results.to_export_dict(), f, indent=2, default=str)

    # 5. Detect regressions
    _step("Detecting regressions...")
    regressions = detect_all_regressions(results)
    flagged = [r for r in regressions if r.is_regression]
    _done(f"Regression check complete ({len(flagged)} found)")

    # 6. Determine output path
    output_path = output if output is not None else results_dir / "report.html"
    if output_path.exists() and not force and console.is_terminal:
        typer.confirm(f"File exists: {output_path}. Overwrite?", abort=True)

    # 7. Export raw data first (unless --no-export) so CSV can be passed to generator
    json_path = None
    csv_path = None
    csv_content = None
    if not no_export:
        _step("Exporting raw data...")
        json_path, csv_path = export_raw_data(results, results_dir)
        csv_content = csv_path.read_text(encoding="utf-8") if csv_path.exists() else ""
        _done("Exported JSON and CSV")

    # 8. Generate report (pass pre-loaded results, regressions, and CSV to avoid redundant work)
    _step("Generating HTML report...")
    generator = ReportGenerator(results_dir)
    generator.generate(
        output_path,
        results=results,
        regressions=regressions,
        csv_content=csv_content,
        task_descriptions=task_descriptions,
        llm_summary=not no_llm_summary,
    )
    _done("HTML report generated")

    # 9. Print regression summary
    generator.print_cli_summary(regressions)

    # 10. Print output paths (always absolute)
    console.print(f"\n[bold]Report:[/bold] {output_path.resolve()}")
    if json_path is not None:
        console.print(f"[bold]JSON:[/bold] {json_path.resolve()}")
    if csv_path is not None:
        console.print(f"[bold]CSV:[/bold] {csv_path.resolve()}")

    # 11. Auto-open browser (unless --no-open)
    if not no_open:
        webbrowser.open(output_path.resolve().as_uri())
