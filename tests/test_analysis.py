"""Unit tests for the statistical rigor analysis package.

All tests synthesize their own data; nothing on disk and no API calls.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from claude_benchmark.analysis.bootstrap import (
    bootstrap_diff_ci,
    cluster_bootstrap_diff_ci,
)
from claude_benchmark.analysis.corrections import correct_pvalues
from claude_benchmark.analysis.loader import TIDY_COLUMNS, load_runs
from claude_benchmark.analysis.mixed_effects import fit_mixed_effects
from claude_benchmark.analysis.power import compute_power


# --------------------------------------------------------------------------
# Loader
# --------------------------------------------------------------------------


def _write_run(
    base: Path,
    *,
    model: str,
    profile: str,
    task: str,
    variant: str,
    run_number: int,
    composite: float,
    status: str = "success",
    extra: dict | None = None,
) -> Path:
    leaf = base / model / profile / task / variant
    leaf.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_name": task,
        "profile_name": profile,
        "model": model,
        "run_number": run_number,
        "status": status,
        "input_tokens": 100,
        "output_tokens": 200,
        "cost": 0.001,
        "scores": {
            "composite": {
                "composite": composite,
                "static_score": {
                    "test_pass_rate": 100.0,
                    "lint_score": 100.0,
                    "complexity_score": 90.0,
                },
                "llm_score": {"normalized": 95.0},
            }
        },
        "variant_label": variant,
    }
    if extra:
        payload.update(extra)
    path = leaf / f"run-{run_number}.json"
    path.write_text(json.dumps(payload))
    return path


def test_loader_shape_and_dtypes(tmp_path: Path) -> None:
    base = tmp_path / "experiment-toy-20260101-000000"
    base.mkdir()
    for run_n in (1, 2, 3):
        _write_run(
            base,
            model="haiku",
            profile="empty",
            task="bug-fix-01",
            variant="bare",
            run_number=run_n,
            composite=80.0 + run_n,
        )
        _write_run(
            base,
            model="haiku",
            profile="empty",
            task="bug-fix-01",
            variant="kitchen-sink",
            run_number=run_n,
            composite=85.0 + run_n,
        )
    # One failure that should be excluded.
    _write_run(
        base,
        model="haiku",
        profile="empty",
        task="bug-fix-01",
        variant="bare",
        run_number=99,
        composite=0.0,
        status="failed",
    )

    df, stats = load_runs(base)
    assert list(df.columns) == list(TIDY_COLUMNS)
    assert stats.runs_loaded == 6
    assert stats.runs_skipped_status == 1
    assert df["composite"].dtype.kind == "f"
    assert df["run_number"].dtype.name in ("Int64",)
    assert set(df["variant"]) == {"bare", "kitchen-sink"}


def test_loader_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_runs(tmp_path / "does-not-exist")


# --------------------------------------------------------------------------
# Mixed effects
# --------------------------------------------------------------------------


def _synthetic_panel(
    *,
    n_tasks: int = 8,
    n_models: int = 2,
    n_runs: int = 6,
    true_effect: float = 5.0,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for t in range(n_tasks):
        task_intercept = rng.normal(70.0, 5.0)
        for m in range(n_models):
            model_intercept = rng.normal(0.0, 2.0)
            for variant, treat in (("bare", 0.0), ("kitchen-sink", true_effect)):
                for r in range(n_runs):
                    score = task_intercept + model_intercept + treat + rng.normal(0.0, 1.0)
                    rows.append(
                        {
                            "experiment": "synthetic",
                            "model": f"m{m}",
                            "profile": "empty",
                            "task": f"t{t}",
                            "variant": variant,
                            "run_number": r + 1,
                            "composite": float(score),
                            "status": "success",
                        }
                    )
    return pd.DataFrame(rows)


def test_mixed_effects_recovers_known_effect() -> None:
    df = _synthetic_panel(true_effect=5.0, seed=1)
    result = fit_mixed_effects(df, reference_variant="bare")
    assert result.n_obs == len(df)
    treatment_rows = [
        fe for fe in result.fixed_effects if "kitchen-sink" in fe.name and "T." in fe.name
    ]
    assert treatment_rows, f"no treatment row found in {[fe.name for fe in result.fixed_effects]}"
    coef = treatment_rows[0].coef
    assert 4.0 < coef < 6.0, f"expected ~5.0, got {coef}"
    assert treatment_rows[0].p_value < 0.001
    # Variance components should be populated.
    assert "residual" in result.variance_components


def test_mixed_effects_falls_back_when_underspecified() -> None:
    # Single task forces MixedLM to have no group variation; the fallback
    # path should still produce a usable result.
    df = _synthetic_panel(n_tasks=1, n_runs=8, true_effect=3.0, seed=2)
    df = df[df["task"] == "t0"].copy()
    result = fit_mixed_effects(df, reference_variant="bare")
    assert result.n_obs == len(df)
    # Either MixedLM converged on degenerate input or we fell back; both ok.
    assert any("kitchen-sink" in fe.name for fe in result.fixed_effects)


# --------------------------------------------------------------------------
# Corrections
# --------------------------------------------------------------------------


def test_holm_bonferroni_handworked() -> None:
    # Classic Holm example: m=4 raw p-values [0.01, 0.04, 0.03, 0.005].
    # Sorted: 0.005, 0.01, 0.03, 0.04.
    # Holm: 0.005*4=0.020, 0.01*3=0.030, 0.03*2=0.060, 0.04*1=0.040.
    # After monotonicity (cummax along sorted): 0.020, 0.030, 0.060, 0.060.
    raw = {"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.005}
    df = correct_pvalues(raw, alpha=0.05)
    expected = {"d": 0.020, "a": 0.030, "c": 0.060, "b": 0.060}
    for name, exp in expected.items():
        row = df[df["contrast"] == name].iloc[0]
        assert math.isclose(row["p_holm"], exp, rel_tol=1e-9, abs_tol=1e-9)
    # BH adjusted: sorted p * m / rank = 0.020, 0.020, 0.040, 0.040 (after monotonic).
    for name, exp in {"d": 0.020, "a": 0.020, "c": 0.040, "b": 0.040}.items():
        row = df[df["contrast"] == name].iloc[0]
        assert math.isclose(row["p_bh"], exp, rel_tol=1e-9, abs_tol=1e-9)
    # Significance flags at alpha=0.05:
    #   Holm: only 'd' (0.020) and 'a' (0.030) are below 0.05.
    sig_holm = set(df[df["sig_holm"]]["contrast"])
    assert sig_holm == {"d", "a"}


def test_corrections_empty_input() -> None:
    df = correct_pvalues({})
    assert df.empty
    assert list(df.columns) == [
        "contrast",
        "p_raw",
        "p_holm",
        "p_bh",
        "sig_raw",
        "sig_holm",
        "sig_bh",
    ]


def test_corrections_rejects_bad_p() -> None:
    with pytest.raises(ValueError):
        correct_pvalues({"x": 1.5})


# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------


def test_bootstrap_ci_contains_truth() -> None:
    rng = np.random.default_rng(123)
    a = rng.normal(0.0, 1.0, size=200)
    b = rng.normal(2.0, 1.0, size=200)
    res = bootstrap_diff_ci(a, b, n_iter=2000, seed=42)
    # True diff = 2.0; both CI methods should bracket it.
    assert res.percentile_low < 2.0 < res.percentile_high
    assert res.bca_low < 2.0 < res.bca_high
    assert res.percentile_high - res.percentile_low < 1.0


def test_cluster_bootstrap_ci() -> None:
    rng = np.random.default_rng(7)
    rows: list[dict] = []
    n_tasks = 12
    for t in range(n_tasks):
        task_eff = rng.normal(0.0, 3.0)
        for variant, mean in (("bare", 70.0), ("treat", 75.0)):
            for r in range(8):
                rows.append(
                    {
                        "task": f"t{t}",
                        "variant": variant,
                        "composite": mean + task_eff + rng.normal(0.0, 1.0),
                    }
                )
    df = pd.DataFrame(rows)
    res = cluster_bootstrap_diff_ci(
        df,
        value_col="composite",
        group_col="variant",
        cluster_col="task",
        group_a="bare",
        group_b="treat",
        n_iter=1000,
        seed=42,
    )
    # True diff = 5.0; CI should bracket it.
    assert res.percentile_low < 5.0 < res.percentile_high
    assert res.method.startswith("cluster(")


# --------------------------------------------------------------------------
# Power
# --------------------------------------------------------------------------


def test_compute_power_paired_known_effect() -> None:
    # Construct task means with d ~ 1.0 (large): mean diff 5, sd of diffs 5.
    # Use n_tasks=10 paired observations.
    diffs = np.array([0.0, 5.0, 10.0, 5.0, 5.0, 10.0, 0.0, 5.0, 10.0, 0.0], dtype=float)
    rows = []
    bare_vals = np.full_like(diffs, 70.0)
    treat_vals = bare_vals + diffs
    for i, (a_val, b_val) in enumerate(zip(bare_vals, treat_vals, strict=True)):
        rows.append({"task": f"t{i}", "variant": "bare", "composite": float(a_val)})
        rows.append({"task": f"t{i}", "variant": "treat", "composite": float(b_val)})
    df = pd.DataFrame(rows)
    res = compute_power(df, group_a="bare", group_b="treat")
    assert res.paired is True
    assert res.n_paired == 10
    # mean diff = 5.0, sd diff = ~4.0825 (population) or sample sd ~4.30
    assert math.isclose(res.mean_b - res.mean_a, 5.0, abs_tol=1e-9)
    assert 0.5 < res.cohens_d < 1.5
    # Achieved power should be between 0 and 1.
    assert 0.0 <= res.achieved_power <= 1.0
    # MDE in raw score units: with n=10, alpha=0.05, power=0.80, paired t.
    # Roughly d=0.965 -> MDE ~ 0.965 * sd_diff. Check it's positive and finite.
    assert res.mde_d > 0
    assert math.isfinite(res.mde_score) and res.mde_score > 0


def test_compute_power_unpaired_when_clusters_diverge() -> None:
    rows = []
    for i in range(6):
        rows.append({"task": f"t{i}", "variant": "bare", "composite": 70.0 + i})
    for i in range(6):
        rows.append({"task": f"u{i}", "variant": "treat", "composite": 75.0 + i})
    df = pd.DataFrame(rows)
    res = compute_power(df, group_a="bare", group_b="treat")
    assert res.paired is False
    assert res.n_paired == 0
    assert res.cohens_d != 0
