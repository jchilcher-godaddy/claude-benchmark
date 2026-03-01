"""HTML report generator for benchmark results.

Orchestrates all reporting modules to produce a single self-contained HTML report.
Wires together data models, charts, diffs, regression detection, and raw data export
into a Jinja2-rendered HTML file with inlined CSS and Chart.js.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from claude_benchmark.reporting.charts import (
    DIMENSION_LABELS,
    build_all_chart_configs,
    sanitize_chart_data,
)
from claude_benchmark.reporting.diff_view import generate_all_diffs
from claude_benchmark.reporting.exporter import export_raw_data
from claude_benchmark.reporting.models import BenchmarkResults, RunResult, _sanitize_dict
from claude_benchmark.reporting.llm_summary import generate_llm_summary
from claude_benchmark.reporting.regression import (
    detect_all_regressions,
    summarize_regressions,
)

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> str:
    """Serialize value to JSON, replacing NaN/Inf with null."""
    return json.dumps(_sanitize_dict(value), default=str)


def _json_script_safe(value: str) -> str:
    """Escape a JSON string for safe embedding inside HTML <script> tags.

    Replaces sequences that could prematurely close a script block or
    cause HTML parsing issues:
    - ``</`` becomes ``<\\/`` to prevent ``</script>`` from closing the tag.
    - ``<!--`` becomes ``<\\!--`` to prevent opening HTML comments.

    Args:
        value: A pre-serialized JSON string.

    Returns:
        The escaped string, safe for injection into ``<script>`` blocks.
    """
    return value.replace("</", "<\\/").replace("<!--", "<\\!--")


def _build_comparison_tables(
    models: list[str],
    dimensions: list[str],
    scores_by_model: dict[str, dict[str, list[float]]],
) -> dict[str, list[dict[str, Any]]]:
    """Build per-model comparison tables with best-in-dimension highlighting.

    Returns:
        {model: [{profile, scores: [{value, delta, is_best}], avg, rank}]}
        Rows are sorted by avg descending (rank 1 = best).
    """
    tables: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        model_scores = scores_by_model.get(model, {})
        profiles = list(model_scores.keys())
        if not profiles:
            tables[model] = []
            continue

        n_dims = len(dimensions)

        # Best score per dimension
        bests = []
        for d_idx in range(n_dims):
            vals = [model_scores[p][d_idx] for p in profiles]
            bests.append(max(vals))

        rows = []
        for profile in profiles:
            p_scores = model_scores[profile]
            cells = []
            for d_idx in range(n_dims):
                val = p_scores[d_idx]
                best = bests[d_idx]
                is_best = abs(val - best) < 0.005
                delta = val - best  # 0.0 for best, negative for others
                cells.append({
                    "value": round(val, 1),
                    "delta": round(delta, 1),
                    "is_best": is_best,
                })
            avg = sum(p_scores) / n_dims if n_dims else 0.0
            rows.append({
                "profile": profile,
                "scores": cells,
                "avg": round(avg, 1),
                "rank": 0,  # filled below
            })

        # Sort by avg descending, assign ranks
        rows.sort(key=lambda r: r["avg"], reverse=True)
        for i, row in enumerate(rows):
            row["rank"] = i + 1

        tables[model] = rows

    return tables


class ReportGenerator:
    """Generate self-contained HTML benchmark report.

    Orchestrates chart config building, diff generation, regression detection,
    and raw data export, then renders everything into a single HTML file using
    Jinja2 templates with inlined Chart.js.
    """

    def __init__(self, results_dir: Path) -> None:
        """Initialize with path to benchmark results directory.

        Args:
            results_dir: Directory containing benchmark result JSON files.
        """
        self.results_dir = Path(results_dir)
        self.env = Environment(
            loader=PackageLoader("claude_benchmark", "templates"),
            autoescape=select_autoescape(["html", "html.j2"]),
        )
        self.env.filters["tojson_safe"] = _json_safe

    def generate(
        self,
        output_path: Path,
        results: BenchmarkResults | None = None,
        regressions: list | None = None,
        csv_content: str | None = None,
        task_descriptions: dict[str, str] | None = None,
        llm_summary: bool = True,
    ) -> Path:
        """Generate the complete HTML benchmark report.

        Loads data (or uses pre-loaded data), runs all analysis modules, and
        renders the Jinja2 template into a self-contained HTML file at
        output_path.

        Args:
            output_path: Path where the HTML report will be written.
            results: Pre-loaded BenchmarkResults. If provided, skips reading
                results.json from disk. This avoids double-loading when the
                caller (e.g. the ``report`` CLI command) has already assembled
                the data via :func:`load_results_dir`.
            regressions: Pre-computed regression results. If provided, skips
                re-running regression detection.
            csv_content: Pre-loaded CSV content for inline download. If
                provided, skips calling export_raw_data internally.
            task_descriptions: Optional mapping of task name to human-readable
                description (from task.toml files). Passed to templates for
                display alongside task IDs.
            llm_summary: If True (default), generate an LLM narrative summary
                for the executive summary section. Set False to skip.

        Returns:
            The output_path where the report was written.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Load benchmark data (use pre-loaded if available)
        if results is None:
            results = self._load_benchmark_data()

        # 2. Detect regressions (use pre-computed if available)
        if regressions is None:
            regressions = detect_all_regressions(results, baseline_profile="empty")
        regressions_list = [r for r in regressions if r.is_regression]

        # 3. Build chart configs
        models = results.models
        profiles = list(results.profiles.keys())
        dimensions = self._get_dimensions(results)
        tasks = results.tasks

        (
            scores_by_model, scores_by_dimension, token_counts, quality_scores,
            scores_by_dim_by_model, token_counts_by_model,
            quality_scores_by_model,
        ) = self._extract_chart_data(results)

        chart_configs = build_all_chart_configs(
            models=models,
            profiles=profiles,
            dimensions=dimensions,
            tasks=tasks,
            scores_by_model=scores_by_model,
            scores_by_dimension=scores_by_dimension,
            token_counts=token_counts,
            quality_scores=quality_scores,
            scores_by_dim_by_model=scores_by_dim_by_model,
            token_counts_by_model=token_counts_by_model,
            quality_scores_by_model=quality_scores_by_model,
        )

        # 4. Build comparison data and generate diffs
        comparison_data = self._extract_comparison_data(results)
        diffs = generate_all_diffs(
            {k: {p: v for p, v in profiles_map.items()}
             for k, profiles_map in comparison_data.items()}
        )

        # 5. Get CSV content for inline download
        if csv_content is not None:
            raw_csv = csv_content
        else:
            _json_path, csv_path = export_raw_data(results, output_path.parent)
            raw_csv = csv_path.read_text(encoding="utf-8") if csv_path.exists() else ""

        # 6. Read vendored Chart.js
        chartjs_path = Path(__file__).parent.parent / "assets" / "chart.min.js"
        chartjs_source = chartjs_path.read_text(encoding="utf-8")

        # 7. Compute executive summary data (reuse quality_scores from step 3)
        best_profile = self._find_best_profile(results, quality_scores=quality_scores)
        token_winner = self._find_token_winner(results, quality_scores=quality_scores)

        # 7b. Model/profile combo metrics for multi-model reports
        best_combo_model, best_combo_profile, best_combo_score = (
            self._find_best_combo(quality_scores_by_model)
        )
        best_profile_overall, best_profile_score = (
            self._find_best_profile_overall(quality_scores_by_model)
        )
        tw_model, tw_profile, tw_score = self._find_token_winner_combo(
            quality_scores_by_model, token_counts_by_model,
        )

        # 7c. Variant analysis insights
        category_analysis = self._compute_category_variant_analysis(
            results, best_profile_overall
        )
        model_preferences = self._compute_model_variant_preferences(
            quality_scores_by_model, best_profile_overall
        )

        # 8. Generate plain-English insights
        insights = self._generate_insights(
            quality_scores=quality_scores,
            token_counts=token_counts,
            best_profile=best_profile,
            token_winner=token_winner,
            regressions_list=regressions_list,
        )

        # 8b. Generate LLM narrative summary (optional)
        llm_summary_text: str | None = None
        if llm_summary:
            llm_summary_text = generate_llm_summary(
                quality_scores=quality_scores,
                best_combo_model=best_combo_model,
                best_combo_profile=best_combo_profile,
                best_combo_score=best_combo_score,
                best_profile_overall=best_profile_overall,
                best_profile_score=best_profile_score,
                tw_model=tw_model,
                tw_profile=tw_profile,
                tw_score=tw_score,
                category_analysis=category_analysis,
                model_preferences=model_preferences,
                insights=insights,
                regressions_list=regressions_list,
                token_counts=token_counts,
                profiles=profiles,
                tasks=tasks,
                models=models,
            )

        # 9. Build score detail for detailed_scores template (mean +/- std with regression badges)
        score_detail = self._build_score_detail(results, regressions_list, models)

        # 9b. Build drilldown data for click-to-expand score detail
        drilldown_data = self._build_drilldown_data(results)

        # 9c. Build dashboard comparison tables
        comparison_tables = _build_comparison_tables(
            models, dimensions, scores_by_model,
        )

        # 10. Build comparison data JSON with scores and diffs for each model/task combo
        comparison_data_json = self._build_comparison_json(
            results, comparison_data, diffs
        )

        # 11. Render template
        template = self.env.get_template("report.html.j2")
        html = template.render(
            metadata=results.metadata,
            regressions=regressions,
            regressions_list=regressions_list,
            best_profile=best_profile,
            token_winner=token_winner,
            insights=insights,
            quality_scores=quality_scores,
            models=models,
            profiles=profiles,
            tasks=tasks,
            dimensions=dimensions,
            scores_by_dimension=scores_by_dimension,
            score_detail=score_detail,
            multi_model=len(models) > 1,
            scores_by_dim_by_model=scores_by_dim_by_model,
            comparison_tables=comparison_tables,
            dim_labels=DIMENSION_LABELS,
            chartjs_source=chartjs_source,
            benchmark_data_json=_json_script_safe(json.dumps(
                _sanitize_dict(results.to_export_dict()), default=str
            )),
            chart_configs_json=_json_script_safe(json.dumps(
                {k: sanitize_chart_data(v) for k, v in chart_configs.items()},
                default=str,
            )),
            comparison_data_json=_json_script_safe(comparison_data_json),
            drilldown_data_json=_json_script_safe(json.dumps(
                _sanitize_dict(drilldown_data), default=str
            )),
            raw_csv=raw_csv,
            task_descriptions=task_descriptions or {},
            best_combo_model=best_combo_model,
            best_combo_profile=best_combo_profile,
            best_combo_score=best_combo_score,
            best_profile_overall=best_profile_overall,
            best_profile_score=best_profile_score,
            tw_model=tw_model,
            tw_profile=tw_profile,
            tw_score=tw_score,
            category_analysis=category_analysis,
            model_preferences=model_preferences,
            llm_summary_text=llm_summary_text,
        )

        # 12. Write HTML
        output_path.write_text(html, encoding="utf-8")

        return output_path

    def _load_benchmark_data(self) -> BenchmarkResults:
        """Load benchmark data from results directory.

        Reads results.json from results_dir and parses into BenchmarkResults.

        Returns:
            Parsed BenchmarkResults.

        Raises:
            FileNotFoundError: If results.json is not found.
            ValueError: If the JSON cannot be parsed into BenchmarkResults.
        """
        results_file = self.results_dir / "results.json"
        if not results_file.exists():
            raise FileNotFoundError(
                f"Benchmark results not found: {results_file}. "
                f"Expected results.json in {self.results_dir}"
            )

        try:
            data = json.loads(results_file.read_text(encoding="utf-8"))
            return BenchmarkResults.model_validate(data)
        except Exception as e:
            raise ValueError(
                f"Failed to parse benchmark results from {results_file}: {e}"
            ) from e

    def _get_dimensions(self, results: BenchmarkResults) -> list[str]:
        """Extract all scoring dimensions from results."""
        dims: set[str] = set()
        for profile in results.profiles.values():
            for task_result in profile.tasks.values():
                for run in task_result.runs:
                    dims.update(run.scores.keys())
        return sorted(dims)

    def _extract_comparison_data(
        self, results: BenchmarkResults
    ) -> dict[str, dict[str, str]]:
        """Build comparison data mapping model/task combos to profile code outputs.

        For each model/task combination, maps each profile to the code output
        from the best run (highest composite score). Only the first model is used
        for comparisons since tasks are model-specific runs.

        Args:
            results: Full benchmark results.

        Returns:
            Dict of {"{model}/{task}": {profile_id: code_output}}.
        """
        comparison: dict[str, dict[str, str]] = {}

        for model in results.models:
            for task in results.tasks:
                key = f"{model}/{task}"
                comparison[key] = {}

                for profile_id, profile_result in results.profiles.items():
                    if task not in profile_result.tasks:
                        continue

                    task_result = profile_result.tasks[task]
                    runs_for_model = [
                        r for r in task_result.runs if r.model == model
                    ]

                    if not runs_for_model:
                        # If runs don't have model-specific filtering, use all
                        runs_for_model = list(task_result.runs)

                    if not runs_for_model:
                        continue

                    # Best run = highest composite (mean of all scores)
                    best_run = max(
                        runs_for_model,
                        key=lambda r: (
                            sum(r.scores.values()) / len(r.scores)
                            if r.scores
                            else 0
                        ),
                    )

                    if best_run.code_output:
                        comparison[key][profile_id] = best_run.code_output

        return comparison

    def _extract_chart_data(self, results: BenchmarkResults) -> tuple:
        """Extract chart data structures from BenchmarkResults.

        Returns:
            Tuple of:
                scores_by_model: {model: {profile: [scores_per_dimension]}}
                scores_by_dimension: {dim: {profile: {task: score}}}
                token_counts: {profile: total_tokens}
                quality_scores: {profile: avg_composite}
                scores_by_dim_by_model: {model: {dim: {profile: {task: score}}}}
                token_counts_by_model: {model: {profile: total_tokens}}
                quality_scores_by_model: {model: {profile: avg_composite}}
        """
        dimensions = self._get_dimensions(results)

        # scores_by_model: {model: {profile: [avg_score_per_dimension]}}
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
                    if scores_for_dim:
                        dim_avgs.append(
                            sum(scores_for_dim) / len(scores_for_dim)
                        )
                    else:
                        dim_avgs.append(0.0)
                scores_by_model[model][profile_id] = dim_avgs

        # scores_by_dimension: {dimension: {profile: {task: avg_score}}}
        scores_by_dimension: dict[str, dict[str, dict[str, float]]] = {}
        for dim in dimensions:
            scores_by_dimension[dim] = {}
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
                scores_by_dimension[dim][profile_id] = task_scores

        # token_counts: {profile: total_tokens}
        token_counts: dict[str, float] = {}
        for profile_id, profile_result in results.profiles.items():
            token_counts[profile_id] = float(profile_result.total_tokens)

        # quality_scores: {profile: avg_composite_across_all_tasks}
        quality_scores: dict[str, float] = {}
        for profile_id, profile_result in results.profiles.items():
            all_composites: list[float] = []
            for task_result in profile_result.tasks.values():
                for run in task_result.runs:
                    if run.scores:
                        composite = sum(run.scores.values()) / len(run.scores)
                        if not math.isnan(composite):
                            all_composites.append(composite)
            if all_composites:
                quality_scores[profile_id] = (
                    sum(all_composites) / len(all_composites)
                )
            else:
                quality_scores[profile_id] = 0.0

        # Model-specific data for multi-model reports
        # scores_by_dim_by_model: {model: {dim: {profile: {task: score}}}}
        scores_by_dim_by_model: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
        for model in results.models:
            scores_by_dim_by_model[model] = {}
            for dim in dimensions:
                scores_by_dim_by_model[model][dim] = {}
                for profile_id, profile_result in results.profiles.items():
                    model_task_scores: dict[str, float] = {}
                    for task_id, task_result in profile_result.tasks.items():
                        model_dim_scores = [
                            run.scores[dim]
                            for run in task_result.runs
                            if run.model == model and dim in run.scores
                        ]
                        if model_dim_scores:
                            model_task_scores[task_id] = (
                                sum(model_dim_scores) / len(model_dim_scores)
                            )
                    scores_by_dim_by_model[model][dim][profile_id] = model_task_scores

        # token_counts_by_model: {model: {profile: total_tokens}}
        token_counts_by_model: dict[str, dict[str, float]] = {}
        for model in results.models:
            token_counts_by_model[model] = {}
            for profile_id, profile_result in results.profiles.items():
                total = sum(
                    run.token_count
                    for task_result in profile_result.tasks.values()
                    for run in task_result.runs
                    if run.model == model
                )
                token_counts_by_model[model][profile_id] = float(total)

        # quality_scores_by_model: {model: {profile: avg_composite}}
        quality_scores_by_model: dict[str, dict[str, float]] = {}
        for model in results.models:
            quality_scores_by_model[model] = {}
            for profile_id, profile_result in results.profiles.items():
                model_composites: list[float] = []
                for task_result in profile_result.tasks.values():
                    for run in task_result.runs:
                        if run.model == model and run.scores:
                            composite = sum(run.scores.values()) / len(run.scores)
                            if not math.isnan(composite):
                                model_composites.append(composite)
                if model_composites:
                    quality_scores_by_model[model][profile_id] = (
                        sum(model_composites) / len(model_composites)
                    )
                else:
                    quality_scores_by_model[model][profile_id] = 0.0

        return (
            scores_by_model, scores_by_dimension, token_counts, quality_scores,
            scores_by_dim_by_model, token_counts_by_model, quality_scores_by_model,
        )

    def _find_best_profile(
        self,
        results: BenchmarkResults,
        quality_scores: dict[str, float] | None = None,
    ) -> str:
        """Find the profile with the highest average composite score.

        Args:
            results: Full benchmark results (used as fallback).
            quality_scores: Pre-computed {profile: avg_composite} from
                _extract_chart_data. Avoids redundant iteration.
        """
        if quality_scores:
            best_profile = max(quality_scores, key=quality_scores.get)
            return best_profile if quality_scores[best_profile] > 0 else "N/A"

        best_score = -1.0
        best_profile = "N/A"

        for profile_id, profile_result in results.profiles.items():
            composites: list[float] = []
            for task_result in profile_result.tasks.values():
                for run in task_result.runs:
                    if run.scores:
                        composite = sum(run.scores.values()) / len(run.scores)
                        if not math.isnan(composite):
                            composites.append(composite)
            if composites:
                avg = sum(composites) / len(composites)
                if avg > best_score:
                    best_score = avg
                    best_profile = profile_id

        return best_profile

    def _find_token_winner(
        self,
        results: BenchmarkResults,
        quality_scores: dict[str, float] | None = None,
    ) -> str:
        """Find the profile with the highest quality-per-token ratio.

        Args:
            results: Full benchmark results.
            quality_scores: Pre-computed {profile: avg_composite} from
                _extract_chart_data. Avoids redundant iteration.
        """
        best_ratio = -1.0
        best_profile = "N/A"

        for profile_id, profile_result in results.profiles.items():
            total_tokens = profile_result.total_tokens
            if total_tokens == 0:
                continue

            if quality_scores and profile_id in quality_scores:
                avg_quality = quality_scores[profile_id]
            else:
                composites: list[float] = []
                for task_result in profile_result.tasks.values():
                    for run in task_result.runs:
                        if run.scores:
                            composite = sum(run.scores.values()) / len(run.scores)
                            if not math.isnan(composite):
                                composites.append(composite)
                avg_quality = sum(composites) / len(composites) if composites else 0.0

            if avg_quality > 0:
                ratio = avg_quality / total_tokens
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_profile = profile_id

        return best_profile

    def _find_best_combo(
        self,
        quality_scores_by_model: dict[str, dict[str, float]],
    ) -> tuple[str, str, float]:
        """Find the model/profile pair with the highest quality score.

        Args:
            quality_scores_by_model: {model: {profile: avg_composite}}.

        Returns:
            (model, profile, score) for the best pair, or ("N/A", "N/A", 0.0).
        """
        best_model, best_profile, best_score = "N/A", "N/A", -1.0
        for model, profiles in quality_scores_by_model.items():
            for profile, score in profiles.items():
                if score > best_score:
                    best_model, best_profile, best_score = model, profile, score
        if best_score < 0:
            return "N/A", "N/A", 0.0
        return best_model, best_profile, best_score

    def _find_best_profile_overall(
        self,
        quality_scores_by_model: dict[str, dict[str, float]],
    ) -> tuple[str, float]:
        """Find the profile with the highest average quality across all models.

        Args:
            quality_scores_by_model: {model: {profile: avg_composite}}.

        Returns:
            (profile, avg_score) for the best profile, or ("N/A", 0.0).
        """
        # Collect all profiles seen across models
        all_profiles: set[str] = set()
        for profiles in quality_scores_by_model.values():
            all_profiles.update(profiles.keys())

        best_profile, best_avg = "N/A", -1.0
        for profile in all_profiles:
            scores = [
                profiles[profile]
                for profiles in quality_scores_by_model.values()
                if profile in profiles
            ]
            if not scores:
                continue
            avg = sum(scores) / len(scores)
            if avg > best_avg:
                best_profile, best_avg = profile, avg
        if best_avg < 0:
            return "N/A", 0.0
        return best_profile, best_avg

    def _find_token_winner_combo(
        self,
        quality_scores_by_model: dict[str, dict[str, float]],
        token_counts_by_model: dict[str, dict[str, float]],
    ) -> tuple[str, str, float]:
        """Find the model/profile pair with the best quality-per-token ratio.

        Args:
            quality_scores_by_model: {model: {profile: avg_composite}}.
            token_counts_by_model: {model: {profile: total_tokens}}.

        Returns:
            (model, profile, quality_score) for the most efficient pair,
            or ("N/A", "N/A", 0.0).
        """
        best_model, best_profile, best_score = "N/A", "N/A", 0.0
        best_ratio = -1.0
        for model, profiles in quality_scores_by_model.items():
            for profile, score in profiles.items():
                tokens = token_counts_by_model.get(model, {}).get(profile, 0.0)
                if tokens <= 0 or score <= 0:
                    continue
                ratio = score / tokens
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_model, best_profile, best_score = model, profile, score
        return best_model, best_profile, best_score

    @staticmethod
    def _task_category(task_id: str) -> str:
        """Derive task category from task name convention.

        Strips trailing numeric suffix (e.g. ``bug-fix-01`` → ``bug-fix``).
        Falls back to the full task name if no numeric suffix is found.
        """
        parts = task_id.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0]
        return task_id

    def _compute_category_variant_analysis(
        self,
        results: BenchmarkResults,
        best_profile_overall: str,
    ) -> list[dict[str, Any]]:
        """Compute per-category variant analysis.

        For each auto-derived task category, computes average composite per
        profile across all models/runs, identifies the winner, and flags
        exceptions where the category winner differs from the overall best.

        Args:
            results: Full benchmark results.
            best_profile_overall: The profile that won overall.

        Returns:
            List of dicts sorted by category name, each containing category,
            winner, scores, spread, margin, and exception flag.
        """
        # Collect composites per category per profile
        # {category: {profile: [composites]}}
        cat_scores: dict[str, dict[str, list[float]]] = {}
        cat_tasks: dict[str, set[str]] = {}

        for profile_id, profile_result in results.profiles.items():
            for task_id, task_result in profile_result.tasks.items():
                category = self._task_category(task_id)
                if category not in cat_scores:
                    cat_scores[category] = {}
                    cat_tasks[category] = set()
                cat_tasks[category].add(task_id)

                if profile_id not in cat_scores[category]:
                    cat_scores[category][profile_id] = []

                for run in task_result.runs:
                    if not run.scores:
                        continue
                    composite = sum(run.scores.values()) / len(run.scores)
                    if not math.isnan(composite):
                        cat_scores[category][profile_id].append(composite)

        analysis: list[dict[str, Any]] = []
        for category in sorted(cat_scores):
            profiles_in_cat = cat_scores[category]
            # Compute average per profile
            avgs: dict[str, float] = {}
            for profile_id, composites in profiles_in_cat.items():
                if composites:
                    avgs[profile_id] = sum(composites) / len(composites)

            if not avgs:
                continue

            sorted_profiles = sorted(avgs.items(), key=lambda x: x[1], reverse=True)
            winner, winner_score = sorted_profiles[0]

            if len(sorted_profiles) >= 2:
                runner_up, runner_up_score = sorted_profiles[1]
                margin = winner_score - runner_up_score
            else:
                runner_up, runner_up_score = winner, winner_score
                margin = 0.0

            all_scores = list(avgs.values())
            spread = max(all_scores) - min(all_scores) if len(all_scores) > 1 else 0.0

            analysis.append({
                "category": category,
                "winner": winner,
                "winner_score": round(winner_score, 2),
                "runner_up": runner_up,
                "runner_up_score": round(runner_up_score, 2),
                "spread": round(spread, 2),
                "margin": round(margin, 2),
                "is_exception": winner != best_profile_overall,
                "task_count": len(cat_tasks[category]),
            })

        return analysis

    def _compute_model_variant_preferences(
        self,
        quality_scores_by_model: dict[str, dict[str, float]],
        best_profile_overall: str,
    ) -> list[dict[str, Any]]:
        """Compute per-model profile preferences.

        For each model, finds the best profile and flags exceptions where the
        model's preferred profile differs from the overall best.

        Args:
            quality_scores_by_model: {model: {profile: avg_composite}}.
            best_profile_overall: The profile that won overall.

        Returns:
            List of dicts sorted by model name, each containing model,
            preferred_profile, score, spread, margin, and exception flag.
        """
        preferences: list[dict[str, Any]] = []

        for model in sorted(quality_scores_by_model):
            profiles = quality_scores_by_model[model]
            if not profiles:
                continue

            sorted_profiles = sorted(
                profiles.items(), key=lambda x: x[1], reverse=True
            )
            preferred, score = sorted_profiles[0]

            if len(sorted_profiles) >= 2:
                runner_up, runner_up_score = sorted_profiles[1]
                margin = score - runner_up_score
            else:
                runner_up, runner_up_score = preferred, score
                margin = 0.0

            all_scores = list(profiles.values())
            spread = max(all_scores) - min(all_scores) if len(all_scores) > 1 else 0.0

            preferences.append({
                "model": model,
                "preferred_profile": preferred,
                "score": round(score, 2),
                "runner_up": runner_up,
                "runner_up_score": round(runner_up_score, 2),
                "spread": round(spread, 2),
                "margin": round(margin, 2),
                "is_exception": preferred != best_profile_overall,
            })

        return preferences

    @staticmethod
    def _tier_label(score: float) -> str:
        """Return a human-readable tier label for a numeric score."""
        if score >= 90:
            return "excellent"
        if score >= 70:
            return "good"
        if score >= 50:
            return "fair"
        return "poor"

    def _generate_insights(
        self,
        *,
        quality_scores: dict[str, float],
        token_counts: dict[str, float],
        best_profile: str,
        token_winner: str,
        regressions_list: list,
    ) -> list[str]:
        """Generate plain-English insight sentences for the executive summary.

        Returns:
            List of 3–6 human-readable sentences summarizing the benchmark results.
        """
        insights: list[str] = []

        # 1. Best profile result + tier
        best_score = quality_scores.get(best_profile, 0.0)
        tier = self._tier_label(best_score)
        insights.append(
            f'"{best_profile}" achieved {best_score:.1f}/100 overall, '
            f"rated {tier}."
        )

        # 2. Token efficiency comparison
        if token_winner == best_profile:
            insights.append(
                f'"{best_profile}" is also the most token-efficient — '
                f"best quality for the lowest cost."
            )
        else:
            tw_score = quality_scores.get(token_winner, 0.0)
            insights.append(
                f'"{token_winner}" is the most token-efficient '
                f"(scored {tw_score:.1f}/100) — a different profile than "
                f'the quality winner "{best_profile}". Consider the '
                f"quality-vs-cost tradeoff."
            )

        # 3. Quality spread
        if len(quality_scores) >= 2:
            scores = list(quality_scores.values())
            spread = max(scores) - min(scores)
            if spread < 5:
                insights.append(
                    f"Quality spread is only {spread:.1f} points across profiles "
                    f"— instructions had minimal impact on output quality."
                )
            elif spread < 15:
                insights.append(
                    f"Quality spread is {spread:.1f} points — instructions caused "
                    f"moderate differences in output quality."
                )
            else:
                insights.append(
                    f"Quality spread is {spread:.1f} points — instructions caused "
                    f"significant differences in output quality."
                )

        # 4. Regression summary
        if regressions_list:
            affected = {r.profile for r in regressions_list}
            insights.append(
                f"{len(regressions_list)} regression(s) detected across "
                f'{len(affected)} profile(s): {", ".join(sorted(affected))}. '
                f"Review the flagged dimensions below."
            )
        else:
            insights.append(
                "No regressions detected — all profiles performed within "
                "expected ranges compared to the empty baseline."
            )

        # 5. Baseline comparison
        empty_score = quality_scores.get("empty", None)
        if empty_score is not None and len(quality_scores) > 1:
            better = [
                p for p, s in quality_scores.items()
                if p != "empty" and s > empty_score
            ]
            if better:
                insights.append(
                    f"{len(better)} profile(s) beat the empty baseline: "
                    f'{", ".join(sorted(better))}.'
                )
            else:
                insights.append(
                    "No profile outperformed the empty baseline — the custom "
                    "instructions did not improve overall quality."
                )

        return insights

    def _build_score_detail(
        self,
        results: BenchmarkResults,
        regressions_list: list,
        models: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build detailed score info (mean, std, regression flag) for template.

        Keys are "{dimension}/{task}/{profile}" for single-model, or
        "{dimension}/{task}/{profile}/{model}" for multi-model.

        Args:
            results: Full benchmark results.
            regressions_list: List of RegressionResult flagged as regressions.
            models: List of model names. When more than one model is present,
                per-model mean/std are computed from raw runs.

        Returns:
            Dict mapping keys to {mean, std, regression}.
        """
        detail: dict[str, dict[str, Any]] = {}
        multi_model = models is not None and len(models) > 1

        # Index regressions for fast lookup
        regression_set: set[tuple[str, str, str]] = set()
        for r in regressions_list:
            regression_set.add((r.profile, r.task, r.dimension))

        for profile_id, profile_result in results.profiles.items():
            for task_id, task_result in profile_result.tasks.items():
                if multi_model:
                    for model in models:
                        model_runs = [
                            r for r in task_result.runs if r.model == model
                        ]
                        if not model_runs:
                            continue
                        all_dims = {
                            d for r in model_runs for d in r.scores
                        }
                        for dim in all_dims:
                            scores = [
                                r.scores[dim]
                                for r in model_runs
                                if dim in r.scores
                            ]
                            if not scores:
                                continue
                            mean = sum(scores) / len(scores)
                            std = (
                                (
                                    sum((s - mean) ** 2 for s in scores)
                                    / len(scores)
                                )
                                ** 0.5
                                if len(scores) > 1
                                else 0.0
                            )
                            key = f"{dim}/{task_id}/{profile_id}/{model}"
                            detail[key] = {
                                "mean": mean,
                                "std": std,
                                "regression": (
                                    (profile_id, task_id, dim)
                                    in regression_set
                                ),
                            }
                else:
                    for dim in task_result.mean_scores:
                        key = f"{dim}/{task_id}/{profile_id}"
                        detail[key] = {
                            "mean": task_result.mean_scores.get(dim, 0.0),
                            "std": task_result.std_scores.get(dim, 0.0),
                            "regression": (
                                (profile_id, task_id, dim) in regression_set
                            ),
                        }

        return detail

    @staticmethod
    def _load_test_failures(run: RunResult) -> list[dict[str, str]]:
        """Load individual test failure details from the pytest json-report.

        Resolves ``run.output_dir`` to find ``{output_dir}/.test-report.json``,
        parses the pytest json-report format, and extracts failed tests.

        Returns:
            List of dicts with ``name``, ``error``, and ``detail`` keys,
            or an empty list if no report exists or there are no failures.
        """
        if not run.output_dir:
            return []

        report_path = Path(run.output_dir) / ".test-report.json"
        if not report_path.exists():
            return []

        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Failed to read test report %s: %s", report_path, exc)
            return []

        tests = data.get("tests", [])
        failures: list[dict[str, str]] = []
        for t in tests:
            if t.get("outcome") != "failed":
                continue

            nodeid = t.get("nodeid", "")
            # Extract short test name from nodeid (e.g. "path/test.py::test_name" -> "test_name")
            name = nodeid.rsplit("::", 1)[-1] if "::" in nodeid else nodeid

            call = t.get("call", {})
            longrepr = call.get("longrepr", "") if isinstance(call, dict) else ""

            # Extract short error: last line starting with "E   "
            error = ""
            for line in reversed(longrepr.splitlines()):
                stripped = line.strip()
                if stripped.startswith("E "):
                    error = stripped[2:].strip()
                    break
            error = error[:200]

            detail = longrepr[:2000]

            failures.append({"name": name, "error": error, "detail": detail})

        return failures

    def _build_drilldown_data(
        self,
        results: BenchmarkResults,
    ) -> dict[str, Any]:
        """Build per-task/profile drilldown data from nested score_details.

        For each task/profile combination, picks the best run (highest
        composite score) and extracts the nested scoring breakdown into
        a structure suitable for the click-to-expand detail panel.

        Returns:
            Dict mapping "{task}/{profile}" keys to detail dicts.
        """
        drilldown: dict[str, Any] = {}

        for profile_id, profile_result in results.profiles.items():
            for task_id, task_result in profile_result.tasks.items():
                runs = list(task_result.runs)
                if not runs:
                    continue

                # Pick the best run by composite score
                best_run = max(
                    runs,
                    key=lambda r: r.scores.get("composite", 0.0),
                )

                details = best_run.score_details
                if not details:
                    continue

                entry: dict[str, Any] = {"has_output": True}

                # Static analysis details
                static = details.get("static")
                if isinstance(static, dict):
                    entry["has_output"] = static.get("lines_of_code", 0) > 0
                    entry["tests"] = {
                        "passed": static.get("tests_passed", 0),
                        "total": static.get("tests_total", 0),
                        "pass_rate": static.get("test_pass_rate", 0.0),
                        "failures": self._load_test_failures(best_run),
                    }
                    entry["lint"] = {
                        "score": static.get("lint_score", 0.0),
                        "errors": static.get("lint_errors", 0),
                        "details": [
                            {"code": d.get("rule", d.get("code", "")),
                             "message": d.get("message", "")}
                            for d in (static.get("lint_details") or [])
                        ],
                    }
                    entry["complexity"] = {
                        "score": static.get("complexity_score", 0.0),
                        "avg": static.get("avg_complexity", 0.0),
                        "details": [
                            {"name": d.get("name", ""),
                             "complexity": d.get("complexity", 0),
                             "rank": d.get("rank", "")}
                            for d in (static.get("complexity_details") or [])
                        ],
                    }

                # LLM judge details
                llm = details.get("llm")
                if isinstance(llm, dict):
                    entry["llm"] = {
                        "normalized": llm.get("normalized", 0.0),
                        "average": llm.get("average", 0.0),
                        "criteria": [
                            {"name": c.get("name", ""),
                             "score": c.get("score", 0),
                             "reasoning": c.get("reasoning", "")}
                            for c in (llm.get("criteria") or [])
                        ],
                    }

                # Token efficiency
                te = details.get("token_efficiency")
                if isinstance(te, dict):
                    entry["tokens"] = {
                        "total": te.get("total_tokens", 0),
                        "points_per_1k": te.get("points_per_1k_tokens", 0.0),
                    }

                # Run-level token/cost info
                entry["run_tokens"] = best_run.token_count
                entry["run_cost"] = details.get("token_efficiency", {}).get(
                    "composite_score", None
                )

                # Composite formula components
                composite_data = details.get("composite")
                if isinstance(composite_data, dict):
                    entry["composite_score"] = composite_data.get(
                        "composite", 0.0
                    )
                    static_inner = composite_data.get("static_score")
                    if isinstance(static_inner, dict):
                        entry["static_weighted_total"] = static_inner.get(
                            "weighted_total", 0.0
                        )
                    else:
                        entry["static_weighted_total"] = 0.0
                    entry["static_only"] = composite_data.get(
                        "static_only", True
                    )

                # Per-run scores for variance insight
                entry["all_run_scores"] = [
                    dict(r.scores) for r in runs
                ]

                key = f"{task_id}/{profile_id}"
                drilldown[key] = entry

        return drilldown

    def _build_comparison_json(
        self,
        results: BenchmarkResults,
        comparison_data: dict[str, dict[str, str]],
        diffs: dict[str, str],
    ) -> str:
        """Build JSON string for comparison data used by the comparison template.

        Structure: {model/task: {scores: {profile: {dim: score}}, diffs: {pair_key: html}}}
        """
        output: dict[str, dict[str, Any]] = {}

        for model in results.models:
            for task in results.tasks:
                key = f"{model}/{task}"
                entry: dict[str, Any] = {"scores": {}, "diffs": {}}

                for profile_id, profile_result in results.profiles.items():
                    if task in profile_result.tasks:
                        task_result = profile_result.tasks[task]
                        entry["scores"][profile_id] = dict(
                            task_result.mean_scores
                        )

                # Collect diffs for this model/task
                prefix = f"{key}/"
                for diff_key, diff_html in diffs.items():
                    if diff_key.startswith(prefix):
                        pair_name = diff_key[len(prefix):]
                        entry["diffs"][pair_name] = diff_html

                output[key] = entry

        return json.dumps(_sanitize_dict(output), default=str)

    def print_cli_summary(self, regressions: list) -> None:
        """Print regression summary to CLI after benchmark completes.

        Args:
            regressions: List of RegressionResult objects.
        """
        summary = summarize_regressions(regressions)
        print(f"\n--- Regression Summary ---\n{summary}\n")
