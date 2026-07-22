"""CLI: ``claude-benchmark rigor`` — publication-grade statistical analysis.

Loads runs from one or many experiment directories, fits a mixed-effects
model with task as the clustering variable, applies Holm-Bonferroni and
Benjamini-Hochberg corrections to all variants-vs-control contrasts, runs
cluster bootstraps, and computes power and MDE. Emits a markdown report.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from rich.console import Console

from claude_benchmark.analysis.bootstrap import (
    BootstrapDiffCI,
    cluster_bootstrap_diff_ci,
)
from claude_benchmark.analysis.corrections import correct_pvalues
from claude_benchmark.analysis.loader import LoadStats, load_runs, load_runs_multi
from claude_benchmark.analysis.mixed_effects import MixedEffectsResult, fit_mixed_effects
from claude_benchmark.analysis.power import PowerResult, compute_power

console = Console()


def _df_to_md(df: pd.DataFrame, *, floatfmt: str = ".4f") -> str:
    """Render a DataFrame as a GitHub-flavored markdown table.

    Avoids pulling in ``tabulate`` as a hard dependency.
    """
    if df.empty:
        return "_(no rows)_\n"
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        cells = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                cells.append(format(val, floatfmt))
            elif isinstance(val, bool):
                cells.append("yes" if val else "no")
            elif val is None or (isinstance(val, float) and pd.isna(val)):
                cells.append("")
            else:
                cells.append(str(val))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _format_mixed_effects(result: MixedEffectsResult) -> str:
    buf = io.StringIO()
    buf.write(f"**Method:** {result.method}\n\n")
    buf.write(f"**Formula:** `{result.formula}`\n\n")
    buf.write(f"**Observations:** {result.n_obs}  |  **Groups:** {result.n_groups}\n\n")
    if result.fallback_reason:
        buf.write(f"_Fallback applied:_ {result.fallback_reason}\n\n")
    fe_df = result.fixed_effects_df()
    if not fe_df.empty:
        buf.write("**Fixed effects**\n\n")
        buf.write(_df_to_md(fe_df))
        buf.write("\n")
    vc_df = result.variance_components_df()
    if not vc_df.empty:
        buf.write("**Variance components**\n\n")
        buf.write(_df_to_md(vc_df))
        buf.write("\n")
    info_rows = []
    if result.log_likelihood is not None and not pd.isna(result.log_likelihood):
        info_rows.append({"metric": "log_likelihood", "value": result.log_likelihood})
    if result.aic is not None and not pd.isna(result.aic):
        info_rows.append({"metric": "AIC", "value": result.aic})
    if result.bic is not None and not pd.isna(result.bic):
        info_rows.append({"metric": "BIC", "value": result.bic})
    if info_rows:
        buf.write("**Fit diagnostics**\n\n")
        buf.write(_df_to_md(pd.DataFrame(info_rows)))
        buf.write("\n")
    return buf.getvalue()


def _format_load_stats(name: str, stats: LoadStats) -> str:
    payload = stats.as_dict()
    rows = [{"metric": k, "value": str(v)} for k, v in payload.items()]
    return f"### {name}\n\n" + _df_to_md(pd.DataFrame(rows))


def _format_bootstrap_table(rows: list[BootstrapDiffCI], *, names: list[str]) -> str:
    df = pd.DataFrame(
        [
            {
                "contrast": names[i],
                "mean_a": r.mean_a,
                "mean_b": r.mean_b,
                "diff": r.diff,
                "n_a": r.n_a,
                "n_b": r.n_b,
                "ci_pct_low": r.percentile_low,
                "ci_pct_high": r.percentile_high,
                "ci_bca_low": r.bca_low,
                "ci_bca_high": r.bca_high,
                "method": r.method,
            }
            for i, r in enumerate(rows)
        ]
    )
    return _df_to_md(df)


def _format_power_table(rows: list[PowerResult]) -> str:
    df = pd.DataFrame([r.as_dict() for r in rows])
    return _df_to_md(df)


def _summary_paragraph(
    *,
    control: str,
    me_result: MixedEffectsResult,
    corrections_df: pd.DataFrame,
    power_results: list[PowerResult],
    n_obs: int,
    n_tasks: int,
) -> str:
    sig_holm = corrections_df[corrections_df["sig_holm"]] if not corrections_df.empty else corrections_df
    n_sig_holm = int(len(sig_holm))
    n_sig_bh = int(corrections_df["sig_bh"].sum()) if not corrections_df.empty else 0
    n_total = int(len(corrections_df))

    biggest = ""
    if power_results:
        ranked = sorted(power_results, key=lambda r: abs(r.cohens_d), reverse=True)
        top = ranked[0]
        direction = "higher" if top.mean_b > top.mean_a else "lower"
        biggest = (
            f"The largest contrast was {top.group_b!r} vs {top.group_a!r} "
            f"({top.mean_b - top.mean_a:+.2f} composite, Cohen's d={top.cohens_d:.2f}, "
            f"observed power={top.achieved_power:.2f}). "
        )

    fallback = (
        f" Mixed-effects fitting fell back to {me_result.method} ({me_result.fallback_reason})."
        if me_result.fallback_reason
        else ""
    )

    plain = (
        f"Across {n_obs} runs spanning {n_tasks} tasks, {n_total} variant contrasts were "
        f"compared against control {control!r}. After Holm-Bonferroni correction "
        f"{n_sig_holm} contrasts remain significant at alpha=0.05; "
        f"Benjamini-Hochberg flags {n_sig_bh}. {biggest}"
        f"Variance attribution from the mixed model: "
    )
    vc_df = me_result.variance_components_df()
    if not vc_df.empty:
        shares = [
            f"{row['component']} {row['share']:.1%}"
            for _, row in vc_df.iterrows()
            if not pd.isna(row.get("share"))
        ]
        plain += ", ".join(shares) + "."
    plain += fallback
    return plain


def _build_corrections(
    me_result: MixedEffectsResult,
    *,
    treatments: Iterable[str] | None,
    alpha: float,
) -> tuple[dict[str, float], pd.DataFrame]:
    """Pull treatment-vs-control rows out of the fixed-effects table."""
    p_dict: dict[str, float] = {}
    treat_set = set(treatments) if treatments else None
    for fe in me_result.fixed_effects:
        # Intercept skipped.
        if fe.name == "Intercept":
            continue
        # statsmodels names: C(variant, Treatment(reference='bare'))[T.kitchen-sink]
        label = fe.name
        if "[T." in label:
            tail = label.split("[T.")[-1].rstrip("]")
        else:
            tail = label
        if treat_set is not None and tail not in treat_set:
            continue
        p_dict[tail] = fe.p_value
    return p_dict, correct_pvalues(p_dict, alpha=alpha)


def _run_single_experiment(
    results_dir: Path,
    *,
    control: str,
    treatments: list[str] | None,
    alpha: float,
    n_iter: int,
    seed: int,
    target_power: float,
) -> tuple[str, dict[str, object]]:
    df, stats = load_runs(results_dir)
    if df.empty:
        return f"# Rigor Report: {results_dir.name}\n\n_No runs loaded._\n", {}

    available_variants = sorted(df["variant"].dropna().unique().tolist())
    if control not in available_variants:
        raise ValueError(
            f"control variant {control!r} not found. Available: {available_variants}"
        )
    if treatments is None:
        treatments = [v for v in available_variants if v != control]
    else:
        missing = set(treatments) - set(available_variants)
        if missing:
            raise ValueError(
                f"treatment variant(s) not present in data: {sorted(missing)}; "
                f"available: {available_variants}"
            )

    me_result = fit_mixed_effects(df, reference_variant=control)
    p_dict, corr_df = _build_corrections(me_result, treatments=treatments, alpha=alpha)

    boot_results: list[BootstrapDiffCI] = []
    boot_names: list[str] = []
    power_results: list[PowerResult] = []
    for treatment in treatments:
        try:
            br = cluster_bootstrap_diff_ci(
                df,
                value_col="composite",
                group_col="variant",
                cluster_col="task",
                group_a=control,
                group_b=treatment,
                n_iter=n_iter,
                seed=seed,
            )
            boot_results.append(br)
            boot_names.append(f"{treatment} - {control}")
        except Exception as exc:  # noqa: BLE001
            console.print(
                f"[yellow]Bootstrap failed for {treatment} vs {control}: {exc}[/yellow]"
            )
        try:
            pr = compute_power(
                df,
                group_a=control,
                group_b=treatment,
                alpha=alpha,
                target_power=target_power,
            )
            power_results.append(pr)
        except Exception as exc:  # noqa: BLE001
            console.print(
                f"[yellow]Power calc failed for {treatment} vs {control}: {exc}[/yellow]"
            )

    n_tasks = int(df["task"].nunique())
    n_obs = int(len(df))
    summary = _summary_paragraph(
        control=control,
        me_result=me_result,
        corrections_df=corr_df,
        power_results=power_results,
        n_obs=n_obs,
        n_tasks=n_tasks,
    )

    buf = io.StringIO()
    buf.write(f"# Rigor Report: {results_dir.name}\n\n")
    buf.write(f"**Control variant:** `{control}`\n\n")
    buf.write(
        f"**Variants compared:** "
        + ", ".join(f"`{v}`" for v in treatments)
        + "\n\n"
    )
    buf.write("## Data flow\n\n")
    buf.write(_format_load_stats(results_dir.name, stats))
    buf.write("\n## Mixed-effects model\n\n")
    buf.write(_format_mixed_effects(me_result))
    buf.write("## Multiple-comparisons-corrected p-values\n\n")
    if corr_df.empty:
        buf.write("_No treatment contrasts found._\n\n")
    else:
        buf.write(_df_to_md(corr_df))
    buf.write("\n## Cluster-bootstrap CIs (resampled by task)\n\n")
    if boot_results:
        buf.write(_format_bootstrap_table(boot_results, names=boot_names))
    else:
        buf.write("_No bootstrap results._\n\n")
    buf.write("\n## Power and MDE\n\n")
    if power_results:
        buf.write(_format_power_table(power_results))
    else:
        buf.write("_No power results._\n\n")
    buf.write("\n## Plain-language summary\n\n")
    buf.write(summary + "\n")

    artifacts = {
        "load_stats": stats.as_dict(),
        "mixed_effects": {
            "fixed_effects": me_result.fixed_effects_df().to_dict(orient="records"),
            "variance_components": me_result.variance_components_df().to_dict(orient="records"),
            "method": me_result.method,
            "fallback_reason": me_result.fallback_reason,
        },
        "corrections": corr_df.to_dict(orient="records"),
        "bootstrap": [r.as_dict() for r in boot_results],
        "power": [r.as_dict() for r in power_results],
        "summary": summary,
    }
    return buf.getvalue(), artifacts


def rigor(
    results_dir: Path = typer.Argument(
        ...,
        help="Path to results directory (single experiment) or a parent directory with --all-experiments",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    control: str = typer.Option(
        "bare",
        "--control",
        help="Control variant name (must appear in the data)",
    ),
    treatment: Optional[list[str]] = typer.Option(
        None,
        "--treatment",
        help="Restrict to specific treatment variants (repeatable). Default: all non-control variants.",
    ),
    output: Path = typer.Option(
        Path("rigor-report.md"),
        "--output",
        "-o",
        help="Markdown output path",
    ),
    alpha: float = typer.Option(
        0.05,
        "--alpha",
        help="Significance threshold for corrected p-values",
    ),
    n_iter: int = typer.Option(
        2000,
        "--n-iter",
        help="Bootstrap iterations (cluster bootstrap; lower for speed)",
    ),
    seed: int = typer.Option(
        42,
        "--seed",
        help="Random seed for bootstrap",
    ),
    target_power: float = typer.Option(
        0.80,
        "--target-power",
        help="Target power for MDE calculation",
    ),
    all_experiments: bool = typer.Option(
        False,
        "--all-experiments",
        help="Treat results_dir as a parent containing experiment-* subdirs and produce one combined report.",
    ),
) -> None:
    """Publication-grade statistical analysis on benchmark runs.

    Fits a mixed-effects model (random intercept on task, with model as a
    crossed variance component when available), applies Holm-Bonferroni and
    Benjamini-Hochberg corrections, runs cluster bootstraps on the task level,
    and reports observed power and the minimum detectable effect.
    """
    treatments = list(treatment) if treatment else None
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not all_experiments:
        markdown, _artifacts = _run_single_experiment(
            results_dir,
            control=control,
            treatments=treatments,
            alpha=alpha,
            n_iter=n_iter,
            seed=seed,
            target_power=target_power,
        )
        output.write_text(markdown)
        console.print(f"[green]Wrote rigor report:[/green] {output.resolve()}")
        return

    combined_df, stats_per_exp = load_runs_multi(results_dir)
    if combined_df.empty:
        console.print("[red]No runs found under that directory.[/red]")
        raise typer.Exit(1)

    combined_df = combined_df.copy()
    combined_df["variant_label"] = combined_df["experiment"] + "::" + combined_df["variant"]

    # The control in --all-experiments mode applies to the *bare variant* part
    # in each experiment. We aggregate across experiments and pick a global
    # control by matching the unprefixed variant name.
    available = sorted(combined_df["variant"].dropna().unique().tolist())
    if control not in available:
        console.print(
            f"[red]Control variant {control!r} not present in any experiment. "
            f"Available variants: {available}[/red]"
        )
        raise typer.Exit(1)

    # Build a single dataframe restricted to runs in the chosen control or in
    # any treatment, but keep the experiment prefix so contrasts are unique.
    keep_treatments = treatments
    if keep_treatments is None:
        keep_treatments = [v for v in available if v != control]

    work = combined_df[combined_df["variant"].isin([control, *keep_treatments])].copy()
    work["variant_arm"] = work.apply(
        lambda r: control if r["variant"] == control else f"{r['experiment']}::{r['variant']}",
        axis=1,
    )

    # Re-label for the mixed-effects fit so each experiment-treatment is its
    # own arm.
    me_input = work.rename(columns={"variant": "_orig_variant"}).rename(
        columns={"variant_arm": "variant"}
    )
    me_result = fit_mixed_effects(me_input, reference_variant=control)
    p_dict, corr_df = _build_corrections(me_result, treatments=None, alpha=alpha)

    boot_results: list[BootstrapDiffCI] = []
    boot_names: list[str] = []
    power_results: list[PowerResult] = []
    for arm in sorted(me_input["variant"].dropna().unique().tolist()):
        if arm == control:
            continue
        try:
            br = cluster_bootstrap_diff_ci(
                me_input,
                value_col="composite",
                group_col="variant",
                cluster_col="task",
                group_a=control,
                group_b=arm,
                n_iter=n_iter,
                seed=seed,
            )
            boot_results.append(br)
            boot_names.append(f"{arm} - {control}")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Bootstrap failed for {arm}: {exc}[/yellow]")
        try:
            pr = compute_power(
                me_input,
                group_a=control,
                group_b=arm,
                alpha=alpha,
                target_power=target_power,
            )
            power_results.append(pr)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Power calc failed for {arm}: {exc}[/yellow]")

    n_tasks = int(me_input["task"].nunique())
    n_obs = int(len(me_input))
    summary = _summary_paragraph(
        control=control,
        me_result=me_result,
        corrections_df=corr_df,
        power_results=power_results,
        n_obs=n_obs,
        n_tasks=n_tasks,
    )

    buf = io.StringIO()
    buf.write(f"# Rigor Report: {results_dir.name} (combined, --all-experiments)\n\n")
    buf.write(f"**Control variant:** `{control}` (pooled across experiments)\n\n")
    buf.write(f"**Experiments included:** {len(stats_per_exp)}\n\n")
    buf.write("## Data flow\n\n")
    for name, stats in stats_per_exp.items():
        buf.write(_format_load_stats(name, stats))
        buf.write("\n")
    buf.write("## Mixed-effects model (experiment-prefixed variants)\n\n")
    buf.write(_format_mixed_effects(me_result))
    buf.write("## Multiple-comparisons-corrected p-values\n\n")
    if corr_df.empty:
        buf.write("_No treatment contrasts found._\n\n")
    else:
        buf.write(_df_to_md(corr_df))
    buf.write("\n## Cluster-bootstrap CIs (resampled by task)\n\n")
    if boot_results:
        buf.write(_format_bootstrap_table(boot_results, names=boot_names))
    else:
        buf.write("_No bootstrap results._\n\n")
    buf.write("\n## Power and MDE\n\n")
    if power_results:
        buf.write(_format_power_table(power_results))
    else:
        buf.write("_No power results._\n\n")
    buf.write("\n## Plain-language summary\n\n")
    buf.write(summary + "\n")

    output.write_text(buf.getvalue())
    console.print(f"[green]Wrote combined rigor report:[/green] {output.resolve()}")
