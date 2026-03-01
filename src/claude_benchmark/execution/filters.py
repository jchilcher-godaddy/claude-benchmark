"""Run matrix filtering for subset execution.

Provides filter_runs() to narrow the run matrix by task name,
profile name, and/or model name. Supports --task, --profile, --model
CLI flags for selective benchmark execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_benchmark.execution.parallel import BenchmarkRun


def filter_runs(
    runs: list[BenchmarkRun],
    task_names: list[str] | None = None,
    profile_names: list[str] | None = None,
    model_names: list[str] | None = None,
) -> list[BenchmarkRun]:
    """Filter runs by task, profile, and/or model name.

    Filters are AND-combined: all specified filters must match for a run
    to be included. If all filters are None, returns all runs unchanged.

    Args:
        runs: Full list of BenchmarkRun instances.
        task_names: If set, keep only runs with matching task_name.
        profile_names: If set, keep only runs with matching profile_name.
        model_names: If set, keep only runs with matching model.

    Returns:
        Filtered list of BenchmarkRun instances.
    """
    result = runs
    if task_names is not None:
        result = [r for r in result if r.task_name in task_names]
    if profile_names is not None:
        result = [r for r in result if r.profile_name in profile_names]
    if model_names is not None:
        result = [r for r in result if r.model in model_names]
    return result
