"""CLI compare command: compare results across cataloged runs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from claude_benchmark.catalog.compare import compare_entries
from claude_benchmark.catalog.store import (
    default_catalog_path,
    find_entries,
    load_catalog,
)

console = Console()


def compare(
    run_ids: list[str] = typer.Argument(
        ...,
        help="Run IDs or tags to compare (at least 2)",
    ),
    dimension: Optional[list[str]] = typer.Option(
        None,
        "--dimension",
        "-d",
        help="Filter to specific dimension(s)",
    ),
    p_threshold: float = typer.Option(
        0.05,
        "--p-threshold",
        help="Significance level (default: 0.05)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write HTML comparison report to this path",
    ),
    catalog: Optional[Path] = typer.Option(
        None,
        "--catalog",
        help="Path to catalog file",
    ),
    by_tag: bool = typer.Option(
        False,
        "--by-tag",
        help="Interpret arguments as tags instead of run IDs",
    ),
    no_llm_summary: bool = typer.Option(
        False,
        "--no-llm-summary",
        help="Skip LLM narrative in report",
    ),
    cross_variant: bool = typer.Option(
        False,
        "--cross-variant",
        "-x",
        help="Compare individual variants across experiment runs (expands each variant into a separate arm)",
    ),
) -> None:
    """Compare results across cataloged benchmark runs.

    Finds overlapping (model, profile, task) combinations and performs
    pairwise statistical comparison with effect size analysis.
    """
    catalog_path = catalog or default_catalog_path()
    cat = load_catalog(catalog_path)

    # Resolve arguments to catalog entries
    if by_tag:
        entries = find_entries(cat, tags=run_ids)
    else:
        entries = find_entries(cat, run_ids=run_ids)

    if len(entries) < 2:
        console.print(
            f"[red]Error:[/red] Need at least 2 entries to compare, found {len(entries)}.",
            highlight=False,
        )
        if not by_tag:
            console.print(
                "[dim]Tip: Use `claude-benchmark catalog list` to see available run IDs.[/dim]"
            )
        raise typer.Exit(1)

    console.print(
        f"Comparing {len(entries)} runs: "
        + ", ".join(f"[bold]{e.run_id}[/bold] ({e.name})" for e in entries)
    )

    # Run comparison
    try:
        report = compare_entries(
            entries,
            dimensions=dimension,
            p_threshold=p_threshold,
            cross_variant=cross_variant,
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] Comparison failed: {e}", highlight=False)
        raise typer.Exit(1)

    # Print CLI summary
    console.print(
        f"\n[bold]Overlapping combinations:[/bold] {len(report.overlapping_keys)}"
    )
    for run_id, unique in report.unique_keys.items():
        if unique:
            console.print(f"  Unique to {run_id}: {len(unique)} combinations")

    if not report.comparisons:
        console.print("\n[yellow]No overlapping combinations with sufficient data for comparison.[/yellow]")
        raise typer.Exit(0)

    # Summary table
    significant = [c for c in report.comparisons if c.is_significant]
    console.print(
        f"\n[bold]Comparisons:[/bold] {len(report.comparisons)} total, "
        f"{len(significant)} significant (p < {p_threshold})"
    )

    if significant:
        table = Table(title="Significant Differences")
        table.add_column("Model/Profile/Task")
        table.add_column("Dimension")
        table.add_column("Run A")
        table.add_column("Mean A", justify="right")
        table.add_column("Run B")
        table.add_column("Mean B", justify="right")
        table.add_column("Delta", justify="right")
        table.add_column("p-value", justify="right")
        table.add_column("Effect", justify="right")

        for c in significant:
            key_str = f"{c.key_model}/{c.key_profile}/{c.key_task}"
            delta_str = f"{c.delta_pct:+.1%}"
            table.add_row(
                key_str,
                c.dimension,
                c.run_a_name,
                f"{c.run_a_mean:.1f}",
                c.run_b_name,
                f"{c.run_b_mean:.1f}",
                delta_str,
                f"{c.p_value:.4f}",
                c.effect_label,
            )

        console.print(table)
    else:
        console.print(
            "\n[green]No statistically significant differences found.[/green]"
        )

    # Generate HTML report if requested
    if output:
        try:
            from claude_benchmark.catalog.report_generator import ComparisonReportGenerator
            from claude_benchmark.reporting.loader import load_results_dir

            console.print(f"\n[dim]...[/dim] Generating comparison report...", highlight=False)

            # For cross-variant mode, use the virtual entries from the report
            report_entries = report.entries
            results_by_entry = {}
            if cross_variant:
                # Re-expand to get virtual results for report generation
                from claude_benchmark.catalog.compare import expand_to_virtual_entries
                orig_results = {}
                for entry in entries:
                    orig_results[entry.run_id] = load_results_dir(Path(entry.results_path))
                report_entries, results_by_entry = expand_to_virtual_entries(
                    entries, orig_results,
                )
            else:
                for entry in report_entries:
                    results_by_entry[entry.run_id] = load_results_dir(Path(entry.results_path))

            gen = ComparisonReportGenerator(
                entries=report_entries,
                comparisons=report.comparisons,
                comparison_report=report,
            )
            gen.generate(
                output,
                results_by_entry=results_by_entry,
                llm_summary=not no_llm_summary,
            )
            console.print(
                f"  [green]\u2713[/green] Report: {output.resolve()}", highlight=False
            )
        except Exception as e:
            console.print(
                f"  [yellow]Warning:[/yellow] Report generation failed: {e}",
                highlight=False,
            )
