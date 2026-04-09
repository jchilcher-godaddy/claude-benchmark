"""Compute calibration metrics from scoring results.

Pure computation — no API calls. Measures variance, discrimination,
and inter-rater agreement to recommend the best judge model.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import spearmanr

from claude_benchmark.calibration.runner import CalibrationResults, ScoringResult

TIER_ORDINAL = {"severe": 1, "mild": 2, "gold": 3}

CRITERIA_NAMES = [
    "code_readability",
    "architecture_quality",
    "instruction_adherence",
    "correctness_reasoning",
]


@dataclass
class ModelMetrics:
    model: str
    mean_variance: float
    pct_deterministic: float  # % of (sample, criterion) groups with variance=0
    discrimination_d: float  # Cohen's d between gold and severe
    per_criterion_discrimination: dict[str, float]  # criterion -> Cohen's d
    gold_mean: float  # mean normalized score for gold tier
    mild_mean: float
    severe_mean: float
    tier_rank_correlation: float  # Spearman r between tier ordinal and score
    recommendation_score: float = 0.0


@dataclass
class CalibrationReport:
    model_metrics: dict[str, ModelMetrics]
    recommended_model: str
    reasoning: str
    inter_rater_agreement: float  # averaged pairwise Spearman r


def _get_criterion_scores(result: ScoringResult, criterion: str) -> float | None:
    if result.score is None:
        return None
    for c in result.score.criteria:
        if c.name == criterion:
            return float(c.score)
    return None


def _cohens_d(group_a: list[float], group_b: list[float]) -> float:
    """Compute Cohen's d effect size between two groups.

    When both groups have zero variance but different means, returns
    float('inf') capped at 10.0 to indicate perfect separation.
    """
    if len(group_a) < 2 or len(group_b) < 2:
        return 0.0
    mean_a = statistics.mean(group_a)
    mean_b = statistics.mean(group_b)
    var_a = statistics.variance(group_a)
    var_b = statistics.variance(group_b)
    pooled_std = ((var_a + var_b) / 2) ** 0.5
    if pooled_std == 0:
        # Both groups have zero variance — if means differ, it's perfect separation
        return 10.0 if mean_a != mean_b else 0.0
    return (mean_a - mean_b) / pooled_std


def compute_calibration_report(cal_results: CalibrationResults) -> CalibrationReport:
    """Compute per-model metrics and recommend the best judge model."""
    model_metrics: dict[str, ModelMetrics] = {}

    # Group results by model
    by_model: dict[str, list[ScoringResult]] = {}
    for r in cal_results.results:
        by_model.setdefault(r.model, []).append(r)

    for model, results in by_model.items():
        # Filter to successful results
        valid = [r for r in results if r.score is not None]
        if not valid:
            model_metrics[model] = ModelMetrics(
                model=model,
                mean_variance=float("inf"),
                pct_deterministic=0.0,
                discrimination_d=0.0,
                per_criterion_discrimination={},
                gold_mean=0.0,
                mild_mean=0.0,
                severe_mean=0.0,
                tier_rank_correlation=0.0,
            )
            continue

        # --- Variance ---
        # Group by (task_name, tier, criterion) and compute intra-group variance
        score_groups: dict[tuple[str, str, str], list[float]] = {}
        for r in valid:
            for criterion in CRITERIA_NAMES:
                val = _get_criterion_scores(r, criterion)
                if val is not None:
                    key = (r.sample.task_name, r.sample.tier, criterion)
                    score_groups.setdefault(key, []).append(val)

        variances: list[float] = []
        deterministic_count = 0
        total_groups = 0
        for scores in score_groups.values():
            if len(scores) >= 2:
                v = statistics.variance(scores)
                variances.append(v)
                total_groups += 1
                if v == 0:
                    deterministic_count += 1

        mean_variance = statistics.mean(variances) if variances else 0.0
        pct_deterministic = (deterministic_count / total_groups * 100) if total_groups else 0.0

        # --- Tier means (normalized 0-100) ---
        tier_scores: dict[str, list[float]] = {"gold": [], "mild": [], "severe": []}
        for r in valid:
            tier_scores[r.sample.tier].append(r.score.normalized)

        gold_mean = statistics.mean(tier_scores["gold"]) if tier_scores["gold"] else 0.0
        mild_mean = statistics.mean(tier_scores["mild"]) if tier_scores["mild"] else 0.0
        severe_mean = statistics.mean(tier_scores["severe"]) if tier_scores["severe"] else 0.0

        # --- Discrimination: Cohen's d between gold and severe ---
        gold_scores = [r.score.normalized for r in valid if r.sample.tier == "gold"]
        severe_scores = [r.score.normalized for r in valid if r.sample.tier == "severe"]
        discrimination_d = _cohens_d(gold_scores, severe_scores)

        # Per-criterion discrimination
        per_criterion_d: dict[str, float] = {}
        for criterion in CRITERIA_NAMES:
            gold_c = [
                _get_criterion_scores(r, criterion)
                for r in valid
                if r.sample.tier == "gold"
            ]
            severe_c = [
                _get_criterion_scores(r, criterion)
                for r in valid
                if r.sample.tier == "severe"
            ]
            gold_c = [x for x in gold_c if x is not None]
            severe_c = [x for x in severe_c if x is not None]
            per_criterion_d[criterion] = _cohens_d(gold_c, severe_c)

        # --- Tier rank correlation ---
        ordinals: list[float] = []
        scores_flat: list[float] = []
        for r in valid:
            ordinals.append(float(TIER_ORDINAL[r.sample.tier]))
            scores_flat.append(r.score.normalized)

        if len(ordinals) >= 3:
            corr, _ = spearmanr(ordinals, scores_flat)
            tier_rank_correlation = float(corr) if not np.isnan(corr) else 0.0
        else:
            tier_rank_correlation = 0.0

        model_metrics[model] = ModelMetrics(
            model=model,
            mean_variance=mean_variance,
            pct_deterministic=pct_deterministic,
            discrimination_d=discrimination_d,
            per_criterion_discrimination=per_criterion_d,
            gold_mean=gold_mean,
            mild_mean=mild_mean,
            severe_mean=severe_mean,
            tier_rank_correlation=tier_rank_correlation,
        )

    # --- Inter-rater agreement ---
    inter_rater = _compute_inter_rater_agreement(cal_results)

    # --- Recommendation scoring ---
    # Normalize metrics across models for fair comparison
    models = list(model_metrics.keys())
    if models:
        disc_values = [model_metrics[m].discrimination_d for m in models]
        det_values = [model_metrics[m].pct_deterministic for m in models]
        var_values = [model_metrics[m].mean_variance for m in models]

        disc_max = max(disc_values) if max(disc_values) > 0 else 1.0
        det_max = max(det_values) if max(det_values) > 0 else 1.0
        var_max = max(var_values) if max(var_values) > 0 else 1.0

        for m in models:
            mm = model_metrics[m]
            norm_disc = mm.discrimination_d / disc_max
            norm_det = mm.pct_deterministic / det_max
            norm_inv_var = 1.0 - (mm.mean_variance / var_max) if var_max > 0 else 1.0
            mm.recommendation_score = (
                0.40 * norm_disc + 0.30 * norm_det + 0.30 * norm_inv_var
            )

    # Pick the best
    if models:
        best = max(models, key=lambda m: model_metrics[m].recommendation_score)
    else:
        best = "haiku"

    best_mm = model_metrics.get(best)
    reasoning = (
        f"{best} scored highest overall "
        f"(score={best_mm.recommendation_score:.2f}): "
        f"discrimination={best_mm.discrimination_d:.2f}, "
        f"determinism={best_mm.pct_deterministic:.0f}%, "
        f"variance={best_mm.mean_variance:.3f}"
    ) if best_mm else f"{best} selected as default"

    return CalibrationReport(
        model_metrics=model_metrics,
        recommended_model=best,
        reasoning=reasoning,
        inter_rater_agreement=inter_rater,
    )


def _compute_inter_rater_agreement(cal_results: CalibrationResults) -> float:
    """Compute averaged pairwise Spearman correlation across models."""
    models = cal_results.models
    if len(models) < 2:
        return 1.0

    # Build per-model mean score vectors keyed by (task_name, tier)
    model_vectors: dict[str, dict[tuple[str, str], list[float]]] = {}
    for r in cal_results.results:
        if r.score is None:
            continue
        key = (r.sample.task_name, r.sample.tier)
        model_vectors.setdefault(r.model, {}).setdefault(key, []).append(r.score.normalized)

    # Average within each (task, tier) group
    model_means: dict[str, dict[tuple[str, str], float]] = {}
    for model, groups in model_vectors.items():
        model_means[model] = {
            key: statistics.mean(scores) for key, scores in groups.items()
        }

    # Pairwise correlations
    correlations: list[float] = []
    for i, m1 in enumerate(models):
        for m2 in models[i + 1:]:
            means1 = model_means.get(m1, {})
            means2 = model_means.get(m2, {})
            common_keys = sorted(set(means1.keys()) & set(means2.keys()))
            if len(common_keys) < 3:
                continue
            v1 = [means1[k] for k in common_keys]
            v2 = [means2[k] for k in common_keys]
            corr, _ = spearmanr(v1, v2)
            if not np.isnan(corr):
                correlations.append(float(corr))

    return statistics.mean(correlations) if correlations else 0.0
