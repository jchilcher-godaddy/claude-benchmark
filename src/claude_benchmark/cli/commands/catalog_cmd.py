"""CLI catalog management commands: list, tag, remove cataloged runs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from claude_benchmark.catalog.store import (
    default_catalog_path,
    find_entries,
    load_catalog,
    remove_entry,
    save_catalog,
    tag_entry,
)

console = Console()

catalog_app = typer.Typer(name="catalog", help="Manage the results catalog")


@catalog_app.command("list")
def catalog_list(
    tag: Optional[list[str]] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Filter by tag",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Filter by model name",
    ),
    task: Optional[str] = typer.Option(
        None,
        "--task",
        help="Filter by task name",
    ),
    catalog: Optional[Path] = typer.Option(
        None,
        "--catalog",
        help="Path to catalog file",
    ),
) -> None:
    """List cataloged runs."""
    catalog_path = catalog or default_catalog_path()
    cat = load_catalog(catalog_path)

    entries = cat.entries
    if tag:
        entries = find_entries(cat, tags=tag)
    if model:
        entries = [e for e in entries if model in e.models]
    if task:
        entries = [e for e in entries if task in e.tasks]

    if not entries:
        console.print("[dim]No entries found.[/dim]")
        return

    table = Table(title=f"Catalog ({len(entries)} entries)")
    table.add_column("ID", style="bold cyan")
    table.add_column("Name")
    table.add_column("Date")
    table.add_column("Models")
    table.add_column("Tasks", justify="right")
    table.add_column("Runs", justify="right")
    table.add_column("Tags")

    for entry in entries:
        date_short = entry.timestamp[:10] if entry.timestamp else "—"
        table.add_row(
            entry.run_id,
            entry.name,
            date_short,
            ", ".join(entry.models) or "—",
            str(len(entry.tasks)),
            str(entry.total_runs),
            ", ".join(entry.tags) or "—",
        )

    console.print(table)


@catalog_app.command("tag")
def catalog_tag(
    run_id: str = typer.Argument(..., help="Run ID to tag"),
    tags: list[str] = typer.Argument(..., help="Tags to add"),
    catalog: Optional[Path] = typer.Option(
        None,
        "--catalog",
        help="Path to catalog file",
    ),
) -> None:
    """Add tags to a cataloged run."""
    catalog_path = catalog or default_catalog_path()
    cat = load_catalog(catalog_path)

    try:
        entry = tag_entry(cat, run_id, tags)
    except KeyError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    save_catalog(cat, catalog_path)
    console.print(
        f"Tagged [bold]{entry.run_id}[/bold] with: {', '.join(tags)}"
    )
    console.print(f"  All tags: {', '.join(entry.tags)}")


@catalog_app.command("remove")
def catalog_remove(
    run_id: str = typer.Argument(..., help="Run ID to remove"),
    catalog: Optional[Path] = typer.Option(
        None,
        "--catalog",
        help="Path to catalog file",
    ),
) -> None:
    """Remove a run from the catalog (does not delete results)."""
    catalog_path = catalog or default_catalog_path()
    cat = load_catalog(catalog_path)

    try:
        entry = remove_entry(cat, run_id)
    except KeyError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(1)

    save_catalog(cat, catalog_path)
    console.print(
        f"Removed [bold]{entry.run_id}[/bold] ({entry.name}) from catalog"
    )
