"""CLI run-accounting command: CONSORT-style flow audit of an experiment.

Counts runs by status, classifies failures by reason, builds a Mermaid flow
diagram, and produces per-cell breakdown tables to surface concentration of
failures or exclusions.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()


# Failure-reason classifier patterns. Order matters: first match wins.
_FAILURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("timeout", re.compile(r"timeout|timed out|deadline", re.IGNORECASE)),
    ("rate_limit", re.compile(r"rate.?limit|429|too many requests", re.IGNORECASE)),
    ("auth_error", re.compile(r"401|403|unauthor|forbidden|credentials", re.IGNORECASE)),
    (
        "api_error",
        re.compile(r"\b(400|500|502|503|504)\b|api error|server error|bad gateway", re.IGNORECASE),
    ),
    ("parse_error", re.compile(r"json|parse|decode|malformed", re.IGNORECASE)),
    ("network_error", re.compile(r"connection|network|dns|refused|reset", re.IGNORECASE)),
)


@dataclass
class StatusCounts:
    """Aggregated status counts plus failure-reason breakdown."""

    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    timeout: int = 0
    other_status: int = 0
    failure_reasons: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    judged: int = 0
    judge_skipped: int = 0
    scored_clean: int = 0
    degraded: int = 0
    score_missing: int = 0


@dataclass
class CellKey:
    """A (model, variant) cell key."""

    model: str
    variant: str

    def __hash__(self) -> int:
        return hash((self.model, self.variant))


# ---------- helpers ----------


def classify_failure(error: Optional[str]) -> str:
    """Bucket a failure by error message."""
    if not error:
        return "unknown"
    for label, pattern in _FAILURE_PATTERNS:
        if pattern.search(error):
            return label
    return "other"


def load_manifest(results_dir: Path) -> Optional[dict]:
    manifest_path = results_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_aggregated(results_dir: Path) -> Optional[dict]:
    """Load benchmark-results.json (aggregated). Used as a fallback for variants/models."""
    p = results_dir / "benchmark-results.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def planned_count(manifest: Optional[dict], aggregated: Optional[dict]) -> Optional[int]:
    if manifest:
        if "total_runs" in manifest:
            try:
                return int(manifest["total_runs"])
            except (TypeError, ValueError):
                pass
        try:
            n_models = len(manifest.get("models", []))
            n_profiles = len(manifest.get("profiles", []))
            n_tasks = len(manifest.get("tasks", []))
            n_variants = len(manifest.get("variants", [])) or 1
            n_reps = int(manifest.get("runs_per_combination", 0))
            if n_models and n_tasks and n_reps:
                return n_models * (n_profiles or 1) * n_tasks * n_variants * n_reps
        except (TypeError, ValueError):
            pass
    if aggregated:
        meta = aggregated.get("metadata", {})
        if isinstance(meta, dict) and "total_runs" in meta:
            try:
                return int(meta["total_runs"])
            except (TypeError, ValueError):
                pass
    return None


# ---------- core walk ----------


def walk_experiment(
    results_dir: Path,
) -> tuple[StatusCounts, dict[CellKey, StatusCounts]]:
    """Walk run-*.json files and produce overall + per-cell counts."""
    overall = StatusCounts()
    per_cell: dict[CellKey, StatusCounts] = defaultdict(StatusCounts)

    for path in sorted(results_dir.rglob("run-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            overall.attempted += 1
            overall.failed += 1
            overall.failure_reasons["parse_error"] += 1
            continue

        model = data.get("model") or "unknown"
        variant = data.get("variant_label") or "bare"
        cell = per_cell[CellKey(model, variant)]

        status = data.get("status")
        overall.attempted += 1
        cell.attempted += 1

        if status == "success":
            overall.succeeded += 1
            cell.succeeded += 1
            scores = data.get("scores")
            if not isinstance(scores, dict):
                overall.score_missing += 1
                cell.score_missing += 1
                continue
            if scores.get("degraded"):
                overall.degraded += 1
                cell.degraded += 1
            else:
                overall.scored_clean += 1
                cell.scored_clean += 1
            llm = scores.get("llm")
            if isinstance(llm, dict) and llm.get("normalized") is not None:
                overall.judged += 1
                cell.judged += 1
            elif isinstance(llm, dict) and isinstance(llm.get("criteria"), list) and llm["criteria"]:
                overall.judged += 1
                cell.judged += 1
            else:
                overall.judge_skipped += 1
                cell.judge_skipped += 1
        elif status == "timeout":
            overall.timeout += 1
            cell.timeout += 1
            overall.failed += 1
            cell.failed += 1
            overall.failure_reasons["timeout"] += 1
            cell.failure_reasons["timeout"] += 1
        elif status == "failure":
            overall.failed += 1
            cell.failed += 1
            reason = classify_failure(data.get("error"))
            overall.failure_reasons[reason] += 1
            cell.failure_reasons[reason] += 1
        else:
            overall.other_status += 1
            cell.other_status += 1

    return overall, dict(per_cell)


# ---------- markdown rendering ----------


def render_mermaid(
    planned: Optional[int],
    counts: StatusCounts,
) -> str:
    planned_str = f"{planned:,}" if planned is not None else "unknown"
    lines = ["```mermaid", "flowchart TD"]
    lines.append(f"    A[Planned: {planned_str}] --> B[Attempted: {counts.attempted:,}]")
    lines.append(f"    B --> C[Succeeded: {counts.succeeded:,}]")
    lines.append(f"    B --> D[Failed: {counts.failed:,}]")
    if counts.other_status:
        lines.append(f"    B --> O[Other status: {counts.other_status:,}]")
    lines.append(f"    C --> E[Judged: {counts.judged:,}]")
    lines.append(f"    E --> F[Scored clean: {counts.scored_clean:,}]")
    lines.append(f"    E --> G[Degraded: {counts.degraded:,}]")
    if counts.judge_skipped:
        lines.append(f"    C --> H[Judge skipped: {counts.judge_skipped:,}]")
    if counts.score_missing:
        lines.append(f"    C --> S[Score missing: {counts.score_missing:,}]")
    lines.append("```")
    return "\n".join(lines)


def render_failure_breakdown(counts: StatusCounts) -> str:
    if not counts.failure_reasons:
        return "_No failures recorded._"
    lines = ["| reason | count |", "|---|---:|"]
    for reason, n in sorted(
        counts.failure_reasons.items(), key=lambda kv: -kv[1]
    ):
        lines.append(f"| {reason} | {n:,} |")
    return "\n".join(lines)


def render_per_cell_table(per_cell: dict[CellKey, StatusCounts]) -> str:
    if not per_cell:
        return "_No per-cell data._"
    header = (
        "| model | variant | attempted | succeeded | failed | timeout "
        "| degraded | judge skipped |"
    )
    sep = "|---|---|---:|---:|---:|---:|---:|---:|"
    lines = [header, sep]
    for key in sorted(per_cell.keys(), key=lambda k: (k.model, k.variant)):
        c = per_cell[key]
        lines.append(
            f"| {key.model} | {key.variant} | {c.attempted:,} | {c.succeeded:,} "
            f"| {c.failed:,} | {c.timeout:,} | {c.degraded:,} | {c.judge_skipped:,} |"
        )
    return "\n".join(lines)


def render_exclusions() -> str:
    return (
        "Exclusion criteria (runs that do **not** flow into the scored aggregate):\n"
        "- `status != success` (failure, timeout, or other terminal status)\n"
        "- Successful run with missing or null `scores` block\n"
        "- Successful run with missing LLM judge output (judge skipped) — "
        "still counted as scored under static-only fallback, but flagged as `degraded`\n"
        "- Successful run with `scores.degraded == true` (any scorer failed)"
    )


def render_experiment_report(
    results_dir: Path,
    planned: Optional[int],
    counts: StatusCounts,
    per_cell: dict[CellKey, StatusCounts],
) -> str:
    out: list[str] = [f"# Run accounting: {results_dir.name}\n"]
    if planned is not None:
        diff = counts.attempted - planned
        out.append(
            f"- Planned: **{planned:,}** | Attempted: **{counts.attempted:,}** "
            f"({diff:+,d} vs plan)"
        )
    else:
        out.append(
            f"- Planned: unknown (no manifest.json) | Attempted: **{counts.attempted:,}**"
        )
    out.append(
        f"- Succeeded: **{counts.succeeded:,}** | Failed: **{counts.failed:,}** "
        f"| Timeout: **{counts.timeout:,}** | Other status: **{counts.other_status:,}**"
    )
    out.append(
        f"- Judged: **{counts.judged:,}** | Judge skipped: **{counts.judge_skipped:,}** "
        f"| Scored clean: **{counts.scored_clean:,}** | Degraded: **{counts.degraded:,}** "
        f"| Score missing: **{counts.score_missing:,}**"
    )
    out.append("")
    out.append("## Flow\n")
    out.append(render_mermaid(planned, counts))
    out.append("")
    out.append("## Failure breakdown\n")
    out.append(render_failure_breakdown(counts))
    out.append("")
    out.append("## Per-cell breakdown (model x variant)\n")
    out.append(render_per_cell_table(per_cell))
    out.append("")
    out.append("## Exclusion criteria\n")
    out.append(render_exclusions())
    out.append("")
    return "\n".join(out)


def render_summary_table(rows: list[dict]) -> str:
    if not rows:
        return "_No experiments found._"
    header = (
        "| experiment | planned | attempted | succeeded | failed | timeout "
        "| degraded |"
    )
    sep = "|---|---:|---:|---:|---:|---:|---:|"
    lines = [header, sep]
    totals = {
        "planned": 0,
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "timeout": 0,
        "degraded": 0,
    }
    any_planned = False
    for row in rows:
        planned = row["planned"]
        planned_str = f"{planned:,}" if planned is not None else "?"
        if planned is not None:
            totals["planned"] += planned
            any_planned = True
        c: StatusCounts = row["counts"]
        totals["attempted"] += c.attempted
        totals["succeeded"] += c.succeeded
        totals["failed"] += c.failed
        totals["timeout"] += c.timeout
        totals["degraded"] += c.degraded
        lines.append(
            f"| {row['name']} | {planned_str} | {c.attempted:,} | "
            f"{c.succeeded:,} | {c.failed:,} | {c.timeout:,} | {c.degraded:,} |"
        )
    grand_planned = f"{totals['planned']:,}" if any_planned else "?"
    lines.append(
        f"| **TOTAL** | **{grand_planned}** | **{totals['attempted']:,}** | "
        f"**{totals['succeeded']:,}** | **{totals['failed']:,}** | "
        f"**{totals['timeout']:,}** | **{totals['degraded']:,}** |"
    )
    return "\n".join(lines)


# ---------- CLI entrypoint ----------


def run_accounting(
    results_dir: Path = typer.Argument(
        ..., help="Path to a single experiment results directory"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write markdown report to this path"
    ),
    all_experiments: bool = typer.Option(
        False,
        "--all-experiments",
        help="Treat results_dir as the parent directory and walk all experiment-* subdirs",
    ),
) -> None:
    """CONSORT-style accounting for experiment runs."""
    if not results_dir.exists() or not results_dir.is_dir():
        console.print(f"[red]Error:[/red] Directory not found: {results_dir}")
        raise typer.Exit(1)

    if all_experiments:
        exp_dirs = sorted(
            d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith("experiment-")
        )
        if not exp_dirs:
            console.print(f"[red]Error:[/red] No experiment-* subdirs in {results_dir}")
            raise typer.Exit(1)
        console.print(f"Walking {len(exp_dirs)} experiment directories...")
        rows: list[dict] = []
        report_parts: list[str] = [f"# Run accounting (all experiments under {results_dir})\n"]
        for exp_dir in exp_dirs:
            counts, per_cell = walk_experiment(exp_dir)
            planned = planned_count(load_manifest(exp_dir), load_aggregated(exp_dir))
            rows.append({"name": exp_dir.name, "planned": planned, "counts": counts})
            report_parts.append(render_experiment_report(exp_dir, planned, counts, per_cell))
        summary = render_summary_table(rows)
        report = (
            report_parts[0]
            + "## Summary\n\n"
            + summary
            + "\n\n---\n\n"
            + "\n---\n\n".join(report_parts[1:])
        )
    else:
        counts, per_cell = walk_experiment(results_dir)
        planned = planned_count(load_manifest(results_dir), load_aggregated(results_dir))
        report = render_experiment_report(results_dir, planned, counts, per_cell)

    if output:
        output.write_text(report, encoding="utf-8")
        console.print(f"Wrote report to {output}")
    else:
        typer.echo(report)
