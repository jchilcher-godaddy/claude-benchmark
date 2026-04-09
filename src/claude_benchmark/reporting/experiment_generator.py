"""Experiment report generator with variant-centric comparison semantics.

Mirrors ReportGenerator structure but pivots on variants instead of profiles.
Reuses existing chart, diff, regression, and export modules.
"""

from __future__ import annotations

import json
import logging
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape
from scipy import stats

from claude_benchmark.reporting.charts import (
    DIMENSION_LABELS,
    build_grouped_bar_config,
    build_radar_config,
    build_scatter_with_frontier,
    sanitize_chart_data,
)
from claude_benchmark.reporting.generator import _build_comparison_tables
from claude_benchmark.reporting.diff_view import generate_all_diffs
from claude_benchmark.reporting.exporter import export_raw_data
from claude_benchmark.reporting.llm_summary import generate_llm_summary
from claude_benchmark.reporting.models import BenchmarkResults, _sanitize_dict
from claude_benchmark.reporting.regression import (
    bonferroni_correct,
    compute_effect_size,
    interpret_effect_size,
    post_hoc_power,
)

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> str:
    """Serialize value to JSON, replacing NaN/Inf with null."""
    return json.dumps(_sanitize_dict(value), default=str)


def _variant_label(composite_key: str) -> str:
    """Extract short variant label from composite key like 'empty:temp-0.0' -> 'temp-0.0'."""
    if ":" in composite_key:
        return composite_key.rsplit(":", 1)[1]
    return composite_key


def _json_script_safe(value: str) -> str:
    """Escape a JSON string for safe embedding inside HTML <script> tags."""
    return value.replace("</", "<\\/").replace("<!--", "<\\!--")


class ExperimentReportGenerator:
    """Generate self-contained HTML report for experiment results.

    Variant-centric: variants are the primary comparison axis,
    unlike ReportGenerator which pivots on profiles.
    """

    def __init__(self, results_dir: Path, manifest: dict | None = None) -> None:
        self.results_dir = Path(results_dir)
        self.manifest = manifest or {}
        self.env = Environment(
            loader=PackageLoader("claude_benchmark", "templates"),
            autoescape=select_autoescape(["html", "html.j2"]),
        )
        self.env.filters["tojson_safe"] = _json_safe
        self.env.filters["variant_label"] = _variant_label

    def generate(
        self,
        output_path: Path,
        results: BenchmarkResults,
        control_variant: str | None = None,
        csv_content: str | None = None,
        task_descriptions: dict[str, str] | None = None,
        llm_summary: bool = True,
    ) -> Path:
        """Generate the experiment HTML report.

        Args:
            output_path: Where to write the HTML file.
            results: Loaded BenchmarkResults (with composite profile:variant keys).
            control_variant: Label of the control variant. Defaults to first variant.
            csv_content: Pre-loaded CSV for inline download.
            task_descriptions: Task name -> description mapping.
            llm_summary: Whether to generate LLM narrative.

        Returns:
            The output_path.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use composite profile keys (e.g. "empty:temp-0.0") as variant identifiers
        # since those are the actual keys in results.profiles.
        variants = sorted(results.profiles.keys())

        # Build a mapping from short variant names (manifest) to composite keys
        short_to_composite = self._build_short_variant_map(variants)

        # Determine control variant (manifest uses short names like "temp-0.0")
        manifest_variants = self.manifest.get("variants", [])
        if control_variant is None:
            if manifest_variants:
                control_variant = short_to_composite.get(
                    manifest_variants[0], manifest_variants[0],
                )
            elif variants:
                control_variant = variants[0]
        elif control_variant in short_to_composite:
            control_variant = short_to_composite[control_variant]

        # Extract experiment metadata from manifest
        experiment_name = self.manifest.get("experiment_name", "Experiment")
        experiment_desc = self.manifest.get("description", "")
        variant_configs = self._extract_variant_configs(short_to_composite)

        # Extract chart data (reuse profile-keyed data — variants ARE the profile keys)
        dimensions = self._get_dimensions(results)
        tasks = results.tasks
        models = results.models

        scores_by_model = self._extract_scores_by_model(results, dimensions)
        scores_by_dimension = self._extract_scores_by_dimension(results, dimensions)
        token_counts = self._extract_token_counts(results)
        quality_scores = self._extract_quality_scores(results)

        # Build chart configs — pass variants where profiles are expected
        chart_configs: dict[str, dict] = {}
        for model in models:
            model_scores = scores_by_model.get(model, {})
            chart_configs[f"radar-{model}"] = build_radar_config(
                model_name=model,
                profiles=variants,
                dimensions=dimensions,
                scores=model_scores,
            )

        for dim in dimensions:
            dim_scores = scores_by_dimension.get(dim, {})
            chart_configs[f"bar-{dim}"] = build_grouped_bar_config(
                dimension=dim,
                profiles=variants,
                tasks=tasks,
                scores=dim_scores,
            )

        chart_configs["scatter-efficiency"] = build_scatter_with_frontier(
            profiles=variants,
            token_counts=token_counts,
            quality_scores=quality_scores,
        )

        # Statistical comparison table: control vs each treatment
        stat_table = self._build_variant_comparison_table(
            results, variants, control_variant, dimensions,
        )

        # Variant x Task heatmap
        heatmap = self._build_task_variant_heatmap(results, variants, tasks)

        # Code diffs: control vs each treatment
        comparison_data = self._extract_comparison_data(results)
        diffs = generate_all_diffs(comparison_data)

        # CSV content
        if csv_content is None:
            _json_path, csv_path = export_raw_data(results, output_path.parent)
            csv_content = csv_path.read_text(encoding="utf-8") if csv_path.exists() else ""

        # Read vendored Chart.js
        chartjs_path = Path(__file__).parent.parent / "assets" / "chart.min.js"
        chartjs_source = chartjs_path.read_text(encoding="utf-8")

        # Executive summary data
        summary = self._build_experiment_summary_data(
            results, variants, control_variant, quality_scores, token_counts,
        )

        # Insights
        insights = self._generate_experiment_insights(
            results, variants, control_variant, quality_scores, token_counts, stat_table,
        )

        # LLM narrative (optional)
        llm_summary_text = None
        if llm_summary:
            llm_summary_text = self._generate_llm_narrative(
                results, variants, quality_scores, token_counts, insights, summary,
            )

        # Compute run health for failure banner
        run_health = self._compute_run_health(results)

        # Build per-model comparison tables for radar chart data tables
        comparison_tables = _build_comparison_tables(
            models, dimensions, scores_by_model,
        )

        # Render template
        template = self.env.get_template("experiment_report.html.j2")
        html = template.render(
            run_health=run_health,
            experiment_name=experiment_name,
            experiment_desc=experiment_desc,
            metadata=results.metadata,
            variants=variants,
            variant_configs=variant_configs,
            control_variant=control_variant,
            models=models,
            tasks=tasks,
            dimensions=dimensions,
            dim_labels=DIMENSION_LABELS,
            summary=summary,
            insights=insights,
            llm_summary_text=llm_summary_text,
            stat_table=stat_table,
            heatmap=heatmap,
            diffs=diffs,
            chartjs_source=chartjs_source,
            chart_configs_json=_json_script_safe(json.dumps(
                {k: sanitize_chart_data(v) for k, v in chart_configs.items()},
                default=str,
            )),
            benchmark_data_json=_json_script_safe(json.dumps(
                _sanitize_dict(results.to_export_dict()), default=str,
            )),
            raw_csv=csv_content,
            task_descriptions=task_descriptions or {},
            comparison_tables=comparison_tables,
            scores_by_dimension=scores_by_dimension,
        )

        output_path.write_text(html, encoding="utf-8")
        return output_path

    def _compute_run_health(self, results: BenchmarkResults) -> dict[str, Any]:
        """Compute run health metrics for the failure banner."""
        total = 0
        failed = 0
        errors: dict[str, int] = defaultdict(int)
        for pr in results.profiles.values():
            for tr in pr.tasks.values():
                for run in tr.runs:
                    total += 1
                    if not run.success:
                        failed += 1
                        if run.error:
                            errors[run.error] += 1
        common = sorted(errors.items(), key=lambda x: -x[1])[:3]
        return {
            "total_runs": total,
            "failed_runs": failed,
            "failure_rate": failed / total if total else 0,
            "common_errors": common,
        }

    def _build_short_variant_map(
        self, composite_keys: list[str],
    ) -> dict[str, str]:
        """Map short variant names to composite profile keys.

        E.g. {"temp-0.0": "empty:temp-0.0", "temp-0.3": "empty:temp-0.3"}.
        """
        short_map: dict[str, str] = {}
        for key in composite_keys:
            if ":" in key:
                _base, variant = key.rsplit(":", 1)
                short_map[variant] = key
            else:
                short_map[key] = key
        return short_map

    def _extract_variant_configs(
        self, short_to_composite: dict[str, str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Extract variant configuration details from manifest for display.

        Keys are composite profile keys (matching results.profiles) so the
        template can look them up consistently.
        """
        configs: dict[str, dict[str, Any]] = {}
        short_to_composite = short_to_composite or {}
        for label in self.manifest.get("variants", []):
            composite_key = short_to_composite.get(label, label)
            configs[composite_key] = {"label": label}
        return configs

    def _get_dimensions(self, results: BenchmarkResults) -> list[str]:
        dims: set[str] = set()
        for profile in results.profiles.values():
            for task_result in profile.tasks.values():
                for run in task_result.runs:
                    dims.update(run.scores.keys())
        return sorted(dims)

    def _extract_scores_by_model(
        self, results: BenchmarkResults, dimensions: list[str],
    ) -> dict[str, dict[str, list[float]]]:
        """Extract {model: {profile_key: [avg_score_per_dim]}}."""
        scores_by_model: dict[str, dict[str, list[float]]] = {}
        for model in results.models:
            scores_by_model[model] = {}
            for profile_id, profile_result in results.profiles.items():
                dim_avgs: list[float] = []
                for dim in dimensions:
                    scores_for_dim: list[float] = []
                    for task_result in profile_result.tasks.values():
                        for run in task_result.runs:
                            if run.model == model and dim in run.scores:
                                scores_for_dim.append(run.scores[dim])
                    dim_avgs.append(
                        sum(scores_for_dim) / len(scores_for_dim) if scores_for_dim else 0.0
                    )
                scores_by_model[model][profile_id] = dim_avgs
        return scores_by_model

    def _extract_scores_by_dimension(
        self, results: BenchmarkResults, dimensions: list[str],
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Extract {dim: {profile_key: {task: avg_score}}}."""
        scores_by_dim: dict[str, dict[str, dict[str, float]]] = {}
        for dim in dimensions:
            scores_by_dim[dim] = {}
            for profile_id, profile_result in results.profiles.items():
                task_scores: dict[str, float] = {}
                for task_id, task_result in profile_result.tasks.items():
                    dim_scores = [
                        run.scores[dim]
                        for run in task_result.runs
                        if dim in run.scores
                    ]
                    if dim_scores:
                        task_scores[task_id] = sum(dim_scores) / len(dim_scores)
                scores_by_dim[dim][profile_id] = task_scores
        return scores_by_dim

    def _extract_token_counts(
        self, results: BenchmarkResults,
    ) -> dict[str, float]:
        return {
            pid: float(pr.total_tokens)
            for pid, pr in results.profiles.items()
        }

    @staticmethod
    def _composite_score(scores: dict[str, float]) -> float | None:
        """Extract composite score from a run's score dict.

        Prefers the explicit ``composite`` key when present, otherwise
        averages all dimensions.  Returns ``None`` when no usable score
        can be derived.
        """
        if not scores:
            return None
        if "composite" in scores:
            val = scores["composite"]
            return val if not math.isnan(val) else None
        avg = sum(scores.values()) / len(scores)
        return avg if not math.isnan(avg) else None

    def _extract_quality_scores(
        self, results: BenchmarkResults,
    ) -> dict[str, float]:
        quality: dict[str, float] = {}
        for pid, pr in results.profiles.items():
            composites: list[float] = []
            for tr in pr.tasks.values():
                for run in tr.runs:
                    c = self._composite_score(run.scores)
                    if c is not None:
                        composites.append(c)
            quality[pid] = sum(composites) / len(composites) if composites else 0.0
        return quality

    def _build_variant_comparison_table(
        self,
        results: BenchmarkResults,
        variants: list[str],
        control_variant: str | None,
        dimensions: list[str],
    ) -> list[dict[str, Any]]:
        """Build statistical comparison table: each variant vs control.

        Returns list of dicts with: variant, mean, control_mean, delta,
        delta_pct, p_value, effect_size, is_significant.
        """
        if not control_variant or control_variant not in results.profiles:
            return []

        control_profile = results.profiles[control_variant]
        table: list[dict[str, Any]] = []

        for variant in variants:
            if variant == control_variant:
                continue
            if variant not in results.profiles:
                continue

            variant_profile = results.profiles[variant]

            # Collect composite scores across all tasks
            control_composites: list[float] = []
            variant_composites: list[float] = []

            for task_id in results.tasks:
                if task_id in control_profile.tasks:
                    for run in control_profile.tasks[task_id].runs:
                        c = self._composite_score(run.scores)
                        if c is not None:
                            control_composites.append(c)

                if task_id in variant_profile.tasks:
                    for run in variant_profile.tasks[task_id].runs:
                        c = self._composite_score(run.scores)
                        if c is not None:
                            variant_composites.append(c)

            if len(control_composites) < 2 or len(variant_composites) < 2:
                table.append({
                    "variant": variant,
                    "mean": sum(variant_composites) / len(variant_composites) if variant_composites else 0.0,
                    "control_mean": sum(control_composites) / len(control_composites) if control_composites else 0.0,
                    "delta": 0.0,
                    "delta_pct": 0.0,
                    "p_value": 1.0,
                    "effect_size": 0.0,
                    "is_significant": False,
                    "n_control": len(control_composites),
                    "n_variant": len(variant_composites),
                    "cv_pct": 0.0,
                    "adjusted_p_value": 1.0,
                    "effect_interpretation": "negligible",
                    "power": 0.0,
                    "is_significant_adjusted": False,
                })
                continue

            control_mean = sum(control_composites) / len(control_composites)
            variant_mean = sum(variant_composites) / len(variant_composites)
            delta = variant_mean - control_mean
            delta_pct = delta / control_mean if control_mean != 0 else 0.0

            # Two-sided Mann-Whitney U test
            try:
                stat_result = stats.mannwhitneyu(
                    control_composites, variant_composites,
                    alternative="two-sided",
                )
                p_value = float(stat_result.pvalue)
            except ValueError:
                stat_result = stats.ttest_ind(
                    control_composites, variant_composites,
                    equal_var=False, alternative="two-sided",
                )
                p_value = float(stat_result.pvalue)

            effect = compute_effect_size(control_composites, variant_composites)

            # Coefficient of variation for this variant
            variant_stdev = statistics.stdev(variant_composites) if len(variant_composites) > 1 else 0.0
            variant_cv = (variant_stdev / variant_mean * 100) if variant_mean != 0 else 0.0

            table.append({
                "variant": variant,
                "mean": round(variant_mean, 2),
                "control_mean": round(control_mean, 2),
                "delta": round(delta, 2),
                "delta_pct": round(delta_pct, 4),
                "p_value": round(p_value, 4),
                "effect_size": round(effect, 3),
                "effect_interpretation": interpret_effect_size(effect),
                "is_significant": p_value < 0.05,
                "n_control": len(control_composites),
                "n_variant": len(variant_composites),
                "cv_pct": round(variant_cv, 1),
                "power": round(
                    post_hoc_power(effect, len(control_composites), len(variant_composites)),
                    2,
                ),
            })

        # Apply Bonferroni correction across all comparisons
        if table:
            raw_pvals = [row["p_value"] for row in table]
            adjusted = bonferroni_correct(raw_pvals)
            for row, adj_p in zip(table, adjusted):
                row["adjusted_p_value"] = round(adj_p, 4)
                row["is_significant_adjusted"] = adj_p < 0.05

        return table

    def _build_task_variant_heatmap(
        self,
        results: BenchmarkResults,
        variants: list[str],
        tasks: list[str],
    ) -> list[dict[str, Any]]:
        """Build variant x task composite score matrix for heatmap.

        Returns list of {task, scores: {variant: score}} dicts.
        """
        heatmap: list[dict[str, Any]] = []
        for task_id in tasks:
            row: dict[str, float] = {}
            for variant in variants:
                if variant not in results.profiles:
                    row[variant] = 0.0
                    continue
                profile = results.profiles[variant]
                if task_id not in profile.tasks:
                    row[variant] = 0.0
                    continue
                task_result = profile.tasks[task_id]
                composites: list[float] = []
                for run in task_result.runs:
                    c = self._composite_score(run.scores)
                    if c is not None:
                        composites.append(c)
                row[variant] = round(
                    sum(composites) / len(composites), 1,
                ) if composites else 0.0
            heatmap.append({"task": task_id, "scores": row})
        return heatmap

    def _extract_comparison_data(
        self, results: BenchmarkResults,
    ) -> dict[str, dict[str, str]]:
        """Build comparison data for diff generation between variants."""
        comparison: dict[str, dict[str, str]] = {}
        for model in results.models:
            for task in results.tasks:
                key = f"{model}/{task}"
                comparison[key] = {}
                for profile_id, profile_result in results.profiles.items():
                    if task not in profile_result.tasks:
                        continue
                    task_result = profile_result.tasks[task]
                    runs = [r for r in task_result.runs if r.model == model]
                    if not runs:
                        runs = list(task_result.runs)
                    if not runs:
                        continue
                    best = max(
                        runs,
                        key=lambda r: (
                            sum(r.scores.values()) / len(r.scores) if r.scores else 0
                        ),
                    )
                    if best.code_output:
                        comparison[key][profile_id] = best.code_output
        return comparison

    def _build_experiment_summary_data(
        self,
        results: BenchmarkResults,
        variants: list[str],
        control_variant: str | None,
        quality_scores: dict[str, float],
        token_counts: dict[str, float],
    ) -> dict[str, Any]:
        """Build executive summary card data."""
        best_variant = max(
            variants, key=lambda v: quality_scores.get(v, 0.0),
        ) if variants else "N/A"
        best_score = quality_scores.get(best_variant, 0.0)

        control_score = quality_scores.get(control_variant, 0.0) if control_variant else 0.0
        improvement = best_score - control_score

        # Token efficiency winner
        efficiency_winner = "N/A"
        best_ratio = -1.0
        for v in variants:
            tokens = token_counts.get(v, 0)
            quality = quality_scores.get(v, 0)
            if tokens > 0 and quality > 0:
                ratio = quality / tokens
                if ratio > best_ratio:
                    best_ratio = ratio
                    efficiency_winner = v

        return {
            "best_variant": best_variant,
            "best_score": round(best_score, 1),
            "control_variant": control_variant or "N/A",
            "control_score": round(control_score, 1),
            "improvement_delta": round(improvement, 1),
            "improvement_pct": round(
                improvement / control_score * 100, 1,
            ) if control_score > 0 else 0.0,
            "efficiency_winner": efficiency_winner,
            "variant_count": len(variants),
            "task_count": len(results.tasks),
            "total_runs": results.metadata.total_runs,
        }

    def _generate_experiment_insights(
        self,
        results: BenchmarkResults,
        variants: list[str],
        control_variant: str | None,
        quality_scores: dict[str, float],
        token_counts: dict[str, float],
        stat_table: list[dict[str, Any]],
    ) -> list[str]:
        """Generate plain-English insights about experiment results."""
        insights: list[str] = []

        if not variants:
            return insights

        # Best and worst variant
        sorted_variants = sorted(
            variants, key=lambda v: quality_scores.get(v, 0.0), reverse=True,
        )
        best = sorted_variants[0]
        worst = sorted_variants[-1]
        best_score = quality_scores.get(best, 0.0)
        worst_score = quality_scores.get(worst, 0.0)

        if best_score > 0:
            insights.append(
                f"Best performing variant: {_variant_label(best)} with average composite score {best_score:.1f}"
            )

        if len(sorted_variants) > 1 and best_score - worst_score > 1.0:
            insights.append(
                f"Score spread across variants: {best_score - worst_score:.1f} points "
                f"({_variant_label(best)} vs {_variant_label(worst)})"
            )

        # Significant results from stat table
        significant = [r for r in stat_table if r["is_significant"]]
        if significant:
            for row in significant:
                direction = "higher" if row["delta"] > 0 else "lower"
                insights.append(
                    f"{_variant_label(row['variant'])} scored {abs(row['delta']):.1f} points {direction} "
                    f"than control (p={row['p_value']:.3f}, d={row['effect_size']:.2f})"
                )
        elif stat_table:
            insights.append(
                "No statistically significant differences found between variants (p > 0.05)"
            )

            # Check for underpowered comparisons
            underpowered = [
                r for r in stat_table
                if not r.get("is_significant", False) and r.get("power", 0) < 0.80
            ]
            if underpowered:
                insights.append(
                    f"Note: {len(underpowered)} of {len(stat_table)} comparisons had statistical power < 80%, "
                    f"meaning small-to-medium effects may have gone undetected. "
                    f"Consider increasing repetitions beyond 30 for more definitive null results."
                )

        # Token efficiency
        tokens_sorted = sorted(
            [(v, token_counts.get(v, 0)) for v in variants],
            key=lambda x: x[1],
        )
        if len(tokens_sorted) >= 2:
            cheapest, cheapest_tokens = tokens_sorted[0]
            most_expensive, exp_tokens = tokens_sorted[-1]
            if cheapest_tokens > 0 and exp_tokens > 0:
                ratio = exp_tokens / cheapest_tokens
                if ratio > 1.1:
                    insights.append(
                        f"Token usage varies {ratio:.1f}x across variants "
                        f"({_variant_label(cheapest)}: {cheapest_tokens:,.0f} vs {_variant_label(most_expensive)}: {exp_tokens:,.0f})"
                    )

        return insights

    def _generate_llm_narrative(
        self,
        results: BenchmarkResults,
        variants: list[str],
        quality_scores: dict[str, float],
        token_counts: dict[str, float],
        insights: list[str],
        summary: dict[str, Any],
    ) -> str | None:
        """Generate LLM narrative summary for experiment results."""
        try:
            return generate_llm_summary(
                quality_scores=quality_scores,
                best_combo_model=results.models[0] if results.models else "N/A",
                best_combo_profile=summary["best_variant"],
                best_combo_score=summary["best_score"],
                best_profile_overall=summary["best_variant"],
                best_profile_score=summary["best_score"],
                tw_model=results.models[0] if results.models else "N/A",
                tw_profile=summary["efficiency_winner"],
                tw_score=quality_scores.get(summary["efficiency_winner"], 0.0),
                category_analysis=[],
                model_preferences=[],
                insights=insights,
                regressions_list=[],
                token_counts={k: int(v) for k, v in token_counts.items()},
                profiles=variants,
                tasks=results.tasks,
                models=results.models,
            )
        except Exception:
            logger.warning("LLM narrative generation failed", exc_info=True)
            return None

    def print_cli_summary(self, stat_table: list[dict[str, Any]]) -> None:
        """Print a CLI summary of experiment comparison results."""
        from rich.console import Console
        console = Console()

        if not stat_table:
            console.print("[dim]No statistical comparisons available.[/dim]")
            return

        significant = [r for r in stat_table if r["is_significant"]]
        if significant:
            console.print(f"\n[bold yellow]Significant results ({len(significant)}):[/bold yellow]")
            for row in significant:
                direction = "+" if row["delta"] > 0 else ""
                console.print(
                    f"  {row['variant']}: {direction}{row['delta']:.1f} "
                    f"(p={row['p_value']:.3f}, d={row['effect_size']:.2f})"
                )
        else:
            console.print("\n[green]No significant differences between variants.[/green]")
