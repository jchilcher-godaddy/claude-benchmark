"""Tests for calibration metrics computation."""

import pytest

from claude_benchmark.calibration.degrader import CalibrationSample
from claude_benchmark.calibration.metrics import (
    CalibrationReport,
    ModelMetrics,
    _cohens_d,
    compute_calibration_report,
)
from claude_benchmark.calibration.runner import CalibrationResults, ScoringResult
from claude_benchmark.scoring.models import LLMCriterionScore, LLMScore


def _make_score(normalized: float, criteria_score: int = 4) -> LLMScore:
    """Helper to create an LLMScore with uniform criterion scores."""
    criteria = [
        LLMCriterionScore(name="code_readability", score=criteria_score, reasoning="ok"),
        LLMCriterionScore(name="architecture_quality", score=criteria_score, reasoning="ok"),
        LLMCriterionScore(name="instruction_adherence", score=criteria_score, reasoning="ok"),
        LLMCriterionScore(name="correctness_reasoning", score=criteria_score, reasoning="ok"),
    ]
    avg = criteria_score
    return LLMScore(
        criteria=criteria,
        average=float(avg),
        normalized=normalized,
        model_used="test",
    )


def _make_sample(task_name: str, tier: str) -> CalibrationSample:
    return CalibrationSample(
        task_name=task_name,
        tier=tier,
        code="pass",
        task_description="test",
        reference_solution="pass",
    )


class TestCohensD:
    def test_identical_groups_return_zero(self):
        assert _cohens_d([3.0, 3.0, 3.0], [3.0, 3.0, 3.0]) == 0.0

    def test_different_groups_return_nonzero(self):
        d = _cohens_d([5.0, 5.0, 5.0], [1.0, 1.0, 1.0])
        assert d > 0

    def test_small_groups(self):
        assert _cohens_d([1.0], [2.0]) == 0.0  # need at least 2 per group


class TestZeroVariance:
    def test_deterministic_scores_give_100_pct(self):
        """When all reps produce the same score, determinism should be 100%."""
        sample_gold = _make_sample("t1", "gold")
        sample_severe = _make_sample("t1", "severe")

        results = []
        for rep in range(3):
            results.append(ScoringResult(
                sample=sample_gold, model="haiku", rep=rep,
                score=_make_score(75.0, criteria_score=4),
            ))
            results.append(ScoringResult(
                sample=sample_severe, model="haiku", rep=rep,
                score=_make_score(25.0, criteria_score=2),
            ))

        cal = CalibrationResults(
            results=results,
            models=["haiku"],
            samples=[sample_gold, sample_severe],
            reps_per_model={"haiku": 3},
        )

        report = compute_calibration_report(cal)
        mm = report.model_metrics["haiku"]
        assert mm.pct_deterministic == 100.0
        assert mm.mean_variance == 0.0


class TestPerfectTierOrdering:
    def test_spearman_correlation_is_high(self):
        """When gold > mild > severe consistently, tier correlation should be ~1.0."""
        samples = [
            _make_sample("t1", "gold"),
            _make_sample("t1", "mild"),
            _make_sample("t1", "severe"),
        ]
        tier_scores = {"gold": 90.0, "mild": 50.0, "severe": 10.0}
        tier_criterion = {"gold": 5, "mild": 3, "severe": 1}

        results = []
        for s in samples:
            for rep in range(3):
                results.append(ScoringResult(
                    sample=s, model="haiku", rep=rep,
                    score=_make_score(
                        tier_scores[s.tier],
                        criteria_score=tier_criterion[s.tier],
                    ),
                ))

        cal = CalibrationResults(
            results=results,
            models=["haiku"],
            samples=samples,
            reps_per_model={"haiku": 3},
        )

        report = compute_calibration_report(cal)
        mm = report.model_metrics["haiku"]
        assert mm.tier_rank_correlation > 0.9


class TestRecommendation:
    def test_highest_discrimination_model_wins(self):
        """Model with better discrimination should be recommended."""
        samples = [
            _make_sample("t1", "gold"),
            _make_sample("t1", "severe"),
        ]

        results = []
        # Model A: high discrimination (gold=90, severe=10)
        for rep in range(3):
            results.append(ScoringResult(
                sample=samples[0], model="model_a", rep=rep,
                score=_make_score(90.0, criteria_score=5),
            ))
            results.append(ScoringResult(
                sample=samples[1], model="model_a", rep=rep,
                score=_make_score(10.0, criteria_score=1),
            ))

        # Model B: no discrimination (scores same for both tiers)
        for rep in range(3):
            results.append(ScoringResult(
                sample=samples[0], model="model_b", rep=rep,
                score=_make_score(50.0, criteria_score=3),
            ))
            results.append(ScoringResult(
                sample=samples[1], model="model_b", rep=rep,
                score=_make_score(50.0, criteria_score=3),
            ))

        cal = CalibrationResults(
            results=results,
            models=["model_a", "model_b"],
            samples=samples,
            reps_per_model={"model_a": 3, "model_b": 3},
        )

        report = compute_calibration_report(cal)
        assert report.recommended_model == "model_a"
        assert report.model_metrics["model_a"].recommendation_score > report.model_metrics["model_b"].recommendation_score


class TestFailedResults:
    def test_handles_none_scores_gracefully(self):
        """Results with score=None (failed API calls) should not crash."""
        sample = _make_sample("t1", "gold")

        results = [
            ScoringResult(sample=sample, model="haiku", rep=0, score=None, error="API error"),
            ScoringResult(sample=sample, model="haiku", rep=1, score=None, error="API error"),
        ]

        cal = CalibrationResults(
            results=results,
            models=["haiku"],
            samples=[sample],
            reps_per_model={"haiku": 2},
        )

        # Should not raise
        report = compute_calibration_report(cal)
        assert "haiku" in report.model_metrics
