from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_benchmark.results.schema import RunResult

from claude_benchmark.execution.cost import cost_breakdown
from claude_benchmark.results.schema import AggregateResult, StatsSummary


def _safe_stats(data: list[float]) -> StatsSummary:
    if len(data) == 0:
        return StatsSummary(mean=0.0, variance=0.0, stdev=0.0)
    if len(data) == 1:
        return StatsSummary(mean=data[0], variance=0.0, stdev=0.0)

    mean = statistics.mean(data)
    variance = statistics.variance(data, xbar=mean)
    stdev = statistics.stdev(data, xbar=mean)

    return StatsSummary(mean=mean, variance=variance, stdev=stdev)


def compute_aggregate(
    run_results: list[RunResult],
    task_name: str,
    profile_name: str,
    model: str,
) -> AggregateResult:
    total_runs = len(run_results)
    successful_runs = sum(1 for r in run_results if r.success)
    failed_runs = total_runs - successful_runs
    success_rate = successful_runs / total_runs if total_runs > 0 else 0.0

    successful = [r for r in run_results if r.success]
    failed_details = [r.error or "Unknown error" for r in run_results if not r.success]

    wall_clock = None
    if successful:
        wall_clock = _safe_stats([r.wall_clock_seconds for r in successful])

    input_tokens = None
    output_tokens = None
    cache_creation_tokens = None
    cache_read_tokens = None
    cost_usd = None
    cost_breakdown_usd = None

    runs_with_usage = [r for r in successful if r.usage is not None]
    if runs_with_usage:
        input_tokens = _safe_stats([r.usage.input_tokens for r in runs_with_usage])
        output_tokens = _safe_stats([r.usage.output_tokens for r in runs_with_usage])
        cache_creation_tokens = _safe_stats(
            [r.usage.cache_creation_input_tokens for r in runs_with_usage]
        )
        cache_read_tokens = _safe_stats(
            [r.usage.cache_read_input_tokens for r in runs_with_usage]
        )
        # Mean per-run spend mix priced at this model's rates.
        breakdown = cost_breakdown(
            input_tokens=int(input_tokens.mean),
            output_tokens=int(output_tokens.mean),
            cache_creation_input_tokens=int(cache_creation_tokens.mean),
            cache_read_input_tokens=int(cache_read_tokens.mean),
            model=model,
        )
        cost_breakdown_usd = {k: round(v, 6) for k, v in breakdown.items()}

    runs_with_cost = [r for r in successful if r.total_cost_usd is not None]
    if runs_with_cost:
        cost_usd = _safe_stats([r.total_cost_usd for r in runs_with_cost])

    return AggregateResult(
        task_name=task_name,
        profile_name=profile_name,
        model=model,
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        success_rate=success_rate,
        wall_clock=wall_clock,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        cost_usd=cost_usd,
        cost_breakdown_usd=cost_breakdown_usd,
        failed_details=failed_details,
    )
