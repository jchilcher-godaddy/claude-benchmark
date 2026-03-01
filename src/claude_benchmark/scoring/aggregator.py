"""Statistical aggregator for claude-benchmark.

Aggregates scores across multiple benchmark runs using mean, standard
deviation, and 95% confidence intervals via t-distribution for small
samples. Provides both a standalone compute_aggregate function and a
StatisticalAggregator class for aggregating CompositeScore objects.
"""

from __future__ import annotations

import math
import statistics

from scipy.stats import t as t_dist

from .models import AggregateStats, CompositeScore, TokenEfficiency


def compute_aggregate(
    values: list[float],
    confidence: float = 0.95,
) -> AggregateStats:
    """Compute statistical aggregates for a list of values.

    Uses t-distribution for confidence intervals, which is appropriate
    for small sample sizes (n < 30). For n=1, returns point estimate
    with stdev=0 and CI equal to the single value.

    Args:
        values: List of numeric values to aggregate.
        confidence: Confidence level for the interval (default 0.95).

    Returns:
        AggregateStats with mean, stdev, CI bounds, min/max, and raw values.

    Raises:
        ValueError: If values is empty.
    """
    n = len(values)

    if n == 0:
        raise ValueError("Cannot aggregate empty list")

    if n == 1:
        val = values[0]
        return AggregateStats(
            n=1,
            mean=round(val, 2),
            stdev=0.0,
            ci_lower=round(val, 2),
            ci_upper=round(val, 2),
            min_val=round(val, 2),
            max_val=round(val, 2),
            values=values,
        )

    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    se = sd / math.sqrt(n)

    if se == 0:
        # All values identical
        ci_lower = mean
        ci_upper = mean
    else:
        ci_lower, ci_upper = t_dist.interval(confidence, df=n - 1, loc=mean, scale=se)

    return AggregateStats(
        n=n,
        mean=round(mean, 2),
        stdev=round(sd, 2),
        ci_lower=round(ci_lower, 2),
        ci_upper=round(ci_upper, 2),
        min_val=round(min(values), 2),
        max_val=round(max(values), 2),
        values=values,
    )


class StatisticalAggregator:
    """Aggregates multiple CompositeScore objects from repeated runs.

    Computes statistical summaries (mean, stdev, 95% CI) for each
    scoring dimension: composite, static components, LLM scores,
    and per-criterion LLM scores.
    """

    def aggregate_run_scores(
        self,
        composite_scores: list[CompositeScore],
    ) -> dict[str, AggregateStats]:
        """Aggregate multiple CompositeScore objects from repeated runs.

        Computes AggregateStats for:
        - composite: overall composite scores
        - static_weighted_total: static weighted totals
        - test_pass_rate: test pass rates
        - lint_score: lint scores
        - complexity_score: complexity scores
        - llm_normalized: LLM normalized scores (only if any run has LLM)
        - Per LLM criterion: individual criterion scores (if LLM scores exist)

        Args:
            composite_scores: List of CompositeScore objects from multiple runs.

        Returns:
            Dict mapping metric name to AggregateStats.
        """
        result: dict[str, AggregateStats] = {}

        # Core metrics always present
        result["composite"] = compute_aggregate(
            [cs.composite for cs in composite_scores]
        )
        result["static_weighted_total"] = compute_aggregate(
            [cs.static_score.weighted_total for cs in composite_scores]
        )
        result["test_pass_rate"] = compute_aggregate(
            [cs.static_score.test_pass_rate for cs in composite_scores]
        )
        result["lint_score"] = compute_aggregate(
            [cs.static_score.lint_score for cs in composite_scores]
        )
        result["complexity_score"] = compute_aggregate(
            [cs.static_score.complexity_score for cs in composite_scores]
        )

        # LLM metrics only if at least one run has LLM scores
        llm_scores = [
            cs.llm_score for cs in composite_scores if cs.llm_score is not None
        ]
        if llm_scores:
            result["llm_normalized"] = compute_aggregate(
                [ls.normalized for ls in llm_scores]
            )

            # Per-criterion aggregation
            # Collect all criterion names from the first LLM score
            criterion_names = [c.name for c in llm_scores[0].criteria]
            for criterion_name in criterion_names:
                criterion_values = []
                for ls in llm_scores:
                    for c in ls.criteria:
                        if c.name == criterion_name:
                            criterion_values.append(float(c.score))
                            break
                if criterion_values:
                    result[f"llm_{criterion_name}"] = compute_aggregate(
                        criterion_values
                    )

        return result

    def aggregate_token_efficiency(
        self,
        efficiencies: list[TokenEfficiency],
    ) -> AggregateStats:
        """Aggregate token efficiency across multiple runs.

        Args:
            efficiencies: List of TokenEfficiency objects.

        Returns:
            AggregateStats for points_per_1k_tokens values.
        """
        return compute_aggregate(
            [e.points_per_1k_tokens for e in efficiencies]
        )
