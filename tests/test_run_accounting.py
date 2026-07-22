"""Tests for the run-accounting CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from claude_benchmark.cli.commands.run_accounting import (
    classify_failure,
    load_aggregated,
    load_manifest,
    planned_count,
    walk_experiment,
)
from claude_benchmark.cli.main import app

runner = CliRunner()


# ---------- helpers ----------


def _write_manifest(base: Path, **overrides) -> None:
    base.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_name": "synthetic",
        "models": ["haiku"],
        "profiles": ["empty"],
        "tasks": ["t"],
        "variants": ["bare", "nice"],
        "runs_per_combination": 2,
        "total_runs": 4,
    }
    payload.update(overrides)
    (base / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_run(
    base: Path,
    *,
    model: str = "haiku",
    profile: str = "empty",
    task: str = "t",
    variant: str = "bare",
    run_n: int = 1,
    status: str = "success",
    error: str | None = None,
    has_llm: bool = True,
    degraded: bool = False,
    missing_scores: bool = False,
) -> Path:
    out_dir = base / model / profile / task / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "task_name": task,
        "profile_name": profile,
        "model": model,
        "run_number": run_n,
        "status": status,
        "variant_label": variant,
        "error": error,
    }
    if status == "success" and not missing_scores:
        scores: dict = {
            "static": {
                "test_pass_rate": 100.0,
                "lint_score": 100.0,
                "complexity_score": 100.0,
            },
            "degraded": degraded,
        }
        if has_llm:
            scores["llm"] = {
                "criteria": [{"score": 4}, {"score": 4}, {"score": 4}, {"score": 4}],
                "normalized": 75.0,
            }
        else:
            scores["llm"] = None
        payload["scores"] = scores
    elif status == "success" and missing_scores:
        payload["scores"] = None
    path = out_dir / f"run-{run_n}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------- failure classification ----------


def test_classify_failure_timeout():
    assert classify_failure("Operation timed out after 60s") == "timeout"


def test_classify_failure_api_400():
    assert classify_failure("Error code: 400 - bad request") == "api_error"


def test_classify_failure_rate_limit():
    assert classify_failure("HTTP 429 too many requests") == "rate_limit"


def test_classify_failure_auth():
    assert classify_failure("401 unauthorized") == "auth_error"


def test_classify_failure_unknown_when_none():
    assert classify_failure(None) == "unknown"


def test_classify_failure_other_when_no_match():
    assert classify_failure("totally unexpected explosion") == "other"


# ---------- walk_experiment ----------


def test_walk_experiment_counts_success_and_failure(tmp_path):
    base = tmp_path / "exp"
    _write_run(base, run_n=1, status="success")
    _write_run(base, run_n=2, status="success", degraded=True)
    _write_run(base, run_n=3, status="success", has_llm=False)
    _write_run(base, run_n=4, status="failure", error="Error code: 400 - bad request")
    _write_run(base, run_n=5, status="timeout")
    _write_run(
        base,
        variant="nice",
        run_n=1,
        status="failure",
        error="Operation timed out",
    )

    overall, per_cell = walk_experiment(base)

    assert overall.attempted == 6
    assert overall.succeeded == 3
    assert overall.failed == 3  # failure(2) + timeout(1) -> all counted as failed
    assert overall.timeout == 1
    assert overall.degraded == 1
    assert overall.scored_clean == 2  # success-non-degraded
    assert overall.judge_skipped == 1  # has_llm=False
    assert overall.judged == 2

    # failure breakdown
    assert overall.failure_reasons["api_error"] == 1
    assert overall.failure_reasons["timeout"] >= 1  # timeout-status + timeout-failure
    # per-cell preserves both bare and nice
    keys = {(k.model, k.variant) for k in per_cell.keys()}
    assert ("haiku", "bare") in keys
    assert ("haiku", "nice") in keys


def test_walk_experiment_handles_missing_scores(tmp_path):
    base = tmp_path / "exp"
    _write_run(base, run_n=1, status="success", missing_scores=True)
    overall, _ = walk_experiment(base)
    assert overall.score_missing == 1
    assert overall.scored_clean == 0


def test_walk_experiment_handles_corrupt_json(tmp_path):
    base = tmp_path / "exp"
    out_dir = base / "haiku" / "empty" / "t" / "bare"
    out_dir.mkdir(parents=True)
    (out_dir / "run-1.json").write_text("{not valid json", encoding="utf-8")
    overall, _ = walk_experiment(base)
    assert overall.attempted == 1
    assert overall.failed == 1
    assert overall.failure_reasons["parse_error"] == 1


# ---------- planned count ----------


def test_planned_count_from_manifest_total_runs(tmp_path):
    base = tmp_path / "exp"
    _write_manifest(base, total_runs=42)
    assert planned_count(load_manifest(base), load_aggregated(base)) == 42


def test_planned_count_falls_back_to_combination_math(tmp_path):
    base = tmp_path / "exp"
    _write_manifest(
        base,
        total_runs=None,
        models=["a", "b"],
        profiles=["empty"],
        tasks=["t1", "t2", "t3"],
        variants=["v1", "v2"],
        runs_per_combination=5,
    )
    # remove total_runs
    raw = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    raw.pop("total_runs", None)
    (base / "manifest.json").write_text(json.dumps(raw), encoding="utf-8")
    # 2 * 1 * 3 * 2 * 5 = 60
    assert planned_count(load_manifest(base), None) == 60


def test_planned_count_returns_none_without_data(tmp_path):
    base = tmp_path / "exp"
    base.mkdir()
    assert planned_count(None, None) is None


# ---------- CLI integration ----------


def test_run_accounting_cli_writes_report(tmp_path):
    base = tmp_path / "exp"
    _write_manifest(base, total_runs=3)
    _write_run(base, run_n=1)
    _write_run(base, run_n=2)
    _write_run(base, run_n=3, status="failure", error="Error 400")

    out = tmp_path / "acct.md"
    result = runner.invoke(app, ["run-accounting", str(base), "--output", str(out)])
    assert result.exit_code == 0, result.output

    text = out.read_text(encoding="utf-8")
    assert "Planned" in text
    assert "Attempted" in text
    assert "Mermaid" in text or "mermaid" in text
    assert "flowchart TD" in text
    assert "haiku" in text  # per-cell


def test_run_accounting_cli_all_experiments(tmp_path):
    parent = tmp_path / "results"
    exp_a = parent / "experiment-aaa"
    exp_b = parent / "experiment-bbb"
    _write_manifest(exp_a, total_runs=2)
    _write_run(exp_a, run_n=1)
    _write_run(exp_a, run_n=2)
    _write_manifest(exp_b, total_runs=2)
    _write_run(exp_b, run_n=1)
    _write_run(exp_b, run_n=2, status="failure", error="Error 500")

    out = tmp_path / "all.md"
    result = runner.invoke(
        app,
        ["run-accounting", str(parent), "--output", str(out), "--all-experiments"],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "experiment-aaa" in text
    assert "experiment-bbb" in text
    assert "TOTAL" in text


def test_run_accounting_cli_errors_on_missing_dir(tmp_path):
    missing = tmp_path / "nope"
    result = runner.invoke(app, ["run-accounting", str(missing)])
    assert result.exit_code != 0


def test_run_accounting_cli_all_experiments_without_subdirs_fails(tmp_path):
    empty_parent = tmp_path / "results"
    empty_parent.mkdir()
    result = runner.invoke(
        app, ["run-accounting", str(empty_parent), "--all-experiments"]
    )
    assert result.exit_code != 0
