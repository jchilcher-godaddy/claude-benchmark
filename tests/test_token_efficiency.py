"""Tests for token efficiency calculator.

Verifies compute_token_efficiency produces correct points-per-1K-tokens
ratios, handles zero-token edge cases, and correctly tracks token breakdowns.
"""

from __future__ import annotations

from claude_benchmark.scoring.token_efficiency import compute_token_efficiency


# ---------------------------------------------------------------------------
# Tests: Known values
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
