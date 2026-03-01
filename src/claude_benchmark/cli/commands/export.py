"""CLI export command: export benchmark results as JSON and/or CSV."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from claude_benchmark.reporting.exporter import export_csv, export_json, export_raw_data
from claude_benchmark.reporting.loader import (
    filter_results,
    find_latest_results,
    load_results_dir,
)

console = Console()


def export_data(
    results_dir: Optional[Path] = typer.Option(
        None, "--results-dir", help="Results directory (default: most recent)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Output directory for export files"
    ),
    format: Optional[str] = typer.Option(
        None, "--format", help="Export format: 'json', 'csv', or both (default)"
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
) -> None:
    """Export benchmark results as JSON and/or CSV."""
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
    try:
        results = load_results_dir(results_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}", highlight=False)
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}", highlight=False)
        raise typer.Exit(1)

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

    # 4. Determine output directory
    export_dir = output_dir if output_dir is not None else results_dir

    # 5. Validate format flag
    if format is not None and format not in ("json", "csv"):
        console.print(
            f"[red]Error:[/red] Invalid format '{format}'. "
            "Must be 'json', 'csv', or omit for both.",
            highlight=False,
        )
        raise typer.Exit(1)

    # 6. Export based on format
    exported_paths: list[Path] = []
    if format == "json":
        json_path = export_json(results, export_dir)
        exported_paths.append(json_path)
    elif format == "csv":
        csv_path = export_csv(results, export_dir)
        exported_paths.append(csv_path)
    else:
        json_path, csv_path = export_raw_data(results, export_dir)
        exported_paths.extend([json_path, csv_path])

    # 7. Print data summary
    console.print("\n[bold]Export Summary[/bold]")
    console.print(f"  Profiles: {len(results.profiles)}")
    console.print(f"  Tasks: {len(results.tasks)}")
    console.print(f"  Total runs: {results.metadata.total_runs}")

    # 8. Print output paths (always absolute)
    console.print("")
    for path in exported_paths:
        console.print(f"[bold]Exported:[/bold] {path.resolve()}")
