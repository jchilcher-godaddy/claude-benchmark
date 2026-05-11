"""Tests for CostTracker and cost estimation functions."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from claude_benchmark.execution.cost import (
    JUDGE_AVG_INPUT_TOKENS,
    JUDGE_AVG_OUTPUT_TOKENS,
    JUDGE_MODEL,
    MODEL_PRICING,
    CostTracker,
    estimate_suite_cost,
)


@dataclass
class FakeRun:
    """Minimal run-like object with a model attribute for cost estimation."""

    model: str
    follow_up_prompts: list[str] | None = None


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
        # haiku execution: 12 * (4000/1M * 1.00 + 2000/1M * 5.00) = 12 * 0.014 = 0.168
        # judge: 12 * (3000/1M * 1.00 + 500/1M * 5.00) = 12 * 0.0055 = 0.066
        assert "haiku" in costs
        assert "total" in costs
        assert costs["haiku"] == pytest.approx(0.168)
        judge_cost = CostTracker().estimate_judge_cost(12)
        assert costs["judge"] == pytest.approx(judge_cost)
        assert costs["total"] == pytest.approx(0.168 + judge_cost)

    def test_multiple_models(self) -> None:
        costs = estimate_suite_cost(
            task_count=1,
            profile_count=1,
            models=["haiku", "sonnet", "opus"],
            reps=1,
        )
        # 1 task * 1 profile * 1 rep = 1 run per model (3 runs total)
        assert costs["haiku"] == pytest.approx(0.014)
        assert costs["sonnet"] == pytest.approx(0.042)
        assert costs["opus"] == pytest.approx(0.07)
        judge_cost = CostTracker().estimate_judge_cost(3)
        assert costs["total"] == pytest.approx(0.014 + 0.042 + 0.07 + judge_cost)

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


class TestEstimateJudgeCost:
    """estimate_judge_cost uses haiku pricing with judge token estimates."""

    def test_single_run(self) -> None:
        tracker = CostTracker()
        pricing = MODEL_PRICING[JUDGE_MODEL]
        expected = (
            (JUDGE_AVG_INPUT_TOKENS / 1_000_000) * pricing["input"]
            + (JUDGE_AVG_OUTPUT_TOKENS / 1_000_000) * pricing["output"]
        )
        assert tracker.estimate_judge_cost(1) == pytest.approx(expected)

    def test_multiple_runs(self) -> None:
        tracker = CostTracker()
        single = tracker.estimate_judge_cost(1)
        assert tracker.estimate_judge_cost(10) == pytest.approx(single * 10)

    def test_zero_runs(self) -> None:
        tracker = CostTracker()
        assert tracker.estimate_judge_cost(0) == pytest.approx(0.0)


class TestEstimateTotalCostWithJudge:
    """estimate_total_cost includes or excludes judge cost via flag."""

    def test_includes_judge_by_default(self) -> None:
        tracker = CostTracker()
        runs = [FakeRun("haiku")]
        with_judge = tracker.estimate_total_cost(runs)
        without_judge = tracker.estimate_total_cost(runs, include_judge=False)
        assert with_judge > without_judge
        assert with_judge == pytest.approx(
            without_judge + tracker.estimate_judge_cost(1)
        )

    def test_exclude_judge(self) -> None:
        tracker = CostTracker()
        runs = [FakeRun("sonnet")]
        # Without judge should equal the old behavior (execution only)
        cost = tracker.estimate_total_cost(runs, include_judge=False)
        expected = tracker.estimate_run_cost("sonnet", 4000, 2000)
        assert cost == pytest.approx(expected)


class TestEstimateSuiteCostWithJudge:
    """estimate_suite_cost includes judge cost by default."""

    def test_includes_judge_key(self) -> None:
        costs = estimate_suite_cost(
            task_count=2,
            profile_count=1,
            models=["haiku"],
            reps=5,
        )
        assert "judge" in costs
        assert costs["judge"] > 0
        # total = haiku execution + judge
        assert costs["total"] == pytest.approx(costs["haiku"] + costs["judge"])

    def test_exclude_judge(self) -> None:
        costs = estimate_suite_cost(
            task_count=2,
            profile_count=1,
            models=["haiku"],
            reps=5,
            include_judge=False,
        )
        assert "judge" not in costs
        assert costs["total"] == pytest.approx(costs["haiku"])


class TestMultiTurnCostEstimation:
    """estimate_total_cost accounts for multi-turn conversation cost scaling."""

    def test_single_turn_unchanged(self) -> None:
        tracker = CostTracker()
        runs = [FakeRun("haiku")]
        cost = tracker.estimate_total_cost(runs, include_judge=False)
        expected = tracker.estimate_run_cost("haiku", 4000, 2000)
        assert cost == pytest.approx(expected)

    def test_two_turn_costs_more_than_single(self) -> None:
        tracker = CostTracker()
        single = [FakeRun("sonnet")]
        multi = [FakeRun("sonnet", follow_up_prompts=["Review."])]
        single_cost = tracker.estimate_total_cost(single, include_judge=False)
        multi_cost = tracker.estimate_total_cost(multi, include_judge=False)
        assert multi_cost > single_cost

    def test_three_turn_costs_more_than_two(self) -> None:
        tracker = CostTracker()
        two = [FakeRun("sonnet", follow_up_prompts=["Review."])]
        three = [FakeRun("sonnet", follow_up_prompts=["Review.", "Fix."])]
        two_cost = tracker.estimate_total_cost(two, include_judge=False)
        three_cost = tracker.estimate_total_cost(three, include_judge=False)
        assert three_cost > two_cost

    def test_none_follow_ups_same_as_no_attr(self) -> None:
        tracker = CostTracker()
        run_none = [FakeRun("haiku", follow_up_prompts=None)]
        run_empty = [FakeRun("haiku", follow_up_prompts=[])]
        run_default = [FakeRun("haiku")]
        cost_none = tracker.estimate_total_cost(run_none, include_judge=False)
        cost_empty = tracker.estimate_total_cost(run_empty, include_judge=False)
        cost_default = tracker.estimate_total_cost(run_default, include_judge=False)
        assert cost_none == pytest.approx(cost_default)
        assert cost_empty == pytest.approx(cost_default)
