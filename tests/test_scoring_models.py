"""Tests for scoring Pydantic models and error classes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from claude_benchmark.scoring import (
    AggregateStats,
    CompositeScore,
    LLMCriterionScore,
    LLMJudgeError,
    LLMScore,
    ScoringError,
    ScoringWeights,
    StaticAnalysisError,
    StaticScore,
    TokenEfficiency,
)


# --- Error hierarchy tests ---


class TestScoringErrors:
    def test_scoring_error_base(self):
        err = ScoringError("something broke")
        assert str(err) == "something broke"
        assert err.message == "something broke"

    def test_static_analysis_error_inherits(self):
        err = StaticAnalysisError("ruff crashed", tool="ruff")
        assert isinstance(err, ScoringError)
        assert err.tool == "ruff"
        assert err.message == "ruff crashed"

    def test_static_analysis_error_without_tool(self):
        err = StaticAnalysisError("unknown tool failure")
        assert err.tool is None

    def test_llm_judge_error_inherits(self):
        err = LLMJudgeError("API timeout", retry_attempted=True)
        assert isinstance(err, ScoringError)
        assert err.retry_attempted is True
        assert err.message == "API timeout"

    def test_llm_judge_error_default_retry(self):
        err = LLMJudgeError("bad response")
        assert err.retry_attempted is False


# --- StaticScore tests ---


class TestStaticScore:
    def test_valid_score(self):
        score = StaticScore(
            test_pass_rate=80.0,
            tests_passed=8,
            tests_total=10,
            lint_score=95.0,
            lint_errors=2,
            complexity_score=85.0,
            avg_complexity=3.5,
            weighted_total=86.0,
            lines_of_code=150,
        )
        assert score.test_pass_rate == 80.0
        assert score.tests_passed == 8
        assert score.tests_total == 10
        assert score.lint_score == 95.0
        assert score.lint_errors == 2
        assert score.complexity_score == 85.0
        assert score.avg_complexity == 3.5
        assert score.weighted_total == 86.0
        assert score.lines_of_code == 150
        assert score.lint_details == []
        assert score.complexity_details == []

    def test_zero_score(self):
        score = StaticScore(
            test_pass_rate=0,
            tests_passed=0,
            tests_total=0,
            lint_score=0,
            lint_errors=0,
            complexity_score=0,
            avg_complexity=0,
            weighted_total=0,
        )
        assert score.weighted_total == 0

    def test_perfect_score(self):
        score = StaticScore(
            test_pass_rate=100,
            tests_passed=10,
            tests_total=10,
            lint_score=100,
            lint_errors=0,
            complexity_score=100,
            avg_complexity=1.0,
            weighted_total=100,
        )
        assert score.weighted_total == 100

    def test_rejects_negative_test_pass_rate(self):
        with pytest.raises(ValidationError):
            StaticScore(
                test_pass_rate=-1,
                tests_passed=0,
                tests_total=0,
                lint_score=50,
                lint_errors=0,
                complexity_score=50,
                avg_complexity=0,
                weighted_total=50,
            )

    def test_rejects_over_100_lint_score(self):
        with pytest.raises(ValidationError):
            StaticScore(
                test_pass_rate=50,
                tests_passed=5,
                tests_total=10,
                lint_score=101,
                lint_errors=0,
                complexity_score=50,
                avg_complexity=0,
                weighted_total=50,
            )

    def test_rejects_negative_lint_errors(self):
        with pytest.raises(ValidationError):
            StaticScore(
                test_pass_rate=50,
                tests_passed=5,
                tests_total=10,
                lint_score=50,
                lint_errors=-1,
                complexity_score=50,
                avg_complexity=0,
                weighted_total=50,
            )

    def test_rejects_over_100_weighted_total(self):
        with pytest.raises(ValidationError):
            StaticScore(
                test_pass_rate=100,
                tests_passed=10,
                tests_total=10,
                lint_score=100,
                lint_errors=0,
                complexity_score=100,
                avg_complexity=0,
                weighted_total=101,
            )

    def test_with_lint_details(self):
        score = StaticScore(
            test_pass_rate=50,
            tests_passed=5,
            tests_total=10,
            lint_score=80,
            lint_errors=3,
            lint_details=[{"rule": "E501", "message": "line too long"}],
            complexity_score=70,
            avg_complexity=5.0,
            weighted_total=63,
        )
        assert len(score.lint_details) == 1


# --- LLMCriterionScore tests ---


class TestLLMCriterionScore:
    def test_valid_score(self):
        cs = LLMCriterionScore(name="readability", score=4, reasoning="Clean code structure")
        assert cs.score == 4
        assert cs.name == "readability"

    def test_accepts_score_1(self):
        cs = LLMCriterionScore(name="test", score=1, reasoning="Poor")
        assert cs.score == 1

    def test_accepts_score_5(self):
        cs = LLMCriterionScore(name="test", score=5, reasoning="Excellent")
        assert cs.score == 5

    def test_rejects_score_0(self):
        with pytest.raises(ValidationError):
            LLMCriterionScore(name="test", score=0, reasoning="Invalid")

    def test_rejects_score_6(self):
        with pytest.raises(ValidationError):
            LLMCriterionScore(name="test", score=6, reasoning="Invalid")


# --- LLMScore tests ---


class TestLLMScore:
    def test_valid_llm_score(self):
        score = LLMScore(
            criteria=[
                LLMCriterionScore(name="readability", score=4, reasoning="Clean"),
                LLMCriterionScore(name="architecture", score=3, reasoning="OK"),
            ],
            average=3.5,
            normalized=62.5,
            model_used="haiku",
        )
        assert score.average == 3.5
        assert score.normalized == 62.5
        assert score.model_used == "haiku"

    def test_rejects_average_below_1(self):
        with pytest.raises(ValidationError):
            LLMScore(
                criteria=[],
                average=0.5,
                normalized=0,
                model_used="test-model",
            )

    def test_rejects_average_above_5(self):
        with pytest.raises(ValidationError):
            LLMScore(
                criteria=[],
                average=5.1,
                normalized=100,
                model_used="test-model",
            )

    def test_rejects_normalized_above_100(self):
        with pytest.raises(ValidationError):
            LLMScore(
                criteria=[],
                average=5.0,
                normalized=101,
                model_used="test-model",
            )


# --- CompositeScore tests ---


class TestCompositeScore:
    def _make_static(self, **kwargs) -> StaticScore:
        defaults = dict(
            test_pass_rate=80,
            tests_passed=8,
            tests_total=10,
            lint_score=90,
            lint_errors=2,
            complexity_score=85,
            avg_complexity=3.5,
            weighted_total=84.5,
        )
        defaults.update(kwargs)
        return StaticScore(**defaults)

    def test_with_llm_score(self):
        static = self._make_static()
        llm = LLMScore(
            criteria=[LLMCriterionScore(name="test", score=4, reasoning="Good")],
            average=4.0,
            normalized=75.0,
            model_used="test-model",
        )
        composite = CompositeScore(
            static_score=static,
            llm_score=llm,
            composite=79.75,
            static_only=False,
        )
        assert composite.llm_score is not None
        assert composite.static_only is False

    def test_without_llm_score(self):
        static = self._make_static()
        composite = CompositeScore(
            static_score=static,
            composite=84.5,
            static_only=True,
        )
        assert composite.llm_score is None
        assert composite.static_only is True

    def test_rejects_composite_over_100(self):
        static = self._make_static()
        with pytest.raises(ValidationError):
            CompositeScore(
                static_score=static,
                composite=101,
                static_only=True,
            )


# --- AggregateStats tests ---


class TestAggregateStats:
    def test_valid_stats(self):
        stats = AggregateStats(
            n=5,
            mean=82.5,
            stdev=3.2,
            ci_lower=78.0,
            ci_upper=87.0,
            min_val=78.0,
            max_val=87.0,
            values=[78.0, 80.0, 82.0, 85.0, 87.0],
        )
        assert stats.n == 5
        assert stats.mean == 82.5
        assert len(stats.values) == 5

    def test_single_run(self):
        stats = AggregateStats(
            n=1,
            mean=85.0,
            stdev=0.0,
            ci_lower=85.0,
            ci_upper=85.0,
            min_val=85.0,
            max_val=85.0,
            values=[85.0],
        )
        assert stats.n == 1

    def test_rejects_n_zero(self):
        with pytest.raises(ValidationError):
            AggregateStats(
                n=0,
                mean=0,
                stdev=0,
                ci_lower=0,
                ci_upper=0,
                min_val=0,
                max_val=0,
            )

    def test_rejects_negative_stdev(self):
        with pytest.raises(ValidationError):
            AggregateStats(
                n=3,
                mean=50,
                stdev=-1,
                ci_lower=40,
                ci_upper=60,
                min_val=40,
                max_val=60,
            )

    def test_default_empty_values(self):
        stats = AggregateStats(
            n=1,
            mean=50,
            stdev=0,
            ci_lower=50,
            ci_upper=50,
            min_val=50,
            max_val=50,
        )
        assert stats.values == []


# --- TokenEfficiency tests ---


class TestTokenEfficiency:
    def test_computation_with_known_values(self):
        te = TokenEfficiency(
            composite_score=80.0,
            total_tokens=10000,
            claudemd_tokens=3000,
            task_io_tokens=7000,
            points_per_1k_tokens=8.0,
        )
        assert te.points_per_1k_tokens == 8.0
        assert te.total_tokens == 10000
        # Verify formula: (80 / 10000) * 1000 = 8.0
        expected = (te.composite_score / te.total_tokens) * 1000
        assert abs(te.points_per_1k_tokens - expected) < 0.01

    def test_zero_tokens(self):
        te = TokenEfficiency(
            composite_score=50.0,
            total_tokens=0,
            claudemd_tokens=0,
            task_io_tokens=0,
            points_per_1k_tokens=0.0,
        )
        assert te.points_per_1k_tokens == 0.0

    def test_high_efficiency(self):
        te = TokenEfficiency(
            composite_score=95.0,
            total_tokens=5000,
            claudemd_tokens=1000,
            task_io_tokens=4000,
            points_per_1k_tokens=19.0,
        )
        assert te.points_per_1k_tokens == 19.0


# --- ScoringWeights tests ---


class TestScoringWeights:
    def test_defaults_sum_to_1(self):
        w = ScoringWeights()
        total = w.test_pass_rate + w.lint_score + w.complexity_score
        assert abs(total - 1.0) < 0.001

    def test_default_values(self):
        w = ScoringWeights()
        assert w.test_pass_rate == 0.50
        assert w.lint_score == 0.30
        assert w.complexity_score == 0.20

    def test_custom_weights_summing_to_1(self):
        w = ScoringWeights(test_pass_rate=0.3, lint_score=0.2, complexity_score=0.5)
        assert w.test_pass_rate == 0.3
        assert w.lint_score == 0.2
        assert w.complexity_score == 0.5

    def test_rejects_weights_not_summing_to_1(self):
        with pytest.raises(ValidationError, match="Weights must sum to 1.0"):
            ScoringWeights(test_pass_rate=0.5, lint_score=0.5, complexity_score=0.5)

    def test_rejects_all_zero_weights(self):
        with pytest.raises(ValidationError, match="Weights must sum to 1.0"):
            ScoringWeights(test_pass_rate=0.0, lint_score=0.0, complexity_score=0.0)

    def test_accepts_within_tolerance(self):
        # 0.333 + 0.333 + 0.334 = 1.000, should pass
        w = ScoringWeights(test_pass_rate=0.333, lint_score=0.333, complexity_score=0.334)
        assert w.test_pass_rate == 0.333

    def test_rejects_individual_weight_over_1(self):
        with pytest.raises(ValidationError):
            ScoringWeights(test_pass_rate=1.1, lint_score=0.0, complexity_score=0.0)

    def test_rejects_negative_weight(self):
        with pytest.raises(ValidationError):
            ScoringWeights(test_pass_rate=-0.1, lint_score=0.5, complexity_score=0.6)


# --- Import tests ---


class TestImports:
    def test_package_imports(self):
        from claude_benchmark.scoring import (
            AggregateStats,
            CompositeScore,
            LLMCriterionScore,
            LLMJudgeError,
            LLMScore,
            ScoringError,
            ScoringWeights,
            StaticAnalysisError,
            StaticScore,
            TokenEfficiency,
        )

        # Verify all are accessible
        assert StaticScore is not None
        assert LLMCriterionScore is not None
        assert LLMScore is not None
        assert CompositeScore is not None
        assert AggregateStats is not None
        assert TokenEfficiency is not None
        assert ScoringWeights is not None
        assert ScoringError is not None
        assert StaticAnalysisError is not None
        assert LLMJudgeError is not None
