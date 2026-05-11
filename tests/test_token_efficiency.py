"""Tests for token efficiency calculator.

Verifies compute_token_efficiency produces correct points-per-1K-tokens
ratios, cost-weighted points-per-dollar metrics, handles zero-token edge
cases, and correctly tracks token breakdowns.
"""

from __future__ import annotations

from claude_benchmark.scoring.token_efficiency import compute_token_efficiency


# ---------------------------------------------------------------------------
# Tests: Known values (points_per_1k_tokens)
# ---------------------------------------------------------------------------


class TestKnownValues:
    """Tests with known expected outputs."""

    def test_basic_efficiency(self) -> None:
        """score=70, claudemd=1000, task_io=4000 -> total=5000 -> 14.0 pts/1K."""
        result = compute_token_efficiency(
            composite_score=70.0,
            claudemd_context_tokens=1000,
            task_io_tokens=4000,
        )

        assert result.points_per_1k_tokens == 14.0
        assert result.total_tokens == 5000
        assert result.composite_score == 70.0

    def test_high_efficiency(self) -> None:
        """score=90, 1000 total tokens -> 90.0 pts/1K."""
        result = compute_token_efficiency(
            composite_score=90.0,
            claudemd_context_tokens=500,
            task_io_tokens=500,
        )

        assert result.points_per_1k_tokens == 90.0
        assert result.total_tokens == 1000

    def test_low_efficiency(self) -> None:
        """score=10, 50000 total tokens -> 0.2 pts/1K."""
        result = compute_token_efficiency(
            composite_score=10.0,
            claudemd_context_tokens=10000,
            task_io_tokens=40000,
        )

        assert result.points_per_1k_tokens == 0.2
        assert result.total_tokens == 50000


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for token efficiency."""

    def test_zero_total_tokens(self) -> None:
        """Zero total tokens: should return 0.0 (no division by zero)."""
        result = compute_token_efficiency(
            composite_score=50.0,
            claudemd_context_tokens=0,
            task_io_tokens=0,
        )

        assert result.points_per_1k_tokens == 0.0
        assert result.total_tokens == 0

    def test_zero_score_nonzero_tokens(self) -> None:
        """score=0 with non-zero tokens: 0.0 pts/1K."""
        result = compute_token_efficiency(
            composite_score=0.0,
            claudemd_context_tokens=500,
            task_io_tokens=500,
        )

        assert result.points_per_1k_tokens == 0.0
        assert result.total_tokens == 1000

    def test_perfect_score(self) -> None:
        """score=100, moderate tokens."""
        result = compute_token_efficiency(
            composite_score=100.0,
            claudemd_context_tokens=2000,
            task_io_tokens=3000,
        )

        assert result.points_per_1k_tokens == 20.0
        assert result.total_tokens == 5000


# ---------------------------------------------------------------------------
# Tests: Token breakdown
# ---------------------------------------------------------------------------


class TestTokenBreakdown:
    """Tests that token breakdown fields are stored correctly."""

    def test_token_fields(self) -> None:
        """claudemd_tokens and task_io_tokens match inputs."""
        result = compute_token_efficiency(
            composite_score=70.0,
            claudemd_context_tokens=1500,
            task_io_tokens=3500,
        )

        assert result.claudemd_tokens == 1500
        assert result.task_io_tokens == 3500
        assert result.total_tokens == 5000

    def test_claudemd_only(self) -> None:
        """Only claudemd tokens, no task IO."""
        result = compute_token_efficiency(
            composite_score=50.0,
            claudemd_context_tokens=2000,
            task_io_tokens=0,
        )

        assert result.claudemd_tokens == 2000
        assert result.task_io_tokens == 0
        assert result.total_tokens == 2000
        assert result.points_per_1k_tokens == 25.0

    def test_task_io_only(self) -> None:
        """Only task IO tokens, no claudemd."""
        result = compute_token_efficiency(
            composite_score=50.0,
            claudemd_context_tokens=0,
            task_io_tokens=2000,
        )

        assert result.claudemd_tokens == 0
        assert result.task_io_tokens == 2000
        assert result.total_tokens == 2000
        assert result.points_per_1k_tokens == 25.0


# ---------------------------------------------------------------------------
# Tests: Cost-weighted efficiency (points_per_dollar)
# ---------------------------------------------------------------------------


class TestCostWeightedEfficiency:
    """Tests for the points_per_dollar metric using model pricing."""

    def test_haiku_cost(self) -> None:
        """Haiku: $1/MTok in, $5/MTok out. 4K in + 2K out = $0.014."""
        result = compute_token_efficiency(
            composite_score=93.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=4000,
            output_tokens=2000,
            model="haiku",
        )

        assert result.input_tokens == 4000
        assert result.output_tokens == 2000
        assert result.model == "haiku"
        # cost = (4000/1M)*1.0 + (2000/1M)*5.0 = 0.004 + 0.01 = 0.014
        assert result.cost_usd == 0.014
        # points_per_dollar = 93.0 / 0.014 = 6642.857...
        assert result.points_per_dollar == 6642.86

    def test_sonnet_cost(self) -> None:
        """Sonnet: $3/MTok in, $15/MTok out. 4K in + 2K out = $0.042."""
        result = compute_token_efficiency(
            composite_score=93.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=4000,
            output_tokens=2000,
            model="sonnet",
        )

        assert result.cost_usd == 0.042
        # 93.0 / 0.042 = 2214.285...
        assert result.points_per_dollar == 2214.29

    def test_opus_cost(self) -> None:
        """Opus: $5/MTok in, $25/MTok out. 4K in + 2K out = $0.07."""
        result = compute_token_efficiency(
            composite_score=93.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=4000,
            output_tokens=2000,
            model="opus",
        )

        assert result.cost_usd == 0.07
        # 93.0 / 0.07 = 1328.571...
        assert result.points_per_dollar == 1328.57

    def test_haiku_much_higher_ppd_than_opus(self) -> None:
        """Same quality, haiku should be ~5x more cost-efficient than opus."""
        haiku = compute_token_efficiency(
            composite_score=93.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=4000,
            output_tokens=2000,
            model="haiku",
        )
        opus = compute_token_efficiency(
            composite_score=93.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=4000,
            output_tokens=2000,
            model="opus",
        )

        assert haiku.points_per_dollar > opus.points_per_dollar * 4

    def test_backward_compat_no_io_tokens(self) -> None:
        """Without input/output tokens, cost fields default to 0."""
        result = compute_token_efficiency(
            composite_score=70.0,
            claudemd_context_tokens=1000,
            task_io_tokens=4000,
        )

        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cost_usd == 0.0
        assert result.points_per_dollar == 0.0
        assert result.model == ""
        # Original metric still works
        assert result.points_per_1k_tokens == 14.0

    def test_unknown_model_falls_back_to_sonnet(self) -> None:
        """Unknown model name uses sonnet pricing."""
        result = compute_token_efficiency(
            composite_score=93.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=4000,
            output_tokens=2000,
            model="unknown-model-v9",
        )

        sonnet = compute_token_efficiency(
            composite_score=93.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=4000,
            output_tokens=2000,
            model="sonnet",
        )

        assert result.cost_usd == sonnet.cost_usd
        assert result.points_per_dollar == sonnet.points_per_dollar

    def test_zero_score_with_cost(self) -> None:
        """score=0 with valid cost: points_per_dollar should be 0."""
        result = compute_token_efficiency(
            composite_score=0.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=4000,
            output_tokens=2000,
            model="haiku",
        )

        assert result.cost_usd == 0.014
        assert result.points_per_dollar == 0.0

    def test_output_heavy_run_costs_more(self) -> None:
        """Output-heavy runs should cost more than input-heavy runs."""
        output_heavy = compute_token_efficiency(
            composite_score=90.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=1000,
            output_tokens=5000,
            model="haiku",
        )
        input_heavy = compute_token_efficiency(
            composite_score=90.0,
            claudemd_context_tokens=0,
            task_io_tokens=6000,
            input_tokens=5000,
            output_tokens=1000,
            model="haiku",
        )

        assert output_heavy.cost_usd > input_heavy.cost_usd
        assert input_heavy.points_per_dollar > output_heavy.points_per_dollar
