"""Cost tracking and estimation for benchmark execution.

Provides CostTracker for accumulating per-run costs and signaling when a
cost cap is reached, plus estimate_suite_cost for dry-run cost previews.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Model pricing per million tokens (as of Feb 2026)
# Haiku 4.5:  $1/MTok input,  $5/MTok output
# Sonnet 4.6: $3/MTok input, $15/MTok output
# Opus 4.6:   $5/MTok input, $25/MTok output
MODEL_PRICING: dict[str, dict[str, float]] = {
    "haiku": {"input": 1.00, "output": 5.00},
    "sonnet": {"input": 3.00, "output": 15.00},
    "opus": {"input": 5.00, "output": 25.00},
}

# LLM judge token estimates (conservative).
# Input: system prompt (~600 tok) + user prompt with code (~2400 tok) = ~3000 tok
# Output: JSON with 4 criteria, scores, and reasoning = ~500 tok
JUDGE_AVG_INPUT_TOKENS = 3000
JUDGE_AVG_OUTPUT_TOKENS = 500
# Judge always uses haiku (see scoring/prompts.py DEFAULT_JUDGE_MODEL)
JUDGE_MODEL = "haiku"


@dataclass
class CostTracker:
    """Tracks accumulated costs and signals when a cost cap is reached.

    When max_cost is set and total_cost reaches or exceeds it, cap_reached
    becomes True. Workers should check cap_reached before starting new runs
    to enable graceful wind-down.
    """

    max_cost: float | None = None
    _total_cost: float = field(default=0.0, init=False, repr=False)
    _cap_reached: bool = field(default=False, init=False, repr=False)

    @property
    def total_cost(self) -> float:
        """Current accumulated cost across all runs."""
        return self._total_cost

    @property
    def cap_reached(self) -> bool:
        """Whether the cost cap has been reached."""
        return self._cap_reached

    def add(self, cost: float) -> None:
        """Add a run's cost to the accumulator.

        Sets cap_reached if max_cost is set and total now exceeds it.
        """
        self._total_cost += cost
        if self.max_cost is not None and self._total_cost >= self.max_cost:
            self._cap_reached = True

    def estimate_run_cost(
        self, model: str, avg_input_tokens: int, avg_output_tokens: int
    ) -> float:
        """Estimate cost for a single run based on model pricing.

        Falls back to sonnet pricing for unknown models.
        """
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["sonnet"])
        input_cost = (avg_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (avg_output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def estimate_judge_cost(self, num_runs: int) -> float:
        """Estimate LLM judge cost for a number of runs.

        Each run triggers one Haiku judge call with ~3K input / ~500 output tokens.
        """
        pricing = MODEL_PRICING[JUDGE_MODEL]
        input_cost = (JUDGE_AVG_INPUT_TOKENS / 1_000_000) * pricing["input"]
        output_cost = (JUDGE_AVG_OUTPUT_TOKENS / 1_000_000) * pricing["output"]
        return (input_cost + output_cost) * num_runs

    def estimate_total_cost(
        self,
        runs: list,
        avg_input_tokens: int = 4000,
        avg_output_tokens: int = 2000,
        include_judge: bool = True,
    ) -> float:
        """Estimate total cost for a list of runs.

        Each run must have a .model attribute. When *include_judge* is True
        (the default), adds one Haiku judge call per run.

        Multi-turn runs (with follow_up_prompts) are estimated with a
        per-turn multiplier: each follow-up re-sends the growing conversation
        history, so input tokens scale roughly as n*(n+1)/2 for n turns.
        """
        total = 0.0
        for run in runs:
            follow_ups = getattr(run, "follow_up_prompts", None) or []
            turn_count = 1 + len(follow_ups)
            if turn_count == 1:
                total += self.estimate_run_cost(run.model, avg_input_tokens, avg_output_tokens)
            else:
                # Each turn re-sends prior history. Approximate: turn k sees
                # avg_input + k * avg_output cached tokens, plus its own output.
                # Triangular sum for input, linear for output.
                pricing = MODEL_PRICING.get(run.model, MODEL_PRICING["sonnet"])
                cumulative_input = 0
                cumulative_output = 0
                for turn in range(turn_count):
                    turn_input = avg_input_tokens + turn * avg_output_tokens
                    cumulative_input += turn_input
                    cumulative_output += avg_output_tokens
                total += (
                    (cumulative_input / 1_000_000) * pricing["input"]
                    + (cumulative_output / 1_000_000) * pricing["output"]
                )
        if include_judge:
            total += self.estimate_judge_cost(len(runs))
        return total


def estimate_suite_cost(
    task_count: int,
    profile_count: int,
    models: list[str],
    reps: int,
    avg_input_tokens: int = 4000,
    avg_output_tokens: int = 2000,
    include_judge: bool = True,
) -> dict[str, float]:
    """Estimate total cost for a benchmark suite.

    Returns a dict with per-model costs, a 'judge' key (if *include_judge*),
    and a 'total' key.

    Uses conservative estimates: 4K input tokens (prompt + CLAUDE.md + task)
    and 2K output tokens (generated code). Actual costs will vary based on
    task complexity and profile size.
    """
    costs: dict[str, float] = {}
    total_runs = 0
    for model in models:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["sonnet"])
        runs = task_count * profile_count * reps
        total_runs += runs
        input_cost = (avg_input_tokens * runs / 1_000_000) * pricing["input"]
        output_cost = (avg_output_tokens * runs / 1_000_000) * pricing["output"]
        costs[model] = input_cost + output_cost
    if include_judge:
        tracker = CostTracker()
        costs["judge"] = tracker.estimate_judge_cost(total_runs)
    costs["total"] = sum(v for k, v in costs.items() if k != "total")
    return costs
