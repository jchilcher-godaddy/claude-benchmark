"""CLI intake command: catalog a results directory for cross-run comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from claude_benchmark.catalog.store import (
    default_catalog_path,
    intake_run,
    load_catalog,
    save_catalog,
)

console = Console()


def intake(
    results_dir: Path = typer.Argument(
        ...,
        help="Path to a results directory containing manifest.json",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Label for this run (default: directory name)",
    ),
    tag: Optional[list[str]] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Tags for this run (repeatable)",
    ),
    run_id: Optional[str] = typer.Option(
        None,
        "--id",
        help="Custom run ID (default: auto-generated)",
    ),
    catalog: Optional[Path] = typer.Option(
        None,
        "--catalog",
        help="Path to catalog file (default: results/catalog.json)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-intake even if directory is already cataloged",
    ),
) -> None:
    """Catalog a results directory for cross-run comparison.

    Validates the results directory, loads its manifest, and adds it to the
    catalog for later comparison with `claude-benchmark compare`.
    """
    catalog_path = catalog or default_catalog_path()
    cat = load_catalog(catalog_path)

    try:
        entry = intake_run(
            cat,
            results_dir=results_dir,
            name=name,
            tags=tag or [],
            run_id=run_id,
            force=force,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    save_catalog(cat, catalog_path)

    # Print summary
    table = Table(title=f"Cataloged: {entry.run_id}")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Run ID", entry.run_id)
    table.add_row("Name", entry.name)
    table.add_row("Timestamp", entry.timestamp)
    table.add_row("Path", entry.results_path)
    table.add_row("Models", ", ".join(entry.models) or "—")
    table.add_row("Profiles", ", ".join(entry.profiles) or "—")
    table.add_row("Tasks", ", ".join(entry.tasks) or "—")
    table.add_row("Total Runs", str(entry.total_runs))
    if entry.tags:
        table.add_row("Tags", ", ".join(entry.tags))
    if entry.experiment_name:
        table.add_row("Experiment", entry.experiment_name)

    console.print(table)
