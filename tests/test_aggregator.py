"""Tests for statistical aggregator.

Verifies compute_aggregate uses t-distribution for confidence intervals,
handles edge cases (n=1, n=2, identical values, empty list), and that
StatisticalAggregator correctly aggregates CompositeScore and TokenEfficiency
objects across multiple runs.
"""

from __future__ import annotations

import pytest

from claude_benchmark.scoring.aggregator import (
    StatisticalAggregator,
    compute_aggregate,
)
from claude_benchmark.scoring.models import (
    CompositeScore,
    LLMCriterionScore,
    LLMScore,
    StaticScore,
    TokenEfficiency,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_static(
    weighted_total: float = 75.0,
    test_pass_rate: float = 80.0,
    lint_score: float = 70.0,
    complexity_score: float = 65.0,
) -> StaticScore:
    """Create a StaticScore with configurable values."""
    return StaticScore(
        test_pass_rate=test_pass_rate,
        tests_passed=8,
        tests_total=10,
        lint_score=lint_score,
        lint_errors=3,
        complexity_score=complexity_score,
        avg_complexity=8.0,
        weighted_total=weighted_total,
        lines_of_code=100,
    )


def make_llm(
    normalized: float = 60.0,
    average: float = 3.4,
    scores: tuple[int, int, int, int] = (3, 4, 3, 4),
) -> LLMScore:
    """Create an LLMScore with configurable values."""
    criteria = [
        LLMCriterionScore(name="code_readability", score=scores[0], reasoning="OK"),
        LLMCriterionScore(
            name="architecture_quality", score=scores[1], reasoning="OK"
        ),
        LLMCriterionScore(
            name="instruction_adherence", score=scores[2], reasoning="OK"
        ),
        LLMCriterionScore(
            name="correctness_reasoning", score=scores[3], reasoning="OK"
        ),
    ]
    return LLMScore(
        criteria=criteria,
        average=average,
        normalized=normalized,
        model_used="test-model",
    )


def make_composite(
    static_wt: float = 75.0,
    llm_norm: float | None = 60.0,
    test: float = 80.0,
    lint: float = 70.0,
    cx: float = 65.0,
    llm_scores: tuple[int, int, int, int] = (3, 4, 3, 4),
) -> CompositeScore:
    """Create a CompositeScore with configurable values."""
    static = make_static(
        weighted_total=static_wt,
        test_pass_rate=test,
        lint_score=lint,
        complexity_score=cx,
    )

    if llm_norm is not None:
        llm = make_llm(normalized=llm_norm, scores=llm_scores)
        composite = static_wt * 0.5 + llm_norm * 0.5
        return CompositeScore(
            static_score=static,
            llm_score=llm,
            composite=round(composite, 2),
            static_only=False,
        )

    return CompositeScore(
        static_score=static,
        llm_score=None,
        composite=round(static_wt, 2),
        static_only=True,
    )


# ---------------------------------------------------------------------------
# Tests: compute_aggregate function
# ---------------------------------------------------------------------------


class TestComputeAggregate:
    """Tests for the standalone compute_aggregate function."""

    def test_three_values(self) -> None:
        """[70, 80, 90]: n=3, mean=80.0, stdev=10.0."""
        result = compute_aggregate([70.0, 80.0, 90.0])

        assert result.n == 3
        assert result.mean == 80.0
        assert result.stdev == 10.0
        # CI should be wider than [70, 90] due to t-distribution with df=2
        assert result.ci_lower < 70.0
        assert result.ci_upper > 90.0

    def test_single_value(self) -> None:
        """[85]: n=1, mean=85.0, stdev=0.0, CI is point estimate."""
        result = compute_aggregate([85.0])

        assert result.n == 1
        assert result.mean == 85.0
        assert result.stdev == 0.0
        assert result.ci_lower == 85.0
        assert result.ci_upper == 85.0

    def test_two_values(self) -> None:
        """[60, 80]: n=2, mean=70.0. t-dist with df=1 produces very wide CI."""
        result = compute_aggregate([60.0, 80.0])

        assert result.n == 2
        assert result.mean == 70.0
        # With df=1, the CI should be extremely wide
        assert result.ci_lower < 0.0
        assert result.ci_upper > 140.0

    def test_five_values(self) -> None:
        """[72, 75, 78, 80, 85]: n=5, tighter CI than n=3."""
        result = compute_aggregate([72.0, 75.0, 78.0, 80.0, 85.0])

        assert result.n == 5
        assert result.ci_lower < result.mean
        assert result.ci_upper > result.mean
        # CI should be narrower than the n=3 case relative to spread
        assert result.min_val == 72.0
        assert result.max_val == 85.0

    def test_all_identical(self) -> None:
        """[50, 50, 50]: stdev=0, CI equals the mean."""
        result = compute_aggregate([50.0, 50.0, 50.0])

        assert result.n == 3
        assert result.mean == 50.0
        assert result.stdev == 0.0
        assert result.ci_lower == 50.0
        assert result.ci_upper == 50.0

    def test_empty_list(self) -> None:
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot aggregate empty list"):
            compute_aggregate([])

    def test_values_stored(self) -> None:
        """Raw values are stored in the output for transparency."""
        values = [70.0, 80.0, 90.0]
        result = compute_aggregate(values)

        assert result.values == values

    def test_min_max(self) -> None:
        """min_val and max_val are correct."""
        result = compute_aggregate([30.0, 50.0, 70.0, 90.0])

        assert result.min_val == 30.0
        assert result.max_val == 90.0

    def test_rounding(self) -> None:
        """All output values are rounded to 2 decimal places."""
        result = compute_aggregate([33.333, 66.666, 99.999])

        # Check that mean is rounded
        assert result.mean == round(result.mean, 2)
        assert result.stdev == round(result.stdev, 2)
        assert result.ci_lower == round(result.ci_lower, 2)
        assert result.ci_upper == round(result.ci_upper, 2)


# ---------------------------------------------------------------------------
# Tests: StatisticalAggregator.aggregate_run_scores
# ---------------------------------------------------------------------------


class TestAggregateRunScores:
    """Tests for aggregating multiple CompositeScore objects."""

    def test_three_runs_with_llm(self) -> None:
        """3 runs with both static and LLM scores."""
        scores = [
            make_composite(static_wt=70.0, llm_norm=60.0, test=75, lint=65, cx=60),
            make_composite(static_wt=80.0, llm_norm=70.0, test=85, lint=75, cx=70),
            make_composite(static_wt=90.0, llm_norm=80.0, test=95, lint=85, cx=80),
        ]

        agg = StatisticalAggregator()
        result = agg.aggregate_run_scores(scores)

        # Core keys present
        assert "composite" in result
        assert "static_weighted_total" in result
        assert "test_pass_rate" in result
        assert "lint_score" in result
        assert "complexity_score" in result
        assert "llm_normalized" in result

        # Verify composite mean
        expected_composites = [
            70.0 * 0.5 + 60.0 * 0.5,
            80.0 * 0.5 + 70.0 * 0.5,
            90.0 * 0.5 + 80.0 * 0.5,
        ]
        assert result["composite"].n == 3
        assert result["composite"].mean == round(
            sum(expected_composites) / 3, 2
        )

        # Verify static weighted total mean
        assert result["static_weighted_total"].mean == 80.0

        # Verify LLM normalized mean
        assert result["llm_normalized"].mean == 70.0

    def test_all_static_only(self) -> None:
        """All runs are static-only: llm_normalized key should be absent."""
        scores = [
            make_composite(static_wt=70.0, llm_norm=None),
            make_composite(static_wt=80.0, llm_norm=None),
            make_composite(static_wt=90.0, llm_norm=None),
        ]

        agg = StatisticalAggregator()
        result = agg.aggregate_run_scores(scores)

        assert "composite" in result
        assert "static_weighted_total" in result
        assert "llm_normalized" not in result

    def test_mixed_llm_and_static(self) -> None:
        """Mixed runs: llm_normalized only aggregates runs with LLM scores."""
        scores = [
            make_composite(static_wt=70.0, llm_norm=60.0),
            make_composite(static_wt=80.0, llm_norm=None),  # static-only
            make_composite(static_wt=90.0, llm_norm=80.0),
        ]

        agg = StatisticalAggregator()
        result = agg.aggregate_run_scores(scores)

        # llm_normalized should only include the 2 runs with LLM scores
        assert "llm_normalized" in result
        assert result["llm_normalized"].n == 2
        assert result["llm_normalized"].mean == 70.0  # (60 + 80) / 2

    def test_per_criterion_aggregation(self) -> None:
        """Per-criterion LLM scores are aggregated."""
        scores = [
            make_composite(
                static_wt=75.0, llm_norm=50.0, llm_scores=(3, 4, 3, 4)
            ),
            make_composite(
                static_wt=75.0, llm_norm=75.0, llm_scores=(4, 5, 4, 5)
            ),
            make_composite(
                static_wt=75.0, llm_norm=25.0, llm_scores=(2, 3, 2, 3)
            ),
        ]

        agg = StatisticalAggregator()
        result = agg.aggregate_run_scores(scores)

        # Check per-criterion keys exist
        assert "llm_code_readability" in result
        assert "llm_architecture_quality" in result
        assert "llm_instruction_adherence" in result
        assert "llm_correctness_reasoning" in result

        # code_readability: [3, 4, 2] -> mean=3.0
        assert result["llm_code_readability"].mean == 3.0
        # architecture_quality: [4, 5, 3] -> mean=4.0
        assert result["llm_architecture_quality"].mean == 4.0


# ---------------------------------------------------------------------------
# Tests: StatisticalAggregator.aggregate_token_efficiency
# ---------------------------------------------------------------------------


class TestAggregateTokenEfficiency:
    """Tests for aggregating TokenEfficiency objects."""

    def test_three_efficiencies(self) -> None:
        """Aggregate 3 TokenEfficiency objects."""
        efficiencies = [
            TokenEfficiency(
                composite_score=70.0,
                total_tokens=5000,
                claudemd_tokens=1000,
                task_io_tokens=4000,
                points_per_1k_tokens=14.0,
            ),
            TokenEfficiency(
                composite_score=80.0,
                total_tokens=4000,
                claudemd_tokens=1000,
                task_io_tokens=3000,
                points_per_1k_tokens=20.0,
            ),
            TokenEfficiency(
                composite_score=90.0,
                total_tokens=6000,
                claudemd_tokens=2000,
                task_io_tokens=4000,
                points_per_1k_tokens=15.0,
            ),
        ]

        agg = StatisticalAggregator()
        result = agg.aggregate_token_efficiency(efficiencies)

        assert result.n == 3
        # Mean of [14.0, 20.0, 15.0] = 49/3 = 16.333...
        assert result.mean == 16.33
        assert result.min_val == 14.0
        assert result.max_val == 20.0

    def test_single_efficiency(self) -> None:
        """Single TokenEfficiency: point estimate."""
        efficiencies = [
            TokenEfficiency(
                composite_score=70.0,
                total_tokens=5000,
                claudemd_tokens=1000,
                task_io_tokens=4000,
                points_per_1k_tokens=14.0,
            ),
        ]

        agg = StatisticalAggregator()
        result = agg.aggregate_token_efficiency(efficiencies)

        assert result.n == 1
        assert result.mean == 14.0
        assert result.stdev == 0.0
        assert result.ci_lower == 14.0
        assert result.ci_upper == 14.0
