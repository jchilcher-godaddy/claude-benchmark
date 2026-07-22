"""Tests for the sensitivity CLI command and re_aggregate logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from claude_benchmark.cli.commands.sensitivity import (
    DEFAULT_SPLITS,
    DEFAULT_STATIC_GRIDS,
    Regime,
    RunRecord,
    _parse_split_list,
    _parse_static_grids,
    build_regimes,
    composite_for_run,
    compute_robustness,
    extract_run_record,
    llm_normalized_from_criteria,
    load_runs,
    re_aggregate,
)
from claude_benchmark.cli.main import app

runner = CliRunner()


# ---------- helpers ----------


def _write_run(
    base: Path,
    *,
    model: str,
    profile: str,
    task: str,
    variant: str,
    run_n: int,
    test_pass_rate: float,
    lint_score: float,
    complexity_score: float,
    llm_avg: float | None = 4.0,
    status: str = "success",
) -> Path:
    """Write a synthetic run-N.json under model/profile/task/variant/."""
    out_dir = base / model / profile / task / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "task_name": task,
        "profile_name": profile,
        "model": model,
        "run_number": run_n,
        "status": status,
        "variant_label": variant,
    }
    if status == "success":
        scores: dict = {
            "static": {
                "test_pass_rate": test_pass_rate,
                "lint_score": lint_score,
                "complexity_score": complexity_score,
                "weighted_total": 0.5 * test_pass_rate
                + 0.3 * lint_score
                + 0.2 * complexity_score,
            }
        }
        if llm_avg is not None:
            criteria = [
                {"name": "code_readability", "score": llm_avg},
                {"name": "architecture_quality", "score": llm_avg},
                {"name": "instruction_adherence", "score": llm_avg},
                {"name": "correctness_reasoning", "score": llm_avg},
            ]
            scores["llm"] = {
                "criteria": criteria,
                "average": llm_avg,
                "normalized": (llm_avg - 1.0) * 25.0,
                "model_used": "haiku",
            }
        else:
            scores["llm"] = None
        payload["scores"] = scores
    path = out_dir / f"run-{run_n}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------- parser tests ----------


def test_parse_split_list_basic():
    assert _parse_split_list("0.3,0.5,0.7") == [0.3, 0.5, 0.7]


def test_parse_split_list_rejects_out_of_range():
    with pytest.raises(Exception):
        _parse_split_list("0.5,1.5")


def test_parse_static_grids_basic():
    out = _parse_static_grids("0.5,0.3,0.2;0.4,0.3,0.3")
    assert out == [(0.5, 0.3, 0.2), (0.4, 0.3, 0.3)]


def test_parse_static_grids_rejects_bad_sum():
    with pytest.raises(Exception):
        _parse_static_grids("0.5,0.3,0.3")


def test_parse_static_grids_rejects_wrong_arity():
    with pytest.raises(Exception):
        _parse_static_grids("0.5,0.5")


def test_default_grid_construction():
    regimes = build_regimes(DEFAULT_SPLITS, DEFAULT_STATIC_GRIDS)
    assert len(regimes) == len(DEFAULT_SPLITS) * len(DEFAULT_STATIC_GRIDS)
    assert any(r.is_default() for r in regimes)


# ---------- normalization & extraction ----------


def test_llm_normalized_from_criteria():
    crit = [{"score": 4}, {"score": 4}, {"score": 4}, {"score": 4}]
    assert llm_normalized_from_criteria(crit) == pytest.approx(75.0)
    assert llm_normalized_from_criteria([]) is None


def test_extract_run_record_full():
    payload = {
        "status": "success",
        "model": "haiku",
        "variant_label": "bare",
        "scores": {
            "static": {
                "test_pass_rate": 80.0,
                "lint_score": 90.0,
                "complexity_score": 100.0,
            },
            "llm": {
                "criteria": [{"score": 4}, {"score": 4}, {"score": 4}, {"score": 4}],
                "normalized": 75.0,
            },
        },
    }
    rec = extract_run_record(payload)
    assert rec is not None
    assert rec.variant == "bare"
    assert rec.test_pass_rate == 80.0
    assert rec.llm_normalized == 75.0


def test_extract_run_record_failure_returns_none():
    payload = {"status": "failure", "scores": None}
    assert extract_run_record(payload) is None


def test_extract_run_record_static_only():
    payload = {
        "status": "success",
        "scores": {
            "static": {"test_pass_rate": 50.0, "lint_score": 50.0, "complexity_score": 50.0},
            "llm": None,
        },
    }
    rec = extract_run_record(payload)
    assert rec is not None
    assert rec.llm_normalized is None


def test_extract_run_record_falls_back_to_criteria_when_normalized_missing():
    payload = {
        "status": "success",
        "scores": {
            "static": {"test_pass_rate": 80.0, "lint_score": 80.0, "complexity_score": 80.0},
            "llm": {"criteria": [{"score": 5}, {"score": 3}, {"score": 4}, {"score": 4}]},
        },
    }
    rec = extract_run_record(payload)
    # avg = 4.0 -> normalized = 75.0
    assert rec.llm_normalized == pytest.approx(75.0)


# ---------- math tests ----------


def test_composite_default_regime_matches_existing_formula():
    run = RunRecord(
        variant="bare",
        model="haiku",
        test_pass_rate=100.0,
        lint_score=100.0,
        complexity_score=100.0,
        llm_normalized=75.0,
    )
    regime = Regime(0.5, (0.5, 0.3, 0.2))
    # static weighted = 100; composite = 0.5*100 + 0.5*75 = 87.5
    assert composite_for_run(run, regime) == pytest.approx(87.5)


def test_composite_static_only_skips_llm():
    run = RunRecord("bare", "h", 100.0, 80.0, 60.0, None)
    regime = Regime(0.5, (0.5, 0.3, 0.2))
    # static_weighted = 50 + 24 + 12 = 86; LLM None -> composite = 86
    assert composite_for_run(run, regime) == pytest.approx(86.0)


def test_composite_with_higher_static_weight():
    run = RunRecord("bare", "h", 100.0, 100.0, 100.0, 50.0)
    regime = Regime(0.7, (0.5, 0.3, 0.2))
    # static_weighted=100, llm=50 -> 0.7*100 + 0.3*50 = 85
    assert composite_for_run(run, regime) == pytest.approx(85.0)


def test_re_aggregate_groups_by_variant():
    runs = [
        RunRecord("bare", "h", 100.0, 100.0, 100.0, 50.0),
        RunRecord("bare", "h", 50.0, 50.0, 50.0, 50.0),
        RunRecord("nice", "h", 80.0, 80.0, 80.0, 80.0),
    ]
    regimes = [Regime(0.5, (0.5, 0.3, 0.2))]
    out = re_aggregate(runs, regimes)
    assert set(out.keys()) == {"bare", "nice"}
    label = regimes[0].label
    # bare static: avg of (100, 50) = 75; composite per regime = 0.5*75+0.5*50 = 62.5
    assert out["bare"][label] == pytest.approx(62.5)
    # nice: 0.5*80+0.5*80 = 80
    assert out["nice"][label] == pytest.approx(80.0)


# ---------- robustness ----------


def test_robustness_sign_stable_when_variant_always_beats_control():
    means = {
        "bare": {"r1": 50.0, "r2": 50.0, "r3": 50.0},
        "good": {"r1": 60.0, "r2": 65.0, "r3": 70.0},
    }
    # stub regimes with matching labels
    fake_regimes = [
        Regime(0.5, (0.5, 0.3, 0.2)),
        Regime(0.4, (0.5, 0.3, 0.2)),
        Regime(0.6, (0.5, 0.3, 0.2)),
    ]
    # remap labels
    means = {
        "bare": {fake_regimes[i].label: 50.0 for i in range(3)},
        "good": {
            fake_regimes[0].label: 60.0,
            fake_regimes[1].label: 65.0,
            fake_regimes[2].label: 70.0,
        },
    }
    rob = compute_robustness(means, fake_regimes, "bare")
    assert rob["good"]["sign_stable_pct"] == pytest.approx(100.0)
    assert rob["good"]["always_beats"] is True
    assert rob["good"]["flips"] == 0


def test_robustness_detects_sign_flip():
    fake_regimes = [
        Regime(0.5, (0.5, 0.3, 0.2)),
        Regime(0.4, (0.5, 0.3, 0.2)),
    ]
    # default = 0.5 (regime 0). Variant beats control there but loses in regime 1.
    means = {
        "bare": {fake_regimes[0].label: 50.0, fake_regimes[1].label: 50.0},
        "flippy": {fake_regimes[0].label: 55.0, fake_regimes[1].label: 45.0},
    }
    rob = compute_robustness(means, fake_regimes, "bare")
    assert rob["flippy"]["always_beats"] is False
    assert rob["flippy"]["always_loses"] is False
    assert rob["flippy"]["flips"] == 1
    assert rob["flippy"]["sign_stable_pct"] == pytest.approx(50.0)


def test_robustness_control_self_is_100():
    fake_regimes = [Regime(0.5, (0.5, 0.3, 0.2))]
    means = {"bare": {fake_regimes[0].label: 50.0}}
    rob = compute_robustness(means, fake_regimes, "bare")
    assert rob["bare"]["sign_stable_pct"] == 100.0


# ---------- load_runs end-to-end ----------


def test_load_runs_walks_synthetic_dir(tmp_path):
    base = tmp_path / "exp"
    _write_run(
        base,
        model="haiku",
        profile="empty",
        task="task-a",
        variant="bare",
        run_n=1,
        test_pass_rate=100.0,
        lint_score=100.0,
        complexity_score=100.0,
        llm_avg=4.0,
    )
    _write_run(
        base,
        model="haiku",
        profile="empty",
        task="task-a",
        variant="nice",
        run_n=1,
        test_pass_rate=80.0,
        lint_score=80.0,
        complexity_score=80.0,
        llm_avg=5.0,
    )
    _write_run(
        base,
        model="haiku",
        profile="empty",
        task="task-a",
        variant="bare",
        run_n=2,
        test_pass_rate=0.0,
        lint_score=0.0,
        complexity_score=0.0,
        llm_avg=None,
        status="failure",
    )
    runs = load_runs(base)
    assert len(runs) == 2
    variants = {r.variant for r in runs}
    assert variants == {"bare", "nice"}


# ---------- CLI integration ----------


def test_sensitivity_cli_writes_markdown(tmp_path):
    base = tmp_path / "exp"
    # write 3 runs of bare and 3 of nice
    for i in range(3):
        _write_run(
            base, model="haiku", profile="empty", task="t", variant="bare",
            run_n=i + 1,
            test_pass_rate=80.0, lint_score=80.0, complexity_score=80.0,
            llm_avg=4.0,
        )
        _write_run(
            base, model="haiku", profile="empty", task="t", variant="nice",
            run_n=i + 1,
            test_pass_rate=100.0, lint_score=100.0, complexity_score=100.0,
            llm_avg=5.0,
        )
    out = tmp_path / "sens.md"
    result = runner.invoke(
        app,
        ["sensitivity", str(base), "--output", str(out)],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "Sensitivity analysis" in text
    assert "bare" in text and "nice" in text
    assert "Robust winners" in text or "always beats" in text


def test_sensitivity_cli_rejects_bad_weights(tmp_path):
    base = tmp_path / "exp"
    base.mkdir()
    _write_run(
        base, model="haiku", profile="empty", task="t", variant="bare",
        run_n=1, test_pass_rate=100, lint_score=100, complexity_score=100,
    )
    result = runner.invoke(
        app,
        [
            "sensitivity",
            str(base),
            "--static-component-weights",
            "0.5,0.3,0.3",
        ],
    )
    assert result.exit_code != 0


def test_sensitivity_cli_errors_on_missing_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    result = runner.invoke(app, ["sensitivity", str(missing)])
    assert result.exit_code != 0
