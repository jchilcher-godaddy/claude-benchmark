"""Tests for CostTracker and cost estimation functions."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from claude_benchmark.execution.cost import (
    MODEL_PRICING,
    CostTracker,
    estimate_suite_cost,
)


@dataclass
class FakeRun:
    """Minimal run-like object with a model attribute for cost estimation."""

    model: str


class TestCostTrackerNoCap:
    """CostTracker with no max_cost should never reach cap."""

    def test_cap_never_reached(self) -> None:
        tracker = CostTracker()
        tracker.add(100.0)
        tracker.add(200.0)
        assert tracker.cap_reached is False

    def test_total_cost_accumulates(self) -> None:
        tracker = CostTracker()
        tracker.add(1.50)
        tracker.add(2.50)
        assert tracker.total_cost == pytest.approx(4.0)


class TestCostTrackerAdd:
    """CostTracker.add() accumulates correctly."""

    def test_add_single(self) -> None:
        tracker = CostTracker(max_cost=10.0)
        tracker.add(3.0)
        assert tracker.total_cost == pytest.approx(3.0)

    def test_add_multiple(self) -> None:
        tracker = CostTracker(max_cost=10.0)
        tracker.add(1.0)
        tracker.add(2.0)
        tracker.add(3.0)
        assert tracker.total_cost == pytest.approx(6.0)

    def test_add_zero(self) -> None:
        tracker = CostTracker(max_cost=10.0)
        tracker.add(0.0)
        assert tracker.total_cost == pytest.approx(0.0)
        assert tracker.cap_reached is False


class TestCostTrackerCapReached:
    """CostTracker signals cap_reached when total >= max_cost."""

    def test_cap_reached_exact(self) -> None:
        tracker = CostTracker(max_cost=5.0)
        tracker.add(5.0)
        assert tracker.cap_reached is True

    def test_cap_reached_exceeded(self) -> None:
        tracker = CostTracker(max_cost=5.0)
        tracker.add(3.0)
        assert tracker.cap_reached is False
        tracker.add(3.0)
        assert tracker.cap_reached is True

    def test_cap_not_reached_below(self) -> None:
        tracker = CostTracker(max_cost=10.0)
        tracker.add(4.99)
        assert tracker.cap_reached is False


class TestEstimateRunCost:
    """estimate_run_cost returns correct values for known models."""

    def test_haiku_cost(self) -> None:
        tracker = CostTracker()
        # haiku: $1/MTok input, $5/MTok output
        # 4000 input tokens: 4000/1_000_000 * 1.00 = 0.004
        # 2000 output tokens: 2000/1_000_000 * 5.00 = 0.01
        cost = tracker.estimate_run_cost("haiku", 4000, 2000)
        assert cost == pytest.approx(0.014)

    def test_sonnet_cost(self) -> None:
        tracker = CostTracker()
        # sonnet: $3/MTok input, $15/MTok output
        # 4000 input: 4000/1_000_000 * 3.00 = 0.012
        # 2000 output: 2000/1_000_000 * 15.00 = 0.03
        cost = tracker.estimate_run_cost("sonnet", 4000, 2000)
        assert cost == pytest.approx(0.042)

    def test_opus_cost(self) -> None:
        tracker = CostTracker()
        # opus: $5/MTok input, $25/MTok output
        # 4000 input: 4000/1_000_000 * 5.00 = 0.02
        # 2000 output: 2000/1_000_000 * 25.00 = 0.05
        cost = tracker.estimate_run_cost("opus", 4000, 2000)
        assert cost == pytest.approx(0.07)

    def test_unknown_model_falls_back_to_sonnet(self) -> None:
        tracker = CostTracker()
        cost_unknown = tracker.estimate_run_cost("unknown-model", 4000, 2000)
        cost_sonnet = tracker.estimate_run_cost("sonnet", 4000, 2000)
        assert cost_unknown == pytest.approx(cost_sonnet)


class TestEstimateSuiteCost:
    """estimate_suite_cost returns per-model and total breakdown."""

    def test_single_model(self) -> None:
        costs = estimate_suite_cost(
            task_count=2,
            profile_count=2,
            models=["haiku"],
            reps=3,
            avg_input_tokens=4000,
            avg_output_tokens=2000,
        )
        # 2 tasks * 2 profiles * 3 reps = 12 runs
        # haiku: 12 * (4000/1M * 1.00 + 2000/1M * 5.00) = 12 * 0.014 = 0.168
        assert "haiku" in costs
        assert "total" in costs
        assert costs["haiku"] == pytest.approx(0.168)
        assert costs["total"] == pytest.approx(0.168)

    def test_multiple_models(self) -> None:
        costs = estimate_suite_cost(
            task_count=1,
            profile_count=1,
            models=["haiku", "sonnet", "opus"],
            reps=1,
        )
        # 1 task * 1 profile * 1 rep = 1 run per model
        assert costs["haiku"] == pytest.approx(0.014)
        assert costs["sonnet"] == pytest.approx(0.042)
        assert costs["opus"] == pytest.approx(0.07)
        assert costs["total"] == pytest.approx(0.014 + 0.042 + 0.07)

    def test_unknown_model_uses_sonnet_pricing(self) -> None:
        costs = estimate_suite_cost(
            task_count=1,
            profile_count=1,
            models=["mystery"],
            reps=1,
        )
        sonnet_costs = estimate_suite_cost(
            task_count=1,
            profile_count=1,
            models=["sonnet"],
            reps=1,
        )
        assert costs["mystery"] == pytest.approx(sonnet_costs["sonnet"])
