"""Tests for composite scorer.

Verifies the CompositeScorer correctly combines static and LLM scores
with 50/50 weighting, handles static-only fallback, and manages edge cases.
"""

from __future__ import annotations

import pytest

from claude_benchmark.scoring.composite import CompositeScorer
from claude_benchmark.scoring.models import (
    LLMCriterionScore,
    LLMScore,
    StaticScore,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_static(weighted_total: float = 80.0) -> StaticScore:
    """Create a StaticScore with the given weighted_total."""
    return StaticScore(
        test_pass_rate=80.0,
        tests_passed=8,
        tests_total=10,
        lint_score=70.0,
        lint_errors=3,
        complexity_score=65.0,
        avg_complexity=8.0,
        weighted_total=weighted_total,
        lines_of_code=100,
    )


def make_llm(normalized: float = 60.0, average: float = 3.4) -> LLMScore:
    """Create an LLMScore with the given normalized score."""
    return LLMScore(
        criteria=[
            LLMCriterionScore(name="code_readability", score=3, reasoning="Decent"),
            LLMCriterionScore(name="architecture_quality", score=4, reasoning="Good"),
            LLMCriterionScore(name="instruction_adherence", score=3, reasoning="OK"),
            LLMCriterionScore(name="correctness_reasoning", score=4, reasoning="Solid"),
        ],
        average=average,
        normalized=normalized,
        model_used="test-model",
    )


def make_llm_all_5() -> LLMScore:
    """LLM score with all criteria at maximum (5)."""
    return LLMScore(
        criteria=[
            LLMCriterionScore(name="code_readability", score=5, reasoning="Excellent"),
            LLMCriterionScore(
                name="architecture_quality", score=5, reasoning="Excellent"
            ),
            LLMCriterionScore(
                name="instruction_adherence", score=5, reasoning="Excellent"
            ),
            LLMCriterionScore(
                name="correctness_reasoning", score=5, reasoning="Excellent"
            ),
        ],
        average=5.0,
        normalized=100.0,
        model_used="test-model",
    )


def make_llm_all_1() -> LLMScore:
    """LLM score with all criteria at minimum (1)."""
    return LLMScore(
        criteria=[
            LLMCriterionScore(name="code_readability", score=1, reasoning="Poor"),
            LLMCriterionScore(name="architecture_quality", score=1, reasoning="Poor"),
            LLMCriterionScore(name="instruction_adherence", score=1, reasoning="Poor"),
            LLMCriterionScore(name="correctness_reasoning", score=1, reasoning="Poor"),
        ],
        average=1.0,
        normalized=0.0,
        model_used="test-model",
    )


# ---------------------------------------------------------------------------
# Tests: Full composite (static + LLM)
# ---------------------------------------------------------------------------


class TestFullComposite:
    """Tests for composite scoring with both static and LLM scores."""

    def test_basic_composite(self) -> None:
        """80 * 0.5 + 60 * 0.5 = 70.0."""
        scorer = CompositeScorer()
        result = scorer.compute(make_static(80.0), make_llm(60.0))

        assert result.composite == 70.0
        assert result.static_only is False
        assert result.llm_score is not None

    def test_static_score_preserved(self) -> None:
        """Static score object is preserved in the composite."""
        scorer = CompositeScorer()
        static = make_static(80.0)
        result = scorer.compute(static, make_llm(60.0))

        assert result.static_score.weighted_total == 80.0
        assert result.static_score.test_pass_rate == 80.0

    def test_llm_score_preserved(self) -> None:
        """LLM score object is preserved in the composite."""
        scorer = CompositeScorer()
        llm = make_llm(60.0)
        result = scorer.compute(make_static(), llm)

        assert result.llm_score is not None
        assert result.llm_score.normalized == 60.0

    def test_perfect_llm(self) -> None:
        """All criteria score 5: normalized=100 -> composite = static*0.5 + 100*0.5."""
        scorer = CompositeScorer()
        static = make_static(80.0)
        result = scorer.compute(static, make_llm_all_5())

        assert result.composite == 80.0 * 0.5 + 100.0 * 0.5  # 90.0
        assert result.static_only is False

    def test_minimum_llm(self) -> None:
        """All criteria score 1: normalized=0 -> composite = static*0.5 + 0*0.5."""
        scorer = CompositeScorer()
        static = make_static(80.0)
        result = scorer.compute(static, make_llm_all_1())

        assert result.composite == 80.0 * 0.5 + 0.0 * 0.5  # 40.0
        assert result.static_only is False


# ---------------------------------------------------------------------------
# Tests: Static-only mode
# ---------------------------------------------------------------------------


class TestStaticOnly:
    """Tests for static-only mode when LLM is unavailable."""

    def test_static_only_score(self) -> None:
        """Static only: composite = weighted_total."""
        scorer = CompositeScorer()
        result = scorer.compute(make_static(80.0), llm=None)

        assert result.composite == 80.0
        assert result.static_only is True
        assert result.llm_score is None

    def test_static_only_flag(self) -> None:
        """static_only is True when LLM is None."""
        scorer = CompositeScorer()
        result = scorer.compute(make_static(50.0))

        assert result.static_only is True

    def test_llm_provided_flag(self) -> None:
        """static_only is False when LLM is provided."""
        scorer = CompositeScorer()
        result = scorer.compute(make_static(50.0), make_llm(50.0))

        assert result.static_only is False


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for composite scoring."""

    def test_both_zero(self) -> None:
        """static.weighted_total=0 and llm.normalized=0 -> composite=0."""
        scorer = CompositeScorer()
        result = scorer.compute(make_static(0.0), make_llm(0.0, average=1.0))

        assert result.composite == 0.0

    def test_both_max(self) -> None:
        """static.weighted_total=100 and llm.normalized=100 -> composite=100."""
        scorer = CompositeScorer()
        result = scorer.compute(make_static(100.0), make_llm_all_5())

        assert result.composite == 100.0

    def test_static_only_zero(self) -> None:
        """Static-only with weighted_total=0 -> composite=0."""
        scorer = CompositeScorer()
        result = scorer.compute(make_static(0.0))

        assert result.composite == 0.0
        assert result.static_only is True

    def test_static_only_max(self) -> None:
        """Static-only with weighted_total=100 -> composite=100."""
        scorer = CompositeScorer()
        result = scorer.compute(make_static(100.0))

        assert result.composite == 100.0
        assert result.static_only is True


# ---------------------------------------------------------------------------
# Tests: Weight validation
# ---------------------------------------------------------------------------


class TestWeightValidation:
    """Tests for CompositeScorer weight validation."""

    def test_default_weights(self) -> None:
        """Default weights are 0.5 / 0.5."""
        scorer = CompositeScorer()
        assert scorer.static_weight == 0.5
        assert scorer.llm_weight == 0.5

    def test_custom_weights(self) -> None:
        """Custom weights that sum to 1.0 are accepted."""
        scorer = CompositeScorer(static_weight=0.7, llm_weight=0.3)
        assert scorer.static_weight == 0.7
        assert scorer.llm_weight == 0.3

    def test_invalid_weights(self) -> None:
        """Weights that don't sum to 1.0 raise ValueError."""
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            CompositeScorer(static_weight=0.6, llm_weight=0.6)

    def test_custom_weights_composite(self) -> None:
        """Custom weights produce correct composite: 80*0.7 + 60*0.3 = 74.0."""
        scorer = CompositeScorer(static_weight=0.7, llm_weight=0.3)
        result = scorer.compute(make_static(80.0), make_llm(60.0))

        assert result.composite == 74.0
