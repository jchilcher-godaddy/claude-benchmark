"""Tests for orchestrator, worker, BenchmarkRun, RunResult, and parallel execution."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest

from claude_benchmark.execution.cost import CostTracker
from claude_benchmark.execution.parallel import (
    BenchmarkRun,
    ProgressCallback,
    RunResult,
    build_run_matrix,
    run_benchmark_parallel,
)
from claude_benchmark.execution.worker import write_result_atomic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    task_name: str = "task-1",
    profile_name: str = "empty",
    model: str = "sonnet",
    run_number: int = 1,
    results_dir: Path | None = None,
) -> BenchmarkRun:
    """Create a BenchmarkRun with sensible defaults for testing."""
    return BenchmarkRun(
        task_name=task_name,
        profile_name=profile_name,
        model=model,
        run_number=run_number,
        task_dir=Path("/tmp/tasks") / task_name,
        profile_path=Path("/tmp/profiles") / profile_name / "CLAUDE.md",
        results_dir=results_dir or Path("/tmp/results"),
    )


@dataclass
class FakeTask:
    """Minimal task-like object for build_run_matrix."""

    name: str
    path: Path


@dataclass
class FakeProfile:
    """Minimal profile-like object for build_run_matrix."""

    name: str
    path: Path


# ---------------------------------------------------------------------------
# BenchmarkRun tests
# ---------------------------------------------------------------------------


class TestBenchmarkRunResultKey:
    """BenchmarkRun.result_key matches expected format."""

    def test_result_key_format(self) -> None:
        run = _make_run(model="sonnet", profile_name="empty", task_name="code-gen", run_number=3)
        assert run.result_key == "sonnet/empty/code-gen/run-3"

    def test_result_key_different_values(self) -> None:
        run = _make_run(model="haiku", profile_name="large", task_name="refactor-01", run_number=1)
        assert run.result_key == "haiku/large/refactor-01/run-1"


class TestBenchmarkRunResultPath:
    """BenchmarkRun.result_path constructs correct path under results_dir."""

    def test_result_path(self, tmp_path: Path) -> None:
        run = _make_run(
            model="opus",
            profile_name="compressed",
            task_name="debug-fix",
            run_number=2,
            results_dir=tmp_path,
        )
        expected = tmp_path / "opus" / "compressed" / "debug-fix" / "run-2.json"
        assert run.result_path == expected

    def test_result_path_is_absolute(self, tmp_path: Path) -> None:
        run = _make_run(results_dir=tmp_path)
        assert run.result_path.is_absolute()


# ---------------------------------------------------------------------------
# RunResult tests
# ---------------------------------------------------------------------------


class TestRunResultToDict:
    """RunResult.to_dict() serializes all fields including Path conversion."""

    def test_to_dict_success(self, tmp_path: Path) -> None:
        run = _make_run(results_dir=tmp_path)
        result = RunResult(
            run=run,
            status="success",
            output_dir=tmp_path / "output",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost=0.042,
            duration_seconds=12.5,
            scores={"quality": 85},
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["task_name"] == "task-1"
        assert d["profile_name"] == "empty"
        assert d["model"] == "sonnet"
        assert d["run_number"] == 1
        assert d["result_key"] == "sonnet/empty/task-1/run-1"
        assert d["input_tokens"] == 1000
        assert d["output_tokens"] == 500
        assert d["total_tokens"] == 1500
        assert d["cost"] == 0.042
        assert d["duration_seconds"] == 12.5
        assert d["scores"] == {"quality": 85}
        assert d["error"] is None
        # Path should be converted to str
        assert isinstance(d["output_dir"], str)

    def test_to_dict_failure_with_error(self) -> None:
        run = _make_run()
        result = RunResult(run=run, status="failure", error="Command not found")
        d = result.to_dict()
        assert d["status"] == "failure"
        assert d["error"] == "Command not found"
        assert d["output_dir"] is None

    def test_to_dict_no_scores(self) -> None:
        run = _make_run()
        result = RunResult(run=run, status="success")
        d = result.to_dict()
        assert d["scores"] is None


class TestRunResultFailure:
    """RunResult.failure() creates a failure result with correct status and error."""

    def test_failure_factory(self) -> None:
        run = _make_run()
        result = RunResult.failure(run, "Connection timeout")
        assert result.status == "failure"
        assert result.error == "Connection timeout"
        assert result.run is run
        assert result.cost == 0.0
        assert result.duration_seconds == 0.0

    def test_failure_is_serializable(self) -> None:
        run = _make_run()
        result = RunResult.failure(run, "Boom")
        d = result.to_dict()
        assert d["status"] == "failure"
        assert d["error"] == "Boom"


# ---------------------------------------------------------------------------
# build_run_matrix tests
# ---------------------------------------------------------------------------


class TestBuildRunMatrix:
    """build_run_matrix produces correct cartesian product."""

    def test_cartesian_product_size(self, tmp_path: Path) -> None:
        tasks = [
            FakeTask(name="task-a", path=tmp_path / "task-a"),
            FakeTask(name="task-b", path=tmp_path / "task-b"),
        ]
        profiles = [
            FakeProfile(name="empty", path=tmp_path / "empty" / "CLAUDE.md"),
            FakeProfile(name="large", path=tmp_path / "large" / "CLAUDE.md"),
        ]
        models = ["haiku", "sonnet"]
        reps = 3
        runs = build_run_matrix(tasks, profiles, models, reps, tmp_path)
        # 2 tasks x 2 profiles x 2 models x 3 reps = 24
        assert len(runs) == 24

    def test_all_runs_are_benchmark_run(self, tmp_path: Path) -> None:
        tasks = [FakeTask(name="t", path=tmp_path)]
        profiles = [FakeProfile(name="p", path=tmp_path / "CLAUDE.md")]
        runs = build_run_matrix(tasks, profiles, ["sonnet"], 1, tmp_path)
        assert all(isinstance(r, BenchmarkRun) for r in runs)

    def test_result_keys_unique(self, tmp_path: Path) -> None:
        tasks = [
            FakeTask(name="task-a", path=tmp_path / "task-a"),
            FakeTask(name="task-b", path=tmp_path / "task-b"),
        ]
        profiles = [
            FakeProfile(name="empty", path=tmp_path / "empty" / "CLAUDE.md"),
            FakeProfile(name="large", path=tmp_path / "large" / "CLAUDE.md"),
        ]
        models = ["haiku", "sonnet"]
        reps = 3
        runs = build_run_matrix(tasks, profiles, models, reps, tmp_path)
        keys = [r.result_key for r in runs]
        assert len(keys) == len(set(keys)), "All result_keys must be unique"

    def test_correct_result_key_values(self, tmp_path: Path) -> None:
        tasks = [FakeTask(name="code-gen", path=tmp_path / "code-gen")]
        profiles = [FakeProfile(name="empty", path=tmp_path / "empty" / "CLAUDE.md")]
        runs = build_run_matrix(tasks, profiles, ["haiku"], 2, tmp_path)
        keys = {r.result_key for r in runs}
        assert "haiku/empty/code-gen/run-1" in keys
        assert "haiku/empty/code-gen/run-2" in keys

    def test_single_combination(self, tmp_path: Path) -> None:
        tasks = [FakeTask(name="t1", path=tmp_path)]
        profiles = [FakeProfile(name="p1", path=tmp_path / "CLAUDE.md")]
        runs = build_run_matrix(tasks, profiles, ["sonnet"], 1, tmp_path)
        assert len(runs) == 1
        assert runs[0].task_name == "t1"
        assert runs[0].profile_name == "p1"
        assert runs[0].model == "sonnet"
        assert runs[0].run_number == 1

    def test_results_dir_propagated(self, tmp_path: Path) -> None:
        tasks = [FakeTask(name="t", path=tmp_path)]
        profiles = [FakeProfile(name="p", path=tmp_path / "CLAUDE.md")]
        runs = build_run_matrix(tasks, profiles, ["sonnet"], 1, tmp_path)
        assert runs[0].results_dir == tmp_path


# ---------------------------------------------------------------------------
# write_result_atomic tests
# ---------------------------------------------------------------------------


class TestWriteResultAtomic:
    """write_result_atomic creates valid JSON file at expected path."""

    def test_creates_valid_json(self, tmp_path: Path) -> None:
        run = _make_run(results_dir=tmp_path)
        result = RunResult(
            run=run,
            status="success",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost=0.01,
            duration_seconds=5.0,
        )
        write_result_atomic(result)

        assert run.result_path.exists()
        data = json.loads(run.result_path.read_text())
        assert data["status"] == "success"
        assert data["input_tokens"] == 100
        assert data["cost"] == 0.01

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        run = _make_run(
            model="opus",
            profile_name="deep",
            task_name="complex-task",
            run_number=5,
            results_dir=tmp_path,
        )
        result = RunResult(run=run, status="failure", error="timeout")
        write_result_atomic(result)

        expected_path = tmp_path / "opus" / "deep" / "complex-task" / "run-5.json"
        assert expected_path.exists()

    def test_cleans_up_temp_on_failure(self, tmp_path: Path) -> None:
        run = _make_run(results_dir=tmp_path)
        result = RunResult(run=run, status="success")

        # Make to_dict return something that causes json.dump to fail
        with patch.object(RunResult, "to_dict", side_effect=RuntimeError("serialize error")):
            with pytest.raises(RuntimeError, match="serialize error"):
                write_result_atomic(result)

        # Verify no .tmp files remain
        parent = run.result_path.parent
        if parent.exists():
            tmp_files = list(parent.glob("*.tmp"))
            assert len(tmp_files) == 0, f"Temp files not cleaned up: {tmp_files}"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        run = _make_run(results_dir=tmp_path)
        result1 = RunResult(run=run, status="failure", error="first attempt")
        write_result_atomic(result1)

        result2 = RunResult(run=run, status="success", cost=0.05)
        write_result_atomic(result2)

        data = json.loads(run.result_path.read_text())
        assert data["status"] == "success"


# ---------------------------------------------------------------------------
# run_benchmark_parallel tests
# ---------------------------------------------------------------------------


class TestRunBenchmarkParallel:
    """run_benchmark_parallel with mocked execute_single_run."""

    @pytest.mark.asyncio
    async def test_runs_all_and_collects_results(self, tmp_path: Path) -> None:
        """All runs are executed and results collected."""
        runs = [_make_run(run_number=i, results_dir=tmp_path) for i in range(1, 4)]

        async def mock_execute(run: BenchmarkRun) -> RunResult:
            await anyio.sleep(0.01)
            return RunResult(run=run, status="success", cost=0.01)

        with (
            patch(
                "claude_benchmark.execution.worker.execute_single_run",
                side_effect=mock_execute,
            ),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            results = await run_benchmark_parallel(runs, concurrency=2)

        assert len(results) == 3
        assert all(r.status == "success" for r in results)

    @pytest.mark.asyncio
    async def test_stops_queueing_when_cost_cap_reached(self, tmp_path: Path) -> None:
        """Cost cap triggers graceful wind-down: no new runs queued."""
        runs = [_make_run(run_number=i, results_dir=tmp_path) for i in range(1, 6)]
        tracker = CostTracker(max_cost=0.025)

        call_count = 0

        async def mock_execute(run: BenchmarkRun) -> RunResult:
            nonlocal call_count
            call_count += 1
            await anyio.sleep(0.01)
            return RunResult(run=run, status="success", cost=0.015)

        with (
            patch(
                "claude_benchmark.execution.worker.execute_single_run",
                side_effect=mock_execute,
            ),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            results = await run_benchmark_parallel(
                runs, concurrency=1, cost_tracker=tracker
            )

        # After 2 runs at $0.015 each = $0.03 >= $0.025 cap
        # Worker checks cap_reached before taking third run, stops
        assert len(results) == 2
        assert tracker.cap_reached is True

    @pytest.mark.asyncio
    async def test_continues_after_individual_failure(self, tmp_path: Path) -> None:
        """One run failing does not prevent other runs from executing."""
        runs = [_make_run(run_number=i, results_dir=tmp_path) for i in range(1, 4)]

        async def mock_execute(run: BenchmarkRun) -> RunResult:
            await anyio.sleep(0.01)
            if run.run_number == 2:
                raise RuntimeError("Simulated failure")
            return RunResult(run=run, status="success", cost=0.01)

        with (
            patch(
                "claude_benchmark.execution.worker.execute_single_run",
                side_effect=mock_execute,
            ),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            results = await run_benchmark_parallel(runs, concurrency=2)

        assert len(results) == 3
        successes = [r for r in results if r.status == "success"]
        failures = [r for r in results if r.status == "failure"]
        assert len(successes) == 2
        assert len(failures) == 1
        assert "Simulated failure" in failures[0].error

    @pytest.mark.asyncio
    async def test_concurrency_bounded(self, tmp_path: Path) -> None:
        """At most concurrency workers run simultaneously."""
        runs = [_make_run(run_number=i, results_dir=tmp_path) for i in range(1, 7)]
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_execute(run: BenchmarkRun) -> RunResult:
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await anyio.sleep(0.02)
            async with lock:
                current_concurrent -= 1
            return RunResult(run=run, status="success", cost=0.01)

        with (
            patch(
                "claude_benchmark.execution.worker.execute_single_run",
                side_effect=mock_execute,
            ),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            results = await run_benchmark_parallel(runs, concurrency=2)

        assert len(results) == 6
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_progress_callbacks_called(self, tmp_path: Path) -> None:
        """Progress callback receives worker_started and run_completed calls."""
        runs = [_make_run(run_number=1, results_dir=tmp_path)]
        progress = MagicMock(spec=["worker_started", "run_completed", "run_failed"])

        async def mock_execute(run: BenchmarkRun) -> RunResult:
            return RunResult(run=run, status="success")

        with (
            patch(
                "claude_benchmark.execution.worker.execute_single_run",
                side_effect=mock_execute,
            ),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            await run_benchmark_parallel(runs, concurrency=1, progress=progress)

        progress.worker_started.assert_called_once()
        progress.run_completed.assert_called_once()
        progress.run_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_progress_run_failed_on_exception(self, tmp_path: Path) -> None:
        """Progress callback receives run_failed on exception."""
        runs = [_make_run(run_number=1, results_dir=tmp_path)]
        progress = MagicMock(spec=["worker_started", "run_completed", "run_failed"])

        async def mock_execute(run: BenchmarkRun) -> RunResult:
            raise RuntimeError("Kaboom")

        with (
            patch(
                "claude_benchmark.execution.worker.execute_single_run",
                side_effect=mock_execute,
            ),
            patch("claude_benchmark.execution.worker.write_result_atomic"),
        ):
            await run_benchmark_parallel(runs, concurrency=1, progress=progress)

        progress.worker_started.assert_called_once()
        progress.run_failed.assert_called_once()
        progress.run_completed.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_runs_list(self) -> None:
        """Empty runs list returns empty results."""
        results = await run_benchmark_parallel([], concurrency=3)
        assert results == []
