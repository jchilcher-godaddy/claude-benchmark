"""Statistical rigor analysis package.

Provides mixed-effects models, multiple-comparisons corrections, bootstrap CIs,
and power analysis for nested benchmark data (runs within task x model x variant).
"""

from __future__ import annotations

from claude_benchmark.analysis.bootstrap import (
    bootstrap_diff_ci,
    cluster_bootstrap_diff_ci,
)
from claude_benchmark.analysis.corrections import correct_pvalues
from claude_benchmark.analysis.loader import (
    LoadStats,
    load_runs,
    load_runs_multi,
)
from claude_benchmark.analysis.mixed_effects import (
    MixedEffectsResult,
    fit_mixed_effects,
)
from claude_benchmark.analysis.power import PowerResult, compute_power

__all__ = [
    "LoadStats",
    "MixedEffectsResult",
    "PowerResult",
    "bootstrap_diff_ci",
    "cluster_bootstrap_diff_ci",
    "compute_power",
    "correct_pvalues",
    "fit_mixed_effects",
    "load_runs",
    "load_runs_multi",
]
