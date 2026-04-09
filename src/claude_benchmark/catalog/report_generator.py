"""Comparison report generator for cross-run benchmark comparisons.

Generates self-contained HTML reports comparing results across multiple catalog entries.
Follows the ExperimentReportGenerator pattern for consistency.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from claude_benchmark.reporting.charts import (
    DIMENSION_LABELS,
    build_grouped_bar_config,
    build_radar_config,
    sanitize_chart_data,
)
from claude_benchmark.reporting.llm_summary import generate_llm_summary
from claude_benchmark.reporting.models import BenchmarkResults, _sanitize_dict

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> str:
    """Serialize value to JSON, replacing NaN/Inf with null."""
    return json.dumps(_sanitize_dict(value), default=str)


def _json_script_safe(value: str) -> str:
    """Escape a JSON string for safe embedding inside HTML <script> tags."""
    return value.replace("</", "<\\/").replace("<!--", "<\\!--")


class ComparisonReportGenerator:
    """Generate self-contained HTML report comparing results across catalog entries."""

    def __init__(self, entries: list, comparisons: list, comparison_report) -> None:
        """Initialize the comparison report generator.

        Args:
            entries: List of CatalogEntry objects
            comparisons: List of PairwiseComparison objects
            comparison_report: ComparisonReport object
        """
        self.entries = entries
        self.comparisons = comparisons
        self.comparison_report = comparison_report
        self.env = Environment(
            loader=PackageLoader("claude_benchmark", "templates"),
            autoescape=select_autoescape(["html", "html.j2"]),
        )
        self.env.filters["tojson_safe"] = _json_safe

    def generate(
        self,
        output_path: Path,
        results_by_entry: dict[str, BenchmarkResults],
        llm_summary: bool = False,
    ) -> Path:
        """Generate HTML comparison report.

        Args:
            output_path: Where to write HTML
            results_by_entry: Dict mapping run_id to loaded BenchmarkResults
            llm_summary: Whether to include LLM narrative (default False)

        Returns:
            The output_path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build entry summaries
        entry_summaries = []
        for entry in self.entries:
            summary = {
                "run_id": entry.run_id,
                "name": entry.name,
                "timestamp": entry.timestamp,
                "tags": entry.tags if hasattr(entry, "tags") else [],
                "models": entry.models if hasattr(entry, "models") else [],
                "profiles": entry.profiles if hasattr(entry, "profiles") else [],
                "tasks": entry.tasks if hasattr(entry, "tasks") else [],
                "total_runs": entry.total_runs if hasattr(entry, "total_runs") else 0,
            }
            entry_summaries.append(summary)

        # Calculate overlap and unique counts
        overlap_count = self._calculate_overlap_count(results_by_entry)
        unique_counts = self._calculate_unique_counts(results_by_entry)

        # Build comparison table for display
        comparison_table = []
        for comp in self.comparisons:
            # Format delta percentage
            delta_pct_formatted = f"{comp.delta_pct * 100:+.1f}%"

            # Significance badge
            if comp.is_significant:
                significance_badge = '<span style="color:#16a34a;font-weight:700">&#10003;</span>'
            else:
                significance_badge = '<span style="color:#94a3b8">&ndash;</span>'

            comparison_table.append({
                "key": f"{comp.key_model}/{comp.key_profile}/{comp.key_task}",
                "dimension": comp.dimension,
                "run_a_name": comp.run_a_name,
                "run_a_mean": round(comp.run_a_mean, 2),
                "run_b_name": comp.run_b_name,
                "run_b_mean": round(comp.run_b_mean, 2),
                "delta_pct": delta_pct_formatted,
                "p_value": round(comp.p_value, 4),
                "effect_label": comp.effect_label,
                "is_significant": comp.is_significant,
                "significance_badge": significance_badge,
            })

        # Group comparisons by dimension
        grouped_comparisons = self._group_comparisons_by_dimension(self.comparisons)

        # Build chart configs
        chart_configs = self._build_chart_configs(
            results_by_entry,
            grouped_comparisons,
        )

        # Executive summary and insights
        quality_by_entry = self._compute_quality_by_entry(results_by_entry)
        token_by_entry = self._compute_token_by_entry(results_by_entry)
        summary = self._build_summary_data(quality_by_entry, token_by_entry)
        insights = self._generate_insights(quality_by_entry, token_by_entry)

        # LLM narrative
        llm_summary_text = None
        if llm_summary:
            llm_summary_text = self._generate_llm_narrative(
                results_by_entry, quality_by_entry, token_by_entry, insights, summary,
            )

        # Read vendored Chart.js
        chartjs_path = Path(__file__).parent.parent / "assets" / "chart.min.js"
        chartjs_source = chartjs_path.read_text(encoding="utf-8")

        # Render template
        template = self.env.get_template("comparison_report.html.j2")
        html = template.render(
            generated_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            entry_summaries=entry_summaries,
            overlap_count=overlap_count,
            unique_counts=unique_counts,
            comparison_table=comparison_table,
            grouped_comparisons=grouped_comparisons,
            summary=summary,
            insights=insights,
            llm_summary_text=llm_summary_text,
            chartjs_source=chartjs_source,
            chart_configs_json=_json_script_safe(json.dumps(
                {k: sanitize_chart_data(v) for k, v in chart_configs.items()},
                default=str,
            )),
            dim_labels=DIMENSION_LABELS,
        )

        output_path.write_text(html, encoding="utf-8")
        logger.info(f"Comparison report written to {output_path}")
        return output_path

    def _compute_quality_by_entry(
        self,
        results_by_entry: dict[str, BenchmarkResults],
    ) -> dict[str, float]:
        """Compute average composite quality score per entry."""
        quality: dict[str, float] = {}
        for run_id, results in results_by_entry.items():
            entry_name = next(
                (e.name for e in self.entries if e.run_id == run_id), run_id,
            )
            all_scores: list[float] = []
            for profile_result in results.profiles.values():
                for task_result in profile_result.tasks.values():
                    for run in task_result.runs:
                        if run.scores:
                            if "composite" in run.scores:
                                all_scores.append(run.scores["composite"])
                            else:
                                all_scores.append(
                                    sum(run.scores.values()) / len(run.scores)
                                )
            quality[entry_name] = (
                sum(all_scores) / len(all_scores) if all_scores else 0.0
            )
        return quality

    def _compute_token_by_entry(
        self,
        results_by_entry: dict[str, BenchmarkResults],
    ) -> dict[str, float]:
        """Compute total tokens per entry."""
        tokens: dict[str, float] = {}
        for run_id, results in results_by_entry.items():
            entry_name = next(
                (e.name for e in self.entries if e.run_id == run_id), run_id,
            )
            total = sum(
                float(pr.total_tokens) for pr in results.profiles.values()
            )
            tokens[entry_name] = total
        return tokens

    def _build_summary_data(
        self,
        quality_by_entry: dict[str, float],
        token_by_entry: dict[str, float],
    ) -> dict[str, Any]:
        """Build executive summary card data."""
        if not quality_by_entry:
            return {
                "best_run": "N/A", "best_score": 0.0,
                "worst_run": "N/A", "worst_score": 0.0,
                "spread": 0.0, "efficiency_winner": "N/A",
                "run_count": 0,
            }

        sorted_entries = sorted(
            quality_by_entry.items(), key=lambda x: x[1], reverse=True,
        )
        best_name, best_score = sorted_entries[0]
        worst_name, worst_score = sorted_entries[-1]

        # Token efficiency winner (best quality/token ratio)
        efficiency_winner = "N/A"
        best_ratio = -1.0
        for name in quality_by_entry:
            tokens = token_by_entry.get(name, 0)
            quality = quality_by_entry.get(name, 0)
            if tokens > 0 and quality > 0:
                ratio = quality / tokens
                if ratio > best_ratio:
                    best_ratio = ratio
                    efficiency_winner = name

        return {
            "best_run": best_name,
            "best_score": round(best_score, 1),
            "worst_run": worst_name,
            "worst_score": round(worst_score, 1),
            "spread": round(best_score - worst_score, 1),
            "efficiency_winner": efficiency_winner,
            "run_count": len(quality_by_entry),
        }

    def _generate_insights(
        self,
        quality_by_entry: dict[str, float],
        token_by_entry: dict[str, float],
    ) -> list[str]:
        """Generate plain-English insights about comparison results."""
        insights: list[str] = []
        if not quality_by_entry:
            return insights

        sorted_entries = sorted(
            quality_by_entry.items(), key=lambda x: x[1], reverse=True,
        )
        best_name, best_score = sorted_entries[0]
        worst_name, worst_score = sorted_entries[-1]

        insights.append(
            f"Best performing run: {best_name} with average composite score {best_score:.1f}"
        )

        if len(sorted_entries) > 1 and best_score - worst_score > 0.5:
            insights.append(
                f"Score spread across runs: {best_score - worst_score:.1f} points "
                f"({best_name} vs {worst_name})"
            )

        # Significant comparisons
        significant = [c for c in self.comparisons if c.is_significant]
        if significant:
            # Group by dimension and summarize
            by_dim: dict[str, list] = {}
            for c in significant:
                by_dim.setdefault(c.dimension, []).append(c)
            for dim, comps in by_dim.items():
                dim_label = DIMENSION_LABELS.get(dim, dim.replace("_", " ").title())
                insights.append(
                    f"{len(comps)} significant difference{'s' if len(comps) != 1 else ''} "
                    f"found in {dim_label}"
                )
        else:
            insights.append(
                "No statistically significant differences found between runs (p > 0.05)"
            )

        # Token efficiency
        if len(token_by_entry) >= 2:
            tokens_sorted = sorted(token_by_entry.items(), key=lambda x: x[1])
            cheapest_name, cheapest_tokens = tokens_sorted[0]
            expensive_name, exp_tokens = tokens_sorted[-1]
            if cheapest_tokens > 0 and exp_tokens > 0:
                ratio = exp_tokens / cheapest_tokens
                if ratio > 1.1:
                    insights.append(
                        f"Token usage varies {ratio:.1f}x across runs "
                        f"({cheapest_name}: {cheapest_tokens:,.0f} vs {expensive_name}: {exp_tokens:,.0f})"
                    )

        return insights

    def _generate_llm_narrative(
        self,
        results_by_entry: dict[str, BenchmarkResults],
        quality_by_entry: dict[str, float],
        token_by_entry: dict[str, float],
        insights: list[str],
        summary: dict[str, Any],
    ) -> str | None:
        """Generate LLM narrative summary for comparison results."""
        try:
            entry_names = list(quality_by_entry.keys())
            all_models: set[str] = set()
            all_tasks: set[str] = set()
            for results in results_by_entry.values():
                all_models.update(results.models)
                all_tasks.update(results.tasks)

            return generate_llm_summary(
                quality_scores=quality_by_entry,
                best_combo_model=next(iter(all_models), "N/A"),
                best_combo_profile=summary["best_run"],
                best_combo_score=summary["best_score"],
                best_profile_overall=summary["best_run"],
                best_profile_score=summary["best_score"],
                tw_model=next(iter(all_models), "N/A"),
                tw_profile=summary["efficiency_winner"],
                tw_score=quality_by_entry.get(summary["efficiency_winner"], 0.0),
                category_analysis=[],
                model_preferences=[],
                insights=insights,
                regressions_list=[],
                token_counts={k: int(v) for k, v in token_by_entry.items()},
                profiles=entry_names,
                tasks=sorted(all_tasks),
                models=sorted(all_models),
            )
        except Exception:
            logger.warning("LLM narrative generation failed", exc_info=True)
            return None

    def _calculate_overlap_count(
        self,
        results_by_entry: dict[str, BenchmarkResults],
    ) -> int:
        """Calculate number of overlapping (model, profile, task) combinations."""
        if len(results_by_entry) < 2:
            return 0

        # Build sets of (model, profile, task) tuples for each entry
        combination_sets = []
        for results in results_by_entry.values():
            combos = set()
            for profile_id, profile_result in results.profiles.items():
                for task_id in profile_result.tasks:
                    for model in results.models:
                        combos.add((model, profile_id, task_id))
            combination_sets.append(combos)

        # Find intersection across all sets
        overlap = set.intersection(*combination_sets)
        return len(overlap)

    def _calculate_unique_counts(
        self,
        results_by_entry: dict[str, BenchmarkResults],
    ) -> dict[str, int]:
        """Calculate unique combinations per entry (not in any other entry)."""
        unique_counts = {}

        # Build sets for each entry
        entry_combos = {}
        for run_id, results in results_by_entry.items():
            combos = set()
            for profile_id, profile_result in results.profiles.items():
                for task_id in profile_result.tasks:
                    for model in results.models:
                        combos.add((model, profile_id, task_id))
            entry_combos[run_id] = combos

        # Find unique for each entry
        for run_id, combos in entry_combos.items():
            # Get all other entry combos
            other_combos = set()
            for other_run_id, other_combos_set in entry_combos.items():
                if other_run_id != run_id:
                    other_combos.update(other_combos_set)
            # Unique = in this entry but not in any other
            unique = combos - other_combos
            unique_counts[run_id] = len(unique)

        return unique_counts

    def _group_comparisons_by_dimension(
        self,
        comparisons: list,
    ) -> dict[str, list]:
        """Group comparisons by dimension for display."""
        grouped = {}
        for comp in comparisons:
            dim = comp.dimension
            if dim not in grouped:
                grouped[dim] = []
            grouped[dim].append(comp)
        return grouped

    def _build_chart_configs(
        self,
        results_by_entry: dict[str, BenchmarkResults],
        grouped_comparisons: dict[str, list],
    ) -> dict[str, dict]:
        """Build Chart.js configs for comparison visualization.

        Creates:
        - Grouped bar charts per dimension (side-by-side run comparison)
        - Radar chart showing aggregate dimension scores per run
        """
        chart_configs = {}

        # Extract entry names/IDs for chart series
        entry_ids = list(results_by_entry.keys())
        entry_names = [
            next((e.name for e in self.entries if e.run_id == rid), rid)
            for rid in entry_ids
        ]

        # Get all dimensions from results
        dimensions = set()
        for results in results_by_entry.values():
            for profile_result in results.profiles.values():
                for task_result in profile_result.tasks.values():
                    for run in task_result.runs:
                        dimensions.update(run.scores.keys())
        dimensions = sorted(dimensions)

        # Get all tasks from results
        tasks = set()
        for results in results_by_entry.values():
            tasks.update(results.tasks)
        tasks = sorted(tasks)

        # Build grouped bar charts per dimension
        for dim in dimensions:
            # Extract scores: {entry_name: {task: avg_score}}
            scores_by_entry = {}
            for entry_id, results in results_by_entry.items():
                entry_name = next(
                    (e.name for e in self.entries if e.run_id == entry_id),
                    entry_id,
                )
                task_scores = {}
                for task_id in tasks:
                    dim_scores = []
                    for profile_result in results.profiles.values():
                        if task_id in profile_result.tasks:
                            task_result = profile_result.tasks[task_id]
                            for run in task_result.runs:
                                if dim in run.scores:
                                    dim_scores.append(run.scores[dim])
                    if dim_scores:
                        task_scores[task_id] = sum(dim_scores) / len(dim_scores)
                scores_by_entry[entry_name] = task_scores

            chart_configs[f"bar-{dim}"] = build_grouped_bar_config(
                dimension=dim,
                profiles=entry_names,
                tasks=tasks,
                scores=scores_by_entry,
            )

        # Build radar chart: aggregate dimension scores per entry
        radar_scores = {}
        for entry_id, results in results_by_entry.items():
            entry_name = next(
                (e.name for e in self.entries if e.run_id == entry_id),
                entry_id,
            )
            dim_avgs = []
            for dim in dimensions:
                all_scores = []
                for profile_result in results.profiles.values():
                    for task_result in profile_result.tasks.values():
                        for run in task_result.runs:
                            if dim in run.scores:
                                all_scores.append(run.scores[dim])
                dim_avgs.append(
                    sum(all_scores) / len(all_scores) if all_scores else 0.0
                )
            radar_scores[entry_name] = dim_avgs

        chart_configs["radar-aggregate"] = build_radar_config(
            model_name="All Entries",
            profiles=entry_names,
            dimensions=dimensions,
            scores=radar_scores,
        )

        return chart_configs
