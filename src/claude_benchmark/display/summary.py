"""Matrix summary table for benchmark results."""

from __future__ import annotations

from collections import defaultdict

from rich.console import Console
from rich.table import Table

from claude_benchmark.results.schema import AggregateResult


def build_summary_table(aggregates: list[AggregateResult]) -> Table:
    """Build matrix summary table: profile x model with avg tokens and time."""
    table = Table(title="Benchmark Summary")
    table.add_column("Profile", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Tasks", justify="right")
    table.add_column("Avg Tokens (in)", justify="right")
    table.add_column("Avg Tokens (out)", justify="right")
    table.add_column("Avg Time (s)", justify="right")
    table.add_column("Success Rate", justify="right")

    # Group by (profile, model)
    groups: dict[tuple[str, str], list[AggregateResult]] = defaultdict(list)
    for agg in aggregates:
        groups[(agg.profile_name, agg.model)].append(agg)

    for (profile, model), aggs in sorted(groups.items()):
        total_tasks = len(aggs)
        avg_in = _avg_stat(aggs, "input_tokens")
        avg_out = _avg_stat(aggs, "output_tokens")
        avg_time = _avg_stat(aggs, "wall_clock")
        avg_success = sum(a.success_rate for a in aggs) / len(aggs) if aggs else 0

        table.add_row(
            profile,
            model,
            str(total_tasks),
            _format_tokens(avg_in),
            _format_tokens(avg_out),
            f"{avg_time:.1f}" if avg_time else "-",
            f"{avg_success:.0%}",
        )

    return table


def _avg_stat(aggs: list[AggregateResult], field: str) -> float | None:
    """Average the mean value of a StatsSummary field across aggregates."""
    vals = []
    for a in aggs:
        stat = getattr(a, field, None)
        if stat and stat.mean is not None:
            vals.append(stat.mean)
    return sum(vals) / len(vals) if vals else None


def _format_tokens(val: float | None) -> str:
    if val is None:
        return "-"
    if val >= 1000:
        return f"{val / 1000:.1f}k"
    return f"{val:.0f}"


def print_summary(aggregates: list[AggregateResult], quiet: bool = False):
    """Print the summary table to console."""
    if quiet:
        return
    console = Console()
    table = build_summary_table(aggregates)
    console.print()
    console.print(table)
