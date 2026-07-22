"""Power and minimum-detectable-effect (MDE) analysis on task means.

Aggregating to one observation per task per arm (the natural cluster) gives
us paired/unpaired Cohen's d that we can plug into ``statsmodels`` power
calculators. The default reports Cohen's d, achieved power at alpha=0.05, and
the MDE at the requested power.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.stats.power import TTestIndPower, TTestPower


@dataclass
class PowerResult:
    """Container for a power analysis on a single contrast."""

    group_a: str
    group_b: str
    n_a: int
    n_b: int
    n_paired: int
    mean_a: float
    mean_b: float
    pooled_sd: float
    cohens_d: float
    achieved_power: float
    target_power: float
    alpha: float
    mde_d: float
    mde_score: float
    paired: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "group_a": self.group_a,
            "group_b": self.group_b,
            "n_a": self.n_a,
            "n_b": self.n_b,
            "n_paired": self.n_paired,
            "mean_a": self.mean_a,
            "mean_b": self.mean_b,
            "pooled_sd": self.pooled_sd,
            "cohens_d": self.cohens_d,
            "achieved_power": self.achieved_power,
            "target_power": self.target_power,
            "alpha": self.alpha,
            "mde_d": self.mde_d,
            "mde_score": self.mde_score,
            "paired": self.paired,
        }


def _task_means(
    df: pd.DataFrame,
    *,
    value_col: str,
    group_col: str,
    cluster_col: str,
) -> pd.DataFrame:
    return (
        df.groupby([cluster_col, group_col], observed=True)[value_col]
        .mean()
        .reset_index()
    )


def compute_power(
    df: pd.DataFrame,
    *,
    group_a: str,
    group_b: str,
    value_col: str = "composite",
    group_col: str = "variant",
    cluster_col: str = "task",
    alpha: float = 0.05,
    target_power: float = 0.80,
) -> PowerResult:
    """Compute Cohen's d, achieved power, and MDE on per-task means.

    Aggregates ``value_col`` to one mean per (cluster, group) cell, then runs
    a paired comparison if every cluster appears in both arms (the typical
    crossover layout) or an independent two-sample comparison otherwise.

    Returns a :class:`PowerResult` with all numerics. ``mde_score`` is the
    minimum detectable raw-score difference at the configured ``target_power``
    holding the observed pooled SD constant.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0, 1)")
    if not (0.0 < target_power < 1.0):
        raise ValueError("target_power must be in (0, 1)")

    needed = {value_col, group_col, cluster_col}
    missing = needed - set(df.columns)
    if missing:
        raise KeyError(f"missing columns: {sorted(missing)}")

    work = df.dropna(subset=[value_col, group_col, cluster_col])
    work = work[work[group_col].isin([group_a, group_b])]
    if work.empty:
        raise ValueError(
            f"no rows found for {group_a!r} / {group_b!r} in column {group_col!r}"
        )

    cell_means = _task_means(
        work, value_col=value_col, group_col=group_col, cluster_col=cluster_col
    )
    a_means = cell_means[cell_means[group_col] == group_a].set_index(cluster_col)[value_col]
    b_means = cell_means[cell_means[group_col] == group_b].set_index(cluster_col)[value_col]

    common = a_means.index.intersection(b_means.index)
    paired = len(common) >= 2 and len(common) == len(a_means) == len(b_means)

    if paired:
        diffs = (b_means.loc[common] - a_means.loc[common]).to_numpy()
        n_paired = int(diffs.size)
        sd_diff = float(np.std(diffs, ddof=1)) if n_paired > 1 else float("nan")
        cohens_d = float(np.mean(diffs) / sd_diff) if sd_diff > 0 else 0.0
        analysis = TTestPower()
        try:
            achieved = float(
                analysis.power(effect_size=abs(cohens_d), nobs=n_paired, alpha=alpha)
            )
        except Exception:  # noqa: BLE001
            achieved = float("nan")
        try:
            mde_d = float(
                analysis.solve_power(
                    effect_size=None,
                    nobs=n_paired,
                    alpha=alpha,
                    power=target_power,
                )
            )
        except Exception:  # noqa: BLE001
            mde_d = float("nan")
        mde_score = float(mde_d * sd_diff) if not np.isnan(mde_d) and sd_diff > 0 else float("nan")
        pooled_sd = sd_diff
        n_a = int(a_means.size)
        n_b = int(b_means.size)
    else:
        a = a_means.to_numpy()
        b = b_means.to_numpy()
        if a.size < 2 or b.size < 2:
            raise ValueError(
                f"need >= 2 clusters per arm; got n_a={a.size}, n_b={b.size}"
            )
        n_paired = int(len(common))
        var_a = float(np.var(a, ddof=1))
        var_b = float(np.var(b, ddof=1))
        # Pool with the two-sample independent formula.
        pooled_sd = float(
            np.sqrt(((a.size - 1) * var_a + (b.size - 1) * var_b) / (a.size + b.size - 2))
        )
        cohens_d = float((np.mean(b) - np.mean(a)) / pooled_sd) if pooled_sd > 0 else 0.0
        analysis = TTestIndPower()
        ratio = float(b.size / a.size) if a.size else 1.0
        try:
            achieved = float(
                analysis.power(
                    effect_size=abs(cohens_d),
                    nobs1=int(a.size),
                    alpha=alpha,
                    ratio=ratio,
                )
            )
        except Exception:  # noqa: BLE001
            achieved = float("nan")
        try:
            mde_d = float(
                analysis.solve_power(
                    effect_size=None,
                    nobs1=int(a.size),
                    alpha=alpha,
                    power=target_power,
                    ratio=ratio,
                )
            )
        except Exception:  # noqa: BLE001
            mde_d = float("nan")
        mde_score = float(mde_d * pooled_sd) if not np.isnan(mde_d) and pooled_sd > 0 else float("nan")
        n_a = int(a.size)
        n_b = int(b.size)

    return PowerResult(
        group_a=group_a,
        group_b=group_b,
        n_a=n_a,
        n_b=n_b,
        n_paired=n_paired,
        mean_a=float(a_means.mean()),
        mean_b=float(b_means.mean()),
        pooled_sd=pooled_sd,
        cohens_d=cohens_d,
        achieved_power=achieved,
        target_power=float(target_power),
        alpha=float(alpha),
        mde_d=mde_d,
        mde_score=mde_score,
        paired=paired,
    )
