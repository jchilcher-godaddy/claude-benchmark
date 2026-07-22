"""Bootstrap confidence intervals for mean differences.

Two flavors are exposed:

- :func:`bootstrap_diff_ci` resamples observations independently. Suitable when
  observations can be treated as i.i.d. within each arm.
- :func:`cluster_bootstrap_diff_ci` resamples at the *task* level (or any
  cluster column), preserving within-task correlation that arises in nested
  benchmark data.

Both return percentile and BCa intervals computed via ``scipy.stats.bootstrap``
to keep behavior consistent with established statistical tooling.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


@dataclass
class BootstrapDiffCI:
    """Result container for a bootstrapped mean-difference CI."""

    mean_a: float
    mean_b: float
    diff: float
    n_a: int
    n_b: int
    n_iter: int
    ci_level: float
    percentile_low: float
    percentile_high: float
    bca_low: float
    bca_high: float
    method: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "mean_a": self.mean_a,
            "mean_b": self.mean_b,
            "diff": self.diff,
            "n_a": self.n_a,
            "n_b": self.n_b,
            "n_iter": self.n_iter,
            "ci_level": self.ci_level,
            "percentile_low": self.percentile_low,
            "percentile_high": self.percentile_high,
            "bca_low": self.bca_low,
            "bca_high": self.bca_high,
            "method": self.method,
        }


def _coerce_array(values: Sequence[float] | np.ndarray | pd.Series) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    return arr


def bootstrap_diff_ci(
    group_a: Sequence[float] | np.ndarray | pd.Series,
    group_b: Sequence[float] | np.ndarray | pd.Series,
    *,
    n_iter: int = 10_000,
    ci: float = 0.95,
    seed: int = 42,
) -> BootstrapDiffCI:
    """Bootstrap CI for ``mean(group_b) - mean(group_a)``.

    Uses ``scipy.stats.bootstrap`` for both percentile and BCa intervals on
    independent draws (with replacement) from each group.
    """
    if not (0.0 < ci < 1.0):
        raise ValueError("ci must be in (0, 1)")
    a = _coerce_array(group_a)
    b = _coerce_array(group_b)
    if a.size < 2 or b.size < 2:
        raise ValueError(
            f"need >= 2 observations per group; got n_a={a.size}, n_b={b.size}"
        )

    rng = np.random.default_rng(seed)

    def diff_stat(sample_a: np.ndarray, sample_b: np.ndarray) -> float:
        return float(np.mean(sample_b) - np.mean(sample_a))

    # SciPy expects axis-aware ufuncs; wrap to handle bootstrap's broadcasting.
    def diff_stat_axis(sample_a: np.ndarray, sample_b: np.ndarray, axis: int = -1) -> np.ndarray:
        return np.mean(sample_b, axis=axis) - np.mean(sample_a, axis=axis)

    pct = sp_stats.bootstrap(
        (a, b),
        statistic=diff_stat_axis,
        confidence_level=ci,
        n_resamples=n_iter,
        method="percentile",
        paired=False,
        vectorized=True,
        random_state=rng,
    )
    bca_seed = np.random.default_rng(seed)
    bca = sp_stats.bootstrap(
        (a, b),
        statistic=diff_stat_axis,
        confidence_level=ci,
        n_resamples=n_iter,
        method="BCa",
        paired=False,
        vectorized=True,
        random_state=bca_seed,
    )

    return BootstrapDiffCI(
        mean_a=float(np.mean(a)),
        mean_b=float(np.mean(b)),
        diff=diff_stat(a, b),
        n_a=int(a.size),
        n_b=int(b.size),
        n_iter=int(n_iter),
        ci_level=float(ci),
        percentile_low=float(pct.confidence_interval.low),
        percentile_high=float(pct.confidence_interval.high),
        bca_low=float(bca.confidence_interval.low),
        bca_high=float(bca.confidence_interval.high),
        method="independent",
    )


def cluster_bootstrap_diff_ci(
    df: pd.DataFrame,
    *,
    value_col: str,
    group_col: str,
    cluster_col: str = "task",
    group_a: str,
    group_b: str,
    n_iter: int = 10_000,
    ci: float = 0.95,
    seed: int = 42,
) -> BootstrapDiffCI:
    """Cluster bootstrap (resamples whole clusters with replacement).

    For each iteration we draw clusters with replacement from the union of
    cluster ids across the two groups, then compute the mean difference using
    the resampled clusters. Within a cluster we keep all observations of each
    arm as drawn (no further resampling), which is the standard nonparametric
    cluster bootstrap.

    Parameters
    ----------
    df
        Tidy DataFrame containing ``value_col``, ``group_col``, ``cluster_col``.
    value_col
        Numeric outcome column.
    group_col
        Column distinguishing the two arms (e.g. ``"variant"``).
    cluster_col
        Column whose unique values define clusters (e.g. ``"task"``).
    group_a, group_b
        Levels in ``group_col`` to compare (diff = b - a).
    n_iter, ci, seed
        Bootstrap configuration.
    """
    if not (0.0 < ci < 1.0):
        raise ValueError("ci must be in (0, 1)")

    needed = {value_col, group_col, cluster_col}
    missing = needed - set(df.columns)
    if missing:
        raise KeyError(f"missing columns: {sorted(missing)}")

    work = df.dropna(subset=[value_col, group_col, cluster_col]).copy()
    work = work[work[group_col].isin([group_a, group_b])]
    if work.empty:
        raise ValueError(
            f"no rows found for groups {group_a!r} / {group_b!r} in column {group_col!r}"
        )

    # Pre-aggregate within (cluster, group) for efficiency.
    grouped = (
        work.groupby([cluster_col, group_col])[value_col]
        .agg(["mean", "count"])
        .reset_index()
    )

    a_block = grouped[grouped[group_col] == group_a]
    b_block = grouped[grouped[group_col] == group_b]
    if a_block.empty or b_block.empty:
        raise ValueError("each group must have at least one cluster with data")

    a_means = dict(zip(a_block[cluster_col].astype(str), a_block["mean"], strict=False))
    a_counts = dict(zip(a_block[cluster_col].astype(str), a_block["count"], strict=False))
    b_means = dict(zip(b_block[cluster_col].astype(str), b_block["mean"], strict=False))
    b_counts = dict(zip(b_block[cluster_col].astype(str), b_block["count"], strict=False))

    clusters = np.array(
        sorted(set(a_means.keys()) | set(b_means.keys())),
        dtype=object,
    )
    if clusters.size < 2:
        raise ValueError("need >= 2 clusters for cluster bootstrap")

    rng = np.random.default_rng(seed)

    def cluster_diff(sampled: np.ndarray) -> float:
        sa_total = sa_count = 0.0
        sb_total = sb_count = 0.0
        for c in sampled:
            if c in a_means:
                sa_total += a_means[c] * a_counts[c]
                sa_count += a_counts[c]
            if c in b_means:
                sb_total += b_means[c] * b_counts[c]
                sb_count += b_counts[c]
        if sa_count == 0 or sb_count == 0:
            return float("nan")
        return float(sb_total / sb_count - sa_total / sa_count)

    point_estimate = cluster_diff(clusters)

    n_clusters = clusters.size
    diffs = np.empty(n_iter, dtype=float)
    for i in range(n_iter):
        idx = rng.integers(0, n_clusters, size=n_clusters)
        diffs[i] = cluster_diff(clusters[idx])
    diffs = diffs[~np.isnan(diffs)]
    if diffs.size < 100:
        raise RuntimeError(
            f"cluster bootstrap produced too many invalid resamples; only {diffs.size} usable"
        )

    alpha = (1.0 - ci) / 2.0
    percentile_low = float(np.quantile(diffs, alpha))
    percentile_high = float(np.quantile(diffs, 1.0 - alpha))

    # BCa for cluster bootstrap.
    z0 = sp_stats.norm.ppf(np.mean(diffs < point_estimate))
    if not np.isfinite(z0):
        z0 = 0.0
    # Jackknife on clusters for acceleration.
    jack = np.empty(n_clusters, dtype=float)
    for i in range(n_clusters):
        mask = np.ones(n_clusters, dtype=bool)
        mask[i] = False
        jack[i] = cluster_diff(clusters[mask])
    jack = jack[~np.isnan(jack)]
    jack_mean = float(np.mean(jack)) if jack.size else point_estimate
    num = float(np.sum((jack_mean - jack) ** 3))
    den = 6.0 * float(np.sum((jack_mean - jack) ** 2)) ** 1.5
    accel = num / den if den != 0 else 0.0

    z_alpha_lo = sp_stats.norm.ppf(alpha)
    z_alpha_hi = sp_stats.norm.ppf(1.0 - alpha)
    a_lo = sp_stats.norm.cdf(z0 + (z0 + z_alpha_lo) / (1.0 - accel * (z0 + z_alpha_lo)))
    a_hi = sp_stats.norm.cdf(z0 + (z0 + z_alpha_hi) / (1.0 - accel * (z0 + z_alpha_hi)))
    bca_low = float(np.quantile(diffs, np.clip(a_lo, 0.001, 0.999)))
    bca_high = float(np.quantile(diffs, np.clip(a_hi, 0.001, 0.999)))

    a_runs = work[work[group_col] == group_a]
    b_runs = work[work[group_col] == group_b]
    return BootstrapDiffCI(
        mean_a=float(a_runs[value_col].mean()),
        mean_b=float(b_runs[value_col].mean()),
        diff=point_estimate,
        n_a=int(a_runs.shape[0]),
        n_b=int(b_runs.shape[0]),
        n_iter=int(diffs.size),
        ci_level=float(ci),
        percentile_low=percentile_low,
        percentile_high=percentile_high,
        bca_low=bca_low,
        bca_high=bca_high,
        method=f"cluster({cluster_col})",
    )
