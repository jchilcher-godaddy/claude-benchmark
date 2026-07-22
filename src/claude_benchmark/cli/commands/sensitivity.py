"""CLI sensitivity command: re-aggregate composite scores under varying weights.

Walks per-run JSONs, extracts raw static components and LLM scores, then
recomputes mean composite per variant under a grid of (composite_split,
static_component) weight regimes. Produces a markdown report.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()


# ---------- weight specs ----------

WeightTriple = tuple[float, float, float]
StaticGrid = list[WeightTriple]
SplitGrid = list[float]

DEFAULT_SPLITS: SplitGrid = [0.3, 0.4, 0.5, 0.6, 0.7]
DEFAULT_STATIC_GRIDS: StaticGrid = [
    (0.5, 0.3, 0.2),
    (0.4, 0.3, 0.3),
    (0.6, 0.2, 0.2),
    (0.34, 0.33, 0.33),
]
DEFAULT_SPLIT = 0.5
DEFAULT_STATIC = (0.5, 0.3, 0.2)
CONTROL_VARIANT = "bare"
WEIGHT_TOLERANCE = 1e-3


@dataclass(frozen=True)
class Regime:
    """A single weight regime."""

    static_weight: float
    static_components: WeightTriple

    @property
    def llm_weight(self) -> float:
        return 1.0 - self.static_weight

    @property
    def label(self) -> str:
        s = self.static_weight
        a, b, c = self.static_components
        return f"S={s:.2f}|t={a:.2f}/l={b:.2f}/c={c:.2f}"

    def is_default(self) -> bool:
        return (
            abs(self.static_weight - DEFAULT_SPLIT) < WEIGHT_TOLERANCE
            and all(
                abs(x - y) < WEIGHT_TOLERANCE
                for x, y in zip(self.static_components, DEFAULT_STATIC)
            )
        )


@dataclass
class RunRecord:
    """Minimal per-run data needed for re-aggregation."""

    variant: str
    model: str
    test_pass_rate: float
    lint_score: float
    complexity_score: float
    llm_normalized: Optional[float]


# ---------- parsing & validation ----------


def _parse_split_list(raw: str) -> SplitGrid:
    out: SplitGrid = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            v = float(piece)
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid split weight: {piece!r}") from exc
        if not (0.0 <= v <= 1.0):
            raise typer.BadParameter(f"Split weight {v} not in [0, 1]")
        out.append(v)
    if not out:
        raise typer.BadParameter("Empty split-weight list")
    return out


def _parse_static_grids(raw: str) -> StaticGrid:
    out: StaticGrid = []
    for group in raw.split(";"):
        group = group.strip()
        if not group:
            continue
        parts = [p.strip() for p in group.split(",")]
        if len(parts) != 3:
            raise typer.BadParameter(
                f"Static-component weights must be 3 floats: {group!r}"
            )
        try:
            triple = (float(parts[0]), float(parts[1]), float(parts[2]))
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid float in {group!r}") from exc
        if abs(sum(triple) - 1.0) > WEIGHT_TOLERANCE:
            raise typer.BadParameter(
                f"Static-component weights must sum to 1.0: {triple} -> {sum(triple):.4f}"
            )
        out.append(triple)
    if not out:
        raise typer.BadParameter("Empty static-grid list")
    return out


def build_regimes(splits: SplitGrid, static_grids: StaticGrid) -> list[Regime]:
    return [Regime(s, t) for s in splits for t in static_grids]


# ---------- core math ----------


def llm_normalized_from_criteria(criteria: list[dict]) -> Optional[float]:
    """Compute (avg_score - 1) * 25 from criteria list. None if empty/invalid."""
    if not criteria:
        return None
    try:
        scores = [float(c["score"]) for c in criteria if "score" in c]
    except (TypeError, ValueError):
        return None
    if not scores:
        return None
    avg = sum(scores) / len(scores)
    return (avg - 1.0) * 25.0


def extract_run_record(data: dict) -> Optional[RunRecord]:
    """Extract a RunRecord from a run-N.json payload, or None if unusable."""
    if data.get("status") != "success":
        return None
    scores = data.get("scores")
    if not isinstance(scores, dict):
        return None
    static = scores.get("static")
    if not isinstance(static, dict):
        return None
    try:
        tpr = float(static["test_pass_rate"])
        lint = float(static["lint_score"])
        cx = float(static["complexity_score"])
    except (KeyError, TypeError, ValueError):
        return None

    llm_norm: Optional[float] = None
    llm = scores.get("llm")
    if isinstance(llm, dict):
        if "normalized" in llm and llm["normalized"] is not None:
            try:
                llm_norm = float(llm["normalized"])
            except (TypeError, ValueError):
                llm_norm = None
        if llm_norm is None:
            crit = llm.get("criteria")
            if isinstance(crit, list):
                llm_norm = llm_normalized_from_criteria(crit)
    if llm_norm is None:
        composite = scores.get("composite")
        if isinstance(composite, dict):
            ll = composite.get("llm_normalized")
            if ll is not None:
                try:
                    llm_norm = float(ll)
                except (TypeError, ValueError):
                    llm_norm = None

    variant = data.get("variant_label") or "bare"
    model = data.get("model") or "unknown"
    return RunRecord(
        variant=variant,
        model=model,
        test_pass_rate=tpr,
        lint_score=lint,
        complexity_score=cx,
        llm_normalized=llm_norm,
    )


def composite_for_run(run: RunRecord, regime: Regime) -> float:
    """Compute composite score for one run under one regime."""
    a, b, c = regime.static_components
    static_weighted = (
        run.test_pass_rate * a + run.lint_score * b + run.complexity_score * c
    )
    if run.llm_normalized is None:
        return static_weighted
    return (
        static_weighted * regime.static_weight
        + run.llm_normalized * regime.llm_weight
    )


def re_aggregate(
    runs: list[RunRecord],
    regimes: list[Regime],
) -> dict[str, dict[str, float]]:
    """Compute mean composite per variant under each regime.

    Returns: {variant: {regime_label: mean_composite}}
    """
    by_variant: dict[str, list[RunRecord]] = defaultdict(list)
    for r in runs:
        by_variant[r.variant].append(r)

    out: dict[str, dict[str, float]] = {}
    for variant, records in by_variant.items():
        per_regime: dict[str, float] = {}
        for regime in regimes:
            vals = [composite_for_run(r, regime) for r in records]
            per_regime[regime.label] = (
                sum(vals) / len(vals) if vals else float("nan")
            )
        out[variant] = per_regime
    return out


def load_runs(results_dir: Path) -> list[RunRecord]:
    """Walk results_dir for run-*.json and produce RunRecord list."""
    runs: list[RunRecord] = []
    for path in sorted(results_dir.rglob("run-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rec = extract_run_record(data)
        if rec is not None:
            runs.append(rec)
    return runs


# ---------- ranking & robustness ----------


def rank_within_regime(
    means: dict[str, dict[str, float]], regime_label: str
) -> dict[str, int]:
    """1-based rank (higher composite = rank 1)."""
    ranking = sorted(
        means.items(), key=lambda kv: kv[1].get(regime_label, float("-inf")), reverse=True
    )
    return {variant: idx + 1 for idx, (variant, _) in enumerate(ranking)}


def compute_robustness(
    means: dict[str, dict[str, float]],
    regimes: list[Regime],
    control: str,
) -> dict[str, dict]:
    """For each variant, compute % regimes with same sign-of-(variant - control) as default.

    Returns: {variant: {'sign_stable_pct': float, 'flips': int, 'total': int,
                        'default_sign': int, 'always_beats': bool, 'always_loses': bool}}
    """
    default = next((r for r in regimes if r.is_default()), regimes[0])
    default_label = default.label
    out: dict[str, dict] = {}
    if control not in means:
        for variant in means:
            out[variant] = {
                "sign_stable_pct": float("nan"),
                "flips": 0,
                "total": len(regimes),
                "default_sign": 0,
                "always_beats": False,
                "always_loses": False,
            }
        return out

    for variant, regime_means in means.items():
        if variant == control:
            out[variant] = {
                "sign_stable_pct": 100.0,
                "flips": 0,
                "total": len(regimes),
                "default_sign": 0,
                "always_beats": False,
                "always_loses": False,
            }
            continue
        default_delta = regime_means.get(default_label, 0.0) - means[control].get(
            default_label, 0.0
        )
        default_sign = 1 if default_delta > 0 else (-1 if default_delta < 0 else 0)
        same = 0
        beats = 0
        loses = 0
        for regime in regimes:
            d = regime_means.get(regime.label, 0.0) - means[control].get(
                regime.label, 0.0
            )
            sign = 1 if d > 0 else (-1 if d < 0 else 0)
            if sign == default_sign:
                same += 1
            if d > 0:
                beats += 1
            elif d < 0:
                loses += 1
        total = len(regimes)
        out[variant] = {
            "sign_stable_pct": (same / total * 100.0) if total else float("nan"),
            "flips": total - same,
            "total": total,
            "default_sign": default_sign,
            "always_beats": beats == total,
            "always_loses": loses == total,
        }
    return out


# ---------- markdown rendering ----------


def render_markdown(
    results_dir: Path,
    runs: list[RunRecord],
    regimes: list[Regime],
    means: dict[str, dict[str, float]],
    robustness: dict[str, dict],
    control: str,
) -> str:
    lines: list[str] = []
    lines.append(f"# Sensitivity analysis: {results_dir.name}\n")
    lines.append(f"- Total runs analyzed: **{len(runs)}**")
    n_variants = len(means)
    n_regimes = len(regimes)
    lines.append(f"- Variants: **{n_variants}**, Regimes: **{n_regimes}**")
    lines.append(f"- Control variant: **{control}**")
    static_only = sum(1 for r in runs if r.llm_normalized is None)
    lines.append(
        f"- Runs without LLM judge score (static-only fallback): **{static_only}**"
    )
    lines.append("")

    lines.append("## Regimes\n")
    lines.append("| # | Static split | Component weights (test/lint/cx) | Default? |")
    lines.append("|---|---|---|---|")
    for idx, regime in enumerate(regimes, start=1):
        a, b, c = regime.static_components
        is_def = "yes" if regime.is_default() else ""
        lines.append(
            f"| {idx} | {regime.static_weight:.2f} (LLM {regime.llm_weight:.2f}) "
            f"| {a:.2f} / {b:.2f} / {c:.2f} | {is_def} |"
        )
    lines.append("")

    lines.append("## Mean composite by variant x regime\n")
    header_cells = ["variant"] + [f"R{i + 1}" for i in range(n_regimes)] + [
        "robust % (sign-stable vs control)"
    ]
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("|" + "|".join(["---"] * len(header_cells)) + "|")

    ranks_per_regime = {
        regime.label: rank_within_regime(means, regime.label) for regime in regimes
    }

    sorted_variants = sorted(
        means.keys(),
        key=lambda v: -means[v].get(
            next(r for r in regimes if r.is_default()).label
            if any(r.is_default() for r in regimes)
            else regimes[0].label,
            float("-inf"),
        ),
    )
    for variant in sorted_variants:
        cells: list[str] = [variant]
        for regime in regimes:
            mean = means[variant][regime.label]
            rank = ranks_per_regime[regime.label][variant]
            cells.append(f"{mean:.2f} (#{rank})")
        rob = robustness.get(variant, {})
        if variant == control:
            cells.append("control")
        else:
            pct = rob.get("sign_stable_pct", float("nan"))
            tag = ""
            if rob.get("always_beats"):
                tag = " (always beats)"
            elif rob.get("always_loses"):
                tag = " (always loses)"
            cells.append(f"{pct:.0f}%{tag}")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Summary\n")
    robust_winners: list[str] = []
    robust_losers: list[str] = []
    flippers: list[tuple[str, int]] = []
    for variant, rob in robustness.items():
        if variant == control:
            continue
        if rob.get("always_beats"):
            robust_winners.append(variant)
        elif rob.get("always_loses"):
            robust_losers.append(variant)
        elif rob.get("flips", 0) > 0:
            flippers.append((variant, rob["flips"]))

    if robust_winners:
        lines.append(
            "- **Robust winners** (beat `"
            + control
            + "` in every regime): "
            + ", ".join(f"`{v}`" for v in sorted(robust_winners))
        )
    if robust_losers:
        lines.append(
            "- **Robust losers** (lose to `"
            + control
            + "` in every regime): "
            + ", ".join(f"`{v}`" for v in sorted(robust_losers))
        )
    if flippers:
        flippers.sort(key=lambda x: -x[1])
        details = ", ".join(f"`{v}` ({n}/{len(regimes)})" for v, n in flippers)
        lines.append(f"- **Sign-flippers** (regime changes the sign of delta): {details}")
    if not robust_winners and not robust_losers and not flippers:
        lines.append("- No variants other than control found.")
    lines.append("")
    lines.append(
        "Robustness column = % of regimes where sign(variant - control) matches "
        "the sign under the default regime (S=0.50, t=0.50/l=0.30/c=0.20)."
    )
    return "\n".join(lines) + "\n"


# ---------- CLI entrypoint ----------


def sensitivity(
    results_dir: Path = typer.Argument(..., help="Path to experiment results directory"),
    static_weights: Optional[str] = typer.Option(
        None,
        "--static-weights",
        help='Comma-separated static splits (e.g. "0.3,0.5,0.7"). LLM weight = 1 - split.',
    ),
    static_component_weights: Optional[str] = typer.Option(
        None,
        "--static-component-weights",
        help=(
            'Semicolon-separated triples for test/lint/complexity weights '
            '(e.g. "0.5,0.3,0.2;0.4,0.3,0.3"). Each triple must sum to 1.0.'
        ),
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write markdown report to this path (otherwise stdout).",
    ),
    control: str = typer.Option(
        CONTROL_VARIANT,
        "--control",
        help='Variant treated as the control for the robustness column.',
    ),
) -> None:
    """Re-aggregate composite scores under varying weight regimes."""
    if not results_dir.exists() or not results_dir.is_dir():
        console.print(f"[red]Error:[/red] Results directory not found: {results_dir}")
        raise typer.Exit(1)

    splits = _parse_split_list(static_weights) if static_weights else DEFAULT_SPLITS
    grids = (
        _parse_static_grids(static_component_weights)
        if static_component_weights
        else DEFAULT_STATIC_GRIDS
    )
    regimes = build_regimes(splits, grids)

    console.print(f"Loading runs from {results_dir} ...")
    runs = load_runs(results_dir)
    if not runs:
        console.print("[red]Error:[/red] No usable runs found.")
        raise typer.Exit(1)
    console.print(f"Loaded {len(runs)} runs across {len({r.variant for r in runs})} variants.")

    means = re_aggregate(runs, regimes)
    robustness = compute_robustness(means, regimes, control)
    report = render_markdown(results_dir, runs, regimes, means, robustness, control)

    if output:
        output.write_text(report, encoding="utf-8")
        console.print(f"Wrote report to {output}")
    else:
        typer.echo(report)
