"""Comprehensive tests for the reporting results loader (data bridge).

Tests cover both storage and parallel execution result formats, edge cases
(corrupt files, missing scores, empty directories), auto-detection of
the latest results directory, and filtering by task/profile/model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_benchmark.reporting.loader import (
    filter_results,
    find_latest_results,
    load_results_dir,
)
from claude_benchmark.reporting.models import (
    BenchmarkResults,
    ProfileResult,
    ReportMetadata,
    RunResult as ReportRunResult,
    TaskResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_manifest(
    results_dir: Path,
    *,
    models: list[str] | None = None,
    profiles: list[str] | None = None,
    tasks: list[str] | None = None,
    runs_per_combination: int = 3,
) -> None:
    """Write a manifest.json into *results_dir*."""
    models = models or ["sonnet", "opus"]
    profiles = profiles or ["test"]
    tasks = tasks or ["code-gen-01", "bug-fix-01"]
    manifest = {
        "timestamp": "2026-02-26T15:18:33",
        "models": models,
        "profiles": profiles,
        "tasks": tasks,
        "runs_per_combination": runs_per_combination,
        "total_combinations": len(models) * len(profiles) * len(tasks),
        "total_runs": len(models)
        * len(profiles)
        * len(tasks)
        * runs_per_combination,
        "cli_args": {},
    }
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def _make_storage_run(
    results_dir: Path,
    model: str,
    profile: str,
    task: str,
    run_number: int,
    *,
    success: bool = True,
    input_tokens: int = 1000,
    output_tokens: int = 500,
    error: str | None = None,
) -> Path:
    """Create a storage-format run file (``run_{NNN}.json``)."""
    run_dir = results_dir / "runs" / model / profile / task
    run_dir.mkdir(parents=True, exist_ok=True)
    filename = f"run_{run_number:03d}.json"
    data = {
        "run_number": run_number,
        "success": success,
        "wall_clock_seconds": 1.5,
        "duration_ms": 0,
        "duration_api_ms": 0,
        "total_cost_usd": None,
        "num_turns": 0,
        "session_id": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
        "output_files": {},
        "error": error,
        "timestamp": "2026-02-26T15:18:33",
    }
    path = run_dir / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_parallel_run(
    results_dir: Path,
    model: str,
    profile: str,
    task: str,
    run_number: int,
    *,
    scores: dict[str, float] | None = None,
    total_tokens: int = 1500,
    status: str = "success",
    error: str | None = None,
) -> Path:
    """Create a parallel-format run file (``run-{N}.json``)."""
    run_dir = results_dir / model / profile / task
    run_dir.mkdir(parents=True, exist_ok=True)
    filename = f"run-{run_number}.json"
    data = {
        "task_name": task,
        "profile_name": profile,
        "model": model,
        "run_number": run_number,
        "result_key": f"{model}/{profile}/{task}/run-{run_number}",
        "status": status,
        "error": error,
        "output_dir": None,
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_tokens": total_tokens,
        "cost": 0.01,
        "duration_seconds": 1.5,
        "scores": scores,
    }
    path = run_dir / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def storage_results(tmp_path: Path) -> Path:
    """Create a complete storage-format results directory."""
    results_dir = tmp_path / "results" / "20260226_151821_686"
    _write_manifest(results_dir)
    for model in ("sonnet", "opus"):
        for task in ("code-gen-01", "bug-fix-01"):
            for run_num in range(1, 4):
                _make_storage_run(
                    results_dir, model, "test", task, run_num
                )
    return results_dir


@pytest.fixture()
def parallel_results(tmp_path: Path) -> Path:
    """Create a complete parallel-format results directory."""
    results_dir = tmp_path / "results" / "20260226_160000"
    _write_manifest(results_dir)
    for model in ("sonnet", "opus"):
        for task in ("code-gen-01", "bug-fix-01"):
            for run_num in range(1, 4):
                _make_parallel_run(
                    results_dir,
                    model,
                    "test",
                    task,
                    run_num,
                    scores={"correctness": 85.0, "style": 72.0},
                )
    return results_dir


# ---------------------------------------------------------------------------
# Tests: load_results_dir -- storage format
# ---------------------------------------------------------------------------


class TestLoadStorageFormat:
    """Tests for loading storage-format results."""

    def test_returns_benchmark_results(self, storage_results: Path) -> None:
        result = load_results_dir(storage_results)
        assert isinstance(result, BenchmarkResults)

    def test_correct_profile_count(self, storage_results: Path) -> None:
        result = load_results_dir(storage_results)
        assert len(result.profiles) == 1
        assert "test" in result.profiles

    def test_correct_models_list(self, storage_results: Path) -> None:
        result = load_results_dir(storage_results)
        assert sorted(result.models) == ["opus", "sonnet"]

    def test_correct_tasks_list(self, storage_results: Path) -> None:
        result = load_results_dir(storage_results)
        assert sorted(result.tasks) == ["bug-fix-01", "code-gen-01"]

    def test_correct_run_count(self, storage_results: Path) -> None:
        result = load_results_dir(storage_results)
        profile = result.profiles["test"]
        # 2 models x 3 runs = 6 runs per task
        for task_result in profile.tasks.values():
            assert len(task_result.runs) == 6

    def test_token_aggregation(self, storage_results: Path) -> None:
        result = load_results_dir(storage_results)
        profile = result.profiles["test"]
        # Each run: 1000 input + 500 output = 1500 tokens
        # 2 models x 2 tasks x 3 runs = 12 runs total
        assert profile.total_tokens == 12 * 1500

    def test_success_and_error_mapped(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "res"
        _write_manifest(results_dir, models=["sonnet"], tasks=["t1"])
        _make_storage_run(
            results_dir,
            "sonnet",
            "test",
            "t1",
            1,
            success=True,
        )
        _make_storage_run(
            results_dir,
            "sonnet",
            "test",
            "t1",
            2,
            success=False,
            error="Command failed",
        )
        result = load_results_dir(results_dir)
        runs = result.profiles["test"].tasks["t1"].runs
        successes = [r for r in runs if r.success]
        failures = [r for r in runs if not r.success]
        assert len(successes) == 1
        assert len(failures) == 1
        assert failures[0].error == "Command failed"

    def test_metadata_total_runs(self, storage_results: Path) -> None:
        result = load_results_dir(storage_results)
        assert result.metadata.total_runs == 12  # 2 models x 2 tasks x 3 runs


# ---------------------------------------------------------------------------
# Tests: load_results_dir -- parallel format
# ---------------------------------------------------------------------------


class TestLoadParallelFormat:
    """Tests for loading parallel-format results."""

    def test_returns_benchmark_results(
        self, parallel_results: Path
    ) -> None:
        result = load_results_dir(parallel_results)
        assert isinstance(result, BenchmarkResults)

    def test_scores_populated(self, parallel_results: Path) -> None:
        result = load_results_dir(parallel_results)
        profile = result.profiles["test"]
        for task_result in profile.tasks.values():
            for run in task_result.runs:
                assert "correctness" in run.scores
                assert "style" in run.scores
                assert run.scores["correctness"] == 85.0
                assert run.scores["style"] == 72.0

    def test_mean_scores_computed(self, parallel_results: Path) -> None:
        result = load_results_dir(parallel_results)
        profile = result.profiles["test"]
        for task_result in profile.tasks.values():
            assert task_result.mean_scores["correctness"] == pytest.approx(
                85.0
            )
            assert task_result.mean_scores["style"] == pytest.approx(72.0)

    def test_std_scores_computed(self, parallel_results: Path) -> None:
        result = load_results_dir(parallel_results)
        profile = result.profiles["test"]
        for task_result in profile.tasks.values():
            # All scores identical -> stdev = 0
            assert task_result.std_scores["correctness"] == pytest.approx(0.0)

    def test_token_counts(self, parallel_results: Path) -> None:
        result = load_results_dir(parallel_results)
        profile = result.profiles["test"]
        for task_result in profile.tasks.values():
            for run in task_result.runs:
                assert run.token_count == 1500


# ---------------------------------------------------------------------------
# Tests: load_results_dir -- edge cases
# ---------------------------------------------------------------------------


class TestLoadEdgeCases:
    """Tests for edge cases in results loading."""

    def test_load_no_manifest(self, tmp_path: Path) -> None:
        """Loader works without manifest.json (infers from directory)."""
        results_dir = tmp_path / "no_manifest"
        results_dir.mkdir()
        _make_storage_run(results_dir, "sonnet", "test", "task1", 1)
        result = load_results_dir(results_dir)
        assert isinstance(result, BenchmarkResults)
        assert len(result.profiles) == 1
        assert result.profiles["test"].tasks["task1"].runs[0].model == "sonnet"

    def test_load_missing_scores_null(self, tmp_path: Path) -> None:
        """Parallel run with scores: null does not crash."""
        results_dir = tmp_path / "null_scores"
        _write_manifest(results_dir, models=["s"], tasks=["t"])
        _make_parallel_run(
            results_dir, "s", "test", "t", 1, scores=None
        )
        result = load_results_dir(results_dir)
        run = result.profiles["test"].tasks["t"].runs[0]
        assert run.scores == {}

    def test_load_corrupt_file(self, tmp_path: Path) -> None:
        """Corrupt JSON files are skipped, not fatal."""
        results_dir = tmp_path / "corrupt"
        _write_manifest(results_dir, models=["m"], tasks=["t"])
        # One valid file
        _make_parallel_run(
            results_dir, "m", "test", "t", 1, scores={"x": 50.0}
        )
        # One corrupt file
        corrupt_dir = results_dir / "m" / "test" / "t"
        (corrupt_dir / "run-2.json").write_text("NOT JSON{{{", encoding="utf-8")

        result = load_results_dir(results_dir)
        assert len(result.profiles["test"].tasks["t"].runs) == 1

    def test_load_empty_dir(self, tmp_path: Path) -> None:
        """Empty results dir with manifest returns empty profiles."""
        results_dir = tmp_path / "empty"
        _write_manifest(results_dir)
        result = load_results_dir(results_dir)
        assert result.profiles == {}
        assert result.models == ["sonnet", "opus"]
        assert result.tasks == ["code-gen-01", "bug-fix-01"]

    def test_load_nonexistent_dir(self, tmp_path: Path) -> None:
        """FileNotFoundError raised with helpful message."""
        with pytest.raises(FileNotFoundError, match="Results directory not found"):
            load_results_dir(tmp_path / "does_not_exist")

    def test_load_mixed_formats(self, tmp_path: Path) -> None:
        """Directory with both storage and parallel files loads and merges."""
        results_dir = tmp_path / "mixed"
        _write_manifest(
            results_dir, models=["sonnet"], tasks=["t1", "t2"]
        )
        # Storage format for t1
        _make_storage_run(results_dir, "sonnet", "test", "t1", 1)
        # Parallel format for t2
        _make_parallel_run(
            results_dir, "sonnet", "test", "t2", 1, scores={"x": 90.0}
        )
        result = load_results_dir(results_dir)
        assert "t1" in result.profiles["test"].tasks
        assert "t2" in result.profiles["test"].tasks
        # t1 from storage has no scores
        assert result.profiles["test"].tasks["t1"].runs[0].scores == {}
        # t2 from parallel has scores
        assert result.profiles["test"].tasks["t2"].runs[0].scores["x"] == 90.0


# ---------------------------------------------------------------------------
# Tests: find_latest_results
# ---------------------------------------------------------------------------


class TestFindLatestResults:
    """Tests for find_latest_results() auto-detection."""

    def test_basic(self, tmp_path: Path) -> None:
        """Returns the most recent directory with manifest.json."""
        base = tmp_path / "results"
        for name in ("20260226_100000_000", "20260226_120000_000", "20260226_150000_000"):
            d = base / name
            d.mkdir(parents=True)
            (d / "manifest.json").write_text("{}", encoding="utf-8")

        # Add one without manifest (should be skipped even if newer name)
        (base / "20260226_200000_000").mkdir()

        result = find_latest_results(base)
        assert result is not None
        assert result.name == "20260226_150000_000"

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Returns None when base dir has no subdirectories."""
        base = tmp_path / "results"
        base.mkdir()
        assert find_latest_results(base) is None

    def test_no_manifest(self, tmp_path: Path) -> None:
        """Returns None when no directories contain manifest.json."""
        base = tmp_path / "results"
        (base / "20260226_100000").mkdir(parents=True)
        (base / "20260226_200000").mkdir(parents=True)
        assert find_latest_results(base) is None

    def test_mixed_naming_formats(self, tmp_path: Path) -> None:
        """Both YYYYMMDD_HHMMSS_fff and YYYYMMDD-HHMMSS naming handled."""
        base = tmp_path / "results"
        # Underscore format (older)
        d1 = base / "20260225_120000_000"
        d1.mkdir(parents=True)
        (d1 / "manifest.json").write_text("{}", encoding="utf-8")
        # Dash format (newer by name)
        d2 = base / "20260226-150000"
        d2.mkdir(parents=True)
        (d2 / "manifest.json").write_text("{}", encoding="utf-8")

        result = find_latest_results(base)
        assert result is not None
        assert result.name == "20260226-150000"

    def test_default_base_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Defaults to Path('results') when base_dir is None."""
        monkeypatch.chdir(tmp_path)
        base = tmp_path / "results"
        d = base / "20260226_100000_000"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text("{}", encoding="utf-8")

        result = find_latest_results()
        assert result is not None
        assert result.name == "20260226_100000_000"

    def test_nonexistent_base_dir(self, tmp_path: Path) -> None:
        """Returns None when base directory does not exist."""
        assert find_latest_results(tmp_path / "nope") is None


# ---------------------------------------------------------------------------
# Tests: filter_results
# ---------------------------------------------------------------------------


def _make_benchmark_results(
    profiles: list[str] | None = None,
    tasks: list[str] | None = None,
    models: list[str] | None = None,
    score_dims: dict[str, float] | None = None,
) -> BenchmarkResults:
    """Build a BenchmarkResults for filter testing."""
    profiles = profiles or ["empty", "minimal", "full"]
    tasks = tasks or ["code-gen-01", "bug-fix-01", "refactor-01"]
    models = models or ["sonnet", "opus"]
    score_dims = score_dims or {"correctness": 80.0, "style": 70.0}

    profile_dict: dict[str, ProfileResult] = {}
    for pname in profiles:
        tasks_dict: dict[str, TaskResult] = {}
        for tname in tasks:
            runs = [
                ReportRunResult(
                    profile=pname,
                    task=tname,
                    model=m,
                    scores=dict(score_dims),
                    token_count=1500,
                    success=True,
                )
                for m in models
            ]
            tasks_dict[tname] = TaskResult(
                task_id=tname,
                task_name=tname,
                runs=runs,
                mean_scores=dict(score_dims),
                std_scores={dim: 0.0 for dim in score_dims},
            )
        agg = dict(score_dims)
        total_tokens = len(tasks) * len(models) * 1500
        profile_dict[pname] = ProfileResult(
            profile_id=pname,
            profile_name=pname,
            tasks=tasks_dict,
            aggregate_scores=agg,
            total_tokens=total_tokens,
        )

    return BenchmarkResults(
        profiles=profile_dict,
        models=models,
        tasks=tasks,
        metadata=ReportMetadata(
            date="2026-02-26",
            models_tested=models,
            profile_count=len(profiles),
            total_runs=len(profiles) * len(tasks) * len(models),
        ),
    )


class TestFilterResults:
    """Tests for filter_results()."""

    def test_filter_by_profile(self) -> None:
        results = _make_benchmark_results()
        filtered = filter_results(results, profile_names=["empty"])
        assert list(filtered.profiles.keys()) == ["empty"]
        assert filtered.metadata.profile_count == 1

    def test_filter_by_task(self) -> None:
        results = _make_benchmark_results()
        filtered = filter_results(results, task_names=["code-gen-01"])
        for pr in filtered.profiles.values():
            assert list(pr.tasks.keys()) == ["code-gen-01"]
        assert filtered.tasks == ["code-gen-01"]

    def test_filter_by_model(self) -> None:
        results = _make_benchmark_results()
        filtered = filter_results(results, model_names=["sonnet"])
        for pr in filtered.profiles.values():
            for tr in pr.tasks.values():
                for run in tr.runs:
                    assert run.model == "sonnet"
        assert filtered.models == ["sonnet"]

    def test_filter_no_match(self) -> None:
        results = _make_benchmark_results()
        filtered = filter_results(
            results,
            profile_names=["nonexistent"],
        )
        assert filtered.profiles == {}
        assert filtered.models == []
        assert filtered.tasks == []

    def test_filter_none_passes_all(self) -> None:
        results = _make_benchmark_results()
        filtered = filter_results(results)
        assert len(filtered.profiles) == len(results.profiles)
        assert sorted(filtered.models) == sorted(results.models)
        assert sorted(filtered.tasks) == sorted(results.tasks)

    def test_filter_combined(self) -> None:
        """Filter by profile AND task simultaneously."""
        results = _make_benchmark_results()
        filtered = filter_results(
            results,
            profile_names=["empty", "full"],
            task_names=["bug-fix-01"],
        )
        assert sorted(filtered.profiles.keys()) == ["empty", "full"]
        for pr in filtered.profiles.values():
            assert list(pr.tasks.keys()) == ["bug-fix-01"]

    def test_filter_does_not_mutate_input(self) -> None:
        """Filtering returns a new object; input is unchanged."""
        results = _make_benchmark_results()
        original_profile_count = len(results.profiles)
        filter_results(results, profile_names=["empty"])
        assert len(results.profiles) == original_profile_count


# ---------------------------------------------------------------------------
# Tests: aggregate scores and token totals
# ---------------------------------------------------------------------------


class TestAggregation:
    """Tests for score aggregation and token totals."""

    def test_aggregate_scores_computed(self, parallel_results: Path) -> None:
        """ProfileResult.aggregate_scores is mean of task mean_scores."""
        result = load_results_dir(parallel_results)
        profile = result.profiles["test"]
        # All tasks have mean correctness=85, style=72 (uniform scores)
        assert profile.aggregate_scores["correctness"] == pytest.approx(85.0)
        assert profile.aggregate_scores["style"] == pytest.approx(72.0)

    def test_total_tokens_summed(self, parallel_results: Path) -> None:
        """ProfileResult.total_tokens equals sum of all run token_counts."""
        result = load_results_dir(parallel_results)
        profile = result.profiles["test"]
        expected_total = 2 * 2 * 3 * 1500  # models x tasks x runs x tokens
        assert profile.total_tokens == expected_total

    def test_std_scores_with_variance(self, tmp_path: Path) -> None:
        """Stdev computed correctly when scores differ across runs."""
        results_dir = tmp_path / "variance"
        _write_manifest(results_dir, models=["m"], tasks=["t"])
        _make_parallel_run(
            results_dir, "m", "test", "t", 1, scores={"x": 80.0}
        )
        _make_parallel_run(
            results_dir, "m", "test", "t", 2, scores={"x": 90.0}
        )
        _make_parallel_run(
            results_dir, "m", "test", "t", 3, scores={"x": 100.0}
        )
        result = load_results_dir(results_dir)
        task_result = result.profiles["test"].tasks["t"]
        assert task_result.mean_scores["x"] == pytest.approx(90.0)
        assert task_result.std_scores["x"] == pytest.approx(10.0)

    def test_std_scores_single_run(self, tmp_path: Path) -> None:
        """Stdev is 0.0 when only a single run exists."""
        results_dir = tmp_path / "single"
        _write_manifest(results_dir, models=["m"], tasks=["t"])
        _make_parallel_run(
            results_dir, "m", "test", "t", 1, scores={"x": 75.0}
        )
        result = load_results_dir(results_dir)
        task_result = result.profiles["test"].tasks["t"]
        assert task_result.std_scores["x"] == 0.0

    def test_filter_recomputes_tokens(self) -> None:
        """Filtering by task recomputes total_tokens for the subset."""
        results = _make_benchmark_results()
        original_tokens = results.profiles["empty"].total_tokens
        filtered = filter_results(results, task_names=["code-gen-01"])
        # 1 task out of 3 -> tokens should be 1/3
        assert filtered.profiles["empty"].total_tokens == original_tokens // 3
