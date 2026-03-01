"""Statistical regression detection for benchmark results.

Detects when a CLAUDE.md profile makes benchmark performance statistically
worse than the empty (no CLAUDE.md) baseline. Uses Mann-Whitney U test
(exact) as primary with Welch's t-test fallback for tied scores.

Dual threshold: BOTH p < 0.05 AND delta > 5% required to flag a regression,
preventing false positives from normal run-to-run variance.
"""

from __future__ import annotations

from scipy import stats

from claude_benchmark.reporting.models import BenchmarkResults, RegressionResult


def check_regression(
    baseline_scores: list[float],
    profile_scores: list[float],
    profile: str,
    task: str,
    dimension: str,
    p_threshold: float = 0.05,
    delta_threshold: float = 0.05,
) -> RegressionResult:
    """Check if profile scores represent a regression from baseline.

    Uses Mann-Whitney U test (exact method) as primary statistical test.
    Falls back to Welch's t-test when ties cause ValueError in Mann-Whitney.

    A regression requires BOTH:
    - p-value < p_threshold (statistically significant)
    - delta_pct < -delta_threshold (profile is meaningfully worse)

    Args:
        baseline_scores: Score values from the baseline (empty) profile.
        profile_scores: Score values from the profile being tested.
        profile: Name of the profile being tested.
        task: Name of the task being compared.
        dimension: Scoring dimension being compared (e.g., "correctness").
        p_threshold: Significance level (default 0.05).
        delta_threshold: Minimum absolute delta percentage to flag (default 0.05 = 5%).

    Returns:
        RegressionResult with statistical test details and regression flag.
    """
    baseline_mean = sum(baseline_scores) / len(baseline_scores)
    profile_mean = sum(profile_scores) / len(profile_scores)

    # Calculate percentage delta (negative = profile is worse)
    if baseline_mean == 0.0:
        delta_pct = 0.0
    else:
        delta_pct = (profile_mean - baseline_mean) / baseline_mean

    # Primary test: Mann-Whitney U (exact method)
    # alternative="greater" tests if baseline > profile (i.e., profile is worse)
    test_used = "mann-whitney-u"
    try:
        stat_result = stats.mannwhitneyu(
            baseline_scores,
            profile_scores,
            alternative="greater",
            method="exact",
        )
        p_value = float(stat_result.pvalue)
    except ValueError:
        # Fallback: Welch's t-test when ties prevent exact Mann-Whitney
        test_used = "welch-t-test"
        stat_result = stats.ttest_ind(
            baseline_scores,
            profile_scores,
            equal_var=False,
            alternative="greater",
        )
        p_value = float(stat_result.pvalue)

    # Dual threshold: both must be met
    is_regression = p_value < p_threshold and delta_pct < -delta_threshold

    return RegressionResult(
        profile=profile,
        task=task,
        dimension=dimension,
        baseline_mean=baseline_mean,
        profile_mean=profile_mean,
        delta_pct=delta_pct,
        p_value=p_value,
        is_regression=is_regression,
        test_used=test_used,
    )


def detect_all_regressions(
    results: BenchmarkResults,
    baseline_profile: str = "empty",
) -> list[RegressionResult]:
    """Detect regressions across all profiles, tasks, and scoring dimensions.

    Compares each non-baseline profile against the baseline (empty) profile
    for every task and scoring dimension. Skips comparisons where either
    side has fewer than 2 runs (insufficient data for statistical testing).

    Args:
        results: Full benchmark results containing all profiles.
        baseline_profile: Profile ID to use as baseline (default "empty").

    Returns:
        List of all RegressionResult objects (including non-regressions
        with is_regression=False).
    """
    if baseline_profile not in results.profiles:
        return []

    baseline = results.profiles[baseline_profile]
    all_results: list[RegressionResult] = []

    for profile_id, profile_result in results.profiles.items():
        if profile_id == baseline_profile:
            continue

        for task_id, task_result in profile_result.tasks.items():
            if task_id not in baseline.tasks:
                continue

            baseline_task = baseline.tasks[task_id]

            # Skip if insufficient runs on either side
            if len(baseline_task.runs) < 2 or len(task_result.runs) < 2:
                continue

            # Collect all scoring dimensions from both sides
            dimensions: set[str] = set()
            for run in baseline_task.runs:
                dimensions.update(run.scores.keys())
            for run in task_result.runs:
                dimensions.update(run.scores.keys())

            for dim in sorted(dimensions):
                baseline_scores = [
                    run.scores[dim]
                    for run in baseline_task.runs
                    if dim in run.scores
                ]
                profile_scores = [
                    run.scores[dim]
                    for run in task_result.runs
                    if dim in run.scores
                ]

                # Need at least 2 scores on each side
                if len(baseline_scores) < 2 or len(profile_scores) < 2:
                    continue

                result = check_regression(
                    baseline_scores=baseline_scores,
                    profile_scores=profile_scores,
                    profile=profile_id,
                    task=task_id,
                    dimension=dim,
                )
                all_results.append(result)

    return all_results


def summarize_regressions(regressions: list[RegressionResult]) -> str:
    """Format a CLI summary of detected regressions.

    Args:
        regressions: List of RegressionResult objects to summarize.

    Returns:
        Formatted string listing all regressions, or "No regressions detected."
    """
    flagged = [r for r in regressions if r.is_regression]

    if not flagged:
        return "No regressions detected."

    lines = []
    for r in flagged:
        lines.append(
            f"REGRESSION: {r.profile} on {r.task}/{r.dimension}: "
            f"{r.delta_pct:+.1%} (p={r.p_value:.3f})"
        )

    return "\n".join(lines)
