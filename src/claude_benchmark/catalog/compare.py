"""Cross-run comparison logic with statistical analysis."""

from __future__ import annotations

import copy
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from scipy import stats

from claude_benchmark.catalog.models import (
    CatalogEntry,
    ComparisonKey,
    ComparisonReport,
    PairwiseComparison,
)
from claude_benchmark.reporting.loader import load_results_dir
from claude_benchmark.reporting.models import BenchmarkResults, RunResult
from claude_benchmark.reporting.regression import (
    bonferroni_correct,
    compute_effect_size,
    interpret_effect_size,
)


def extract_run_keys(
    results: BenchmarkResults,
) -> dict[ComparisonKey, list[RunResult]]:
    """Decompose BenchmarkResults into (model, profile, task) keys with run lists.

    Args:
        results: Full benchmark results.

    Returns:
        Dict mapping ComparisonKey to list of individual RunResult objects.
    """
    key_map: dict[ComparisonKey, list[RunResult]] = defaultdict(list)

    for profile_name, profile_result in results.profiles.items():
        for task_name, task_result in profile_result.tasks.items():
            for run in task_result.runs:
                key = ComparisonKey(
                    model=run.model,
                    profile=profile_name,
                    task=task_name,
                )
                key_map[key].append(run)

    return dict(key_map)


def find_overlapping_keys(
    key_maps: list[dict[ComparisonKey, list]],
) -> set[ComparisonKey]:
    """Find comparison keys present in 2 or more key maps.

    Args:
        key_maps: List of key-to-runs dictionaries from different entries.

    Returns:
        Set of ComparisonKey objects present in at least 2 key_maps.
    """
    if len(key_maps) < 2:
        return set()

    # Count occurrences of each key
    key_counts: dict[ComparisonKey, int] = defaultdict(int)
    for key_map in key_maps:
        for key in key_map:
            key_counts[key] += 1

    # Return keys present in 2+ maps
    return {key for key, count in key_counts.items() if count >= 2}


def _variant_label(composite_key: str) -> str:
    """Extract short variant label from composite key like 'empty:temp-0.0' -> 'temp-0.0'."""
    if ":" in composite_key:
        return composite_key.rsplit(":", 1)[1]
    return composite_key


def expand_to_virtual_entries(
    entries: list[CatalogEntry],
    results_by_id: dict[str, BenchmarkResults],
) -> tuple[list[CatalogEntry], dict[str, BenchmarkResults]]:
    """Expand each run's variants into separate virtual entries for cross-variant comparison.

    Each variant in each run becomes its own CatalogEntry with a single profile
    keyed as "_all" so that (model, "_all", task) keys overlap across all entries.

    Returns:
        Tuple of (virtual_entries, virtual_results_by_id).
    """
    virtual_entries: list[CatalogEntry] = []
    virtual_results: dict[str, BenchmarkResults] = {}

    for entry in entries:
        if entry.run_id not in results_by_id:
            continue
        results = results_by_id[entry.run_id]

        for profile_key, profile_result in results.profiles.items():
            variant_label = _variant_label(profile_key)
            virtual_id = f"{entry.run_id}:{variant_label}"

            # Create virtual entry
            virtual_entry = CatalogEntry(
                run_id=virtual_id,
                name=variant_label,
                timestamp=entry.timestamp,
                results_path=entry.results_path,
                tags=entry.tags,
                models=entry.models,
                profiles=["_all"],
                tasks=entry.tasks,
                variants=[variant_label],
                total_runs=sum(
                    len(tr.runs) for tr in profile_result.tasks.values()
                ),
                experiment_name=entry.experiment_name,
                intake_timestamp=entry.intake_timestamp,
            )
            virtual_entries.append(virtual_entry)

            # Create virtual results with profile key remapped to "_all"
            virtual_br = BenchmarkResults(
                metadata=copy.deepcopy(results.metadata),
                profiles={"_all": profile_result},
            )
            virtual_results[virtual_id] = virtual_br

    return virtual_entries, virtual_results


def compare_entries(
    entries: list[CatalogEntry],
    dimensions: list[str] | None = None,
    p_threshold: float = 0.05,
    delta_threshold: float = 0.05,
    cross_variant: bool = False,
) -> ComparisonReport:
    """Compare multiple catalog entries with statistical analysis.

    For each overlapping (model, profile, task) key and each scoring dimension,
    performs pairwise statistical comparisons between entries.

    Args:
        entries: Catalog entries to compare (2+ required).
        dimensions: Score dimensions to compare. If None, uses all found.
        p_threshold: P-value threshold for significance.
        delta_threshold: Minimum absolute percentage delta to report.
        cross_variant: If True, expand each run's variants into separate
            virtual entries and compare at the (model, task) level.

    Returns:
        ComparisonReport with all pairwise comparisons.
    """
    if len(entries) < 2:
        return ComparisonReport(entries=entries)

    # Load results for each entry
    results_by_id: dict[str, BenchmarkResults] = {}
    for entry in entries:
        try:
            results = load_results_dir(Path(entry.results_path))
            results_by_id[entry.run_id] = results
        except Exception:
            continue

    if len(results_by_id) < 2:
        return ComparisonReport(entries=entries)

    # Cross-variant mode: expand variants into virtual entries
    if cross_variant:
        entries, results_by_id = expand_to_virtual_entries(entries, results_by_id)
        if len(entries) < 2:
            return ComparisonReport(entries=entries)

    # Extract comparison keys for each entry
    key_maps: dict[str, dict[ComparisonKey, list[RunResult]]] = {
        run_id: extract_run_keys(results)
        for run_id, results in results_by_id.items()
    }

    # Find overlapping and unique keys
    overlapping_keys = find_overlapping_keys(list(key_maps.values()))

    unique_keys_by_id: dict[str, list[dict[str, str]]] = {}
    for run_id, key_map in key_maps.items():
        unique = {key for key in key_map if key not in overlapping_keys}
        unique_keys_by_id[run_id] = [
            {"model": k.model, "profile": k.profile, "task": k.task} for k in unique
        ]

    # Determine dimensions to compare
    all_dimensions: set[str] = set()
    if dimensions is None:
        for key_map in key_maps.values():
            for runs in key_map.values():
                for run in runs:
                    all_dimensions.update(run.scores.keys())
        dimensions = sorted(all_dimensions)

    # Perform pairwise comparisons
    comparisons: list[PairwiseComparison] = []

    # Build pairs of entries
    entry_pairs = list(combinations(entries, 2))

    # Apply Bonferroni correction if multiple comparisons
    # Number of comparisons = pairs × overlapping_keys × dimensions
    n_comparisons = (
        len(entry_pairs) * len(overlapping_keys) * len(dimensions)
    )

    for entry_a, entry_b in entry_pairs:
        if entry_a.run_id not in results_by_id or entry_b.run_id not in results_by_id:
            continue

        key_map_a = key_maps[entry_a.run_id]
        key_map_b = key_maps[entry_b.run_id]

        for key in overlapping_keys:
            if key not in key_map_a or key not in key_map_b:
                continue

            runs_a = key_map_a[key]
            runs_b = key_map_b[key]

            for dimension in dimensions:
                # Extract scores for this dimension
                scores_a = [run.scores[dimension] for run in runs_a if dimension in run.scores]
                scores_b = [run.scores[dimension] for run in runs_b if dimension in run.scores]

                if len(scores_a) < 2 or len(scores_b) < 2:
                    continue

                mean_a = sum(scores_a) / len(scores_a)
                mean_b = sum(scores_b) / len(scores_b)

                # Calculate percentage delta
                if mean_a == 0.0:
                    delta_pct = 0.0
                else:
                    delta_pct = (mean_b - mean_a) / mean_a

                # Two-sided Mann-Whitney U test
                test_used = "mann-whitney-u"
                try:
                    stat_result = stats.mannwhitneyu(
                        scores_a,
                        scores_b,
                        alternative="two-sided",
                        method="exact",
                    )
                    p_value = float(stat_result.pvalue)
                except ValueError:
                    # Fallback to Welch's t-test
                    test_used = "welch-t-test"
                    stat_result = stats.ttest_ind(
                        scores_a,
                        scores_b,
                        equal_var=False,
                        alternative="two-sided",
                    )
                    p_value = float(stat_result.pvalue)

                # Compute effect size
                effect_size = compute_effect_size(scores_a, scores_b)
                effect_label = interpret_effect_size(effect_size)

                # Apply Bonferroni correction
                corrected_p = min(1.0, p_value * n_comparisons)

                # Check significance with delta threshold
                is_significant = (
                    corrected_p < p_threshold
                    and abs(delta_pct) > delta_threshold
                )

                comparison = PairwiseComparison(
                    key_model=key.model,
                    key_profile=key.profile,
                    key_task=key.task,
                    dimension=dimension,
                    run_a_id=entry_a.run_id,
                    run_a_name=entry_a.name,
                    run_a_mean=mean_a,
                    run_a_n=len(scores_a),
                    run_b_id=entry_b.run_id,
                    run_b_name=entry_b.name,
                    run_b_mean=mean_b,
                    run_b_n=len(scores_b),
                    delta_pct=delta_pct,
                    p_value=corrected_p,
                    effect_size=effect_size,
                    effect_label=effect_label,
                    is_significant=is_significant,
                    test_used=test_used,
                )
                comparisons.append(comparison)

    # Serialize overlapping keys for report
    overlapping_keys_serialized = [
        {"model": k.model, "profile": k.profile, "task": k.task}
        for k in overlapping_keys
    ]

    return ComparisonReport(
        entries=entries,
        overlapping_keys=overlapping_keys_serialized,
        unique_keys=unique_keys_by_id,
        comparisons=comparisons,
    )
