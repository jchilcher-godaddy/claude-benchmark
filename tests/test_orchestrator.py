"""Tests for the benchmark orchestrator matrix execution."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from claude_benchmark.engine.orchestrator import run_benchmark_matrix
from claude_benchmark.results.schema import RunResult, TokenUsage
from claude_benchmark.tasks.schema import ScoringCriteria, TaskDefinition


def make_test_task(name: str = "test-task") -> TaskDefinition:
    return TaskDefinition(
        name=name,
        task_type="code-gen",
        difficulty="easy",
        description="Test task",
        prompt="Write hello world",
        scoring=ScoringCriteria(test_file="test.py"),
    )


def make_mock_result(run_number: int, success: bool = True) -> RunResult:
    return RunResult(
        run_number=run_number,
        success=success,
        wall_clock_seconds=10.0,
        error=None if success else "Test error",
        usage=TokenUsage(
            input_tokens=500,
            output_tokens=200,
        )
        if success
        else None,
    )


@pytest.fixture
def task_setup(tmp_path: Path):
    """Create a minimal task directory and profile for testing."""
    task_dir = tmp_path / "tasks" / "test-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text("[scoring]\ntest_file = 'test.py'\n")
    (task_dir / "test.py").write_text("# test")

    profile = tmp_path / "profile.md"
    profile.write_text("# Test Profile\n")

    return task_dir, profile


@pytest.fixture
def mock_execute_run():
    """Mock execute_run to return predefined results."""

    async def _mock_execute(
        workspace_dir, prompt, model, run_number, timeout_seconds=300
    ):
        return make_mock_result(run_number)

    with patch(
        "claude_benchmark.engine.orchestrator.execute_run",
        side_effect=_mock_execute,
    ) as mock:
        yield mock


@pytest.fixture
def mock_workspace(tmp_path: Path):
    """Mock workspace creation/cleanup to use tmp dirs."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with (
        patch(
            "claude_benchmark.engine.orchestrator.create_workspace",
            return_value=workspace,
        ),
        patch("claude_benchmark.engine.orchestrator.cleanup_workspace"),
    ):
        yield workspace


@pytest.fixture
def mock_results_dir(tmp_path: Path):
    """Mock results directory creation."""
    results = tmp_path / "results" / "20260226_120000_000"
    results.mkdir(parents=True)
    with patch(
        "claude_benchmark.engine.orchestrator.create_results_directory",
        return_value=results,
    ):
        yield results


def test_matrix_single_combination(
    task_setup, mock_execute_run, mock_workspace, mock_results_dir
):
    """1 task, 1 profile, 1 model, 3 runs creates correct directory structure."""
    task_dir, profile = task_setup
    task = make_test_task()

    result_path = asyncio.run(
        run_benchmark_matrix(
            tasks=[task],
            task_dirs={"test-task": task_dir},
            profiles=[profile],
            models=["sonnet"],
            runs_per=3,
            quiet=True,
        )
    )

    assert result_path == mock_results_dir
    assert mock_execute_run.call_count == 3

    # Check run results were saved
    runs_dir = mock_results_dir / "runs" / "sonnet" / "profile" / "test-task"
    assert runs_dir.exists()
    assert (runs_dir / "run_001.json").exists()
    assert (runs_dir / "run_002.json").exists()
    assert (runs_dir / "run_003.json").exists()


def test_matrix_creates_manifest(
    task_setup, mock_execute_run, mock_workspace, mock_results_dir
):
    """Manifest is saved with correct configuration."""
    task_dir, profile = task_setup
    task = make_test_task()

    asyncio.run(
        run_benchmark_matrix(
            tasks=[task],
            task_dirs={"test-task": task_dir},
            profiles=[profile],
            models=["sonnet"],
            runs_per=3,
            quiet=True,
        )
    )

    manifest_path = mock_results_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["models"] == ["sonnet"]
    assert manifest["profiles"] == ["profile"]
    assert manifest["tasks"] == ["test-task"]
    assert manifest["runs_per_combination"] == 3
    assert manifest["total_runs"] == 3
    assert manifest["total_combinations"] == 1


def test_matrix_creates_aggregates(
    task_setup, mock_execute_run, mock_workspace, mock_results_dir
):
    """Aggregate JSON is created for each task combination."""
    task_dir, profile = task_setup
    task = make_test_task()

    asyncio.run(
        run_benchmark_matrix(
            tasks=[task],
            task_dirs={"test-task": task_dir},
            profiles=[profile],
            models=["sonnet"],
            runs_per=3,
            quiet=True,
        )
    )

    agg_path = (
        mock_results_dir / "aggregates" / "sonnet" / "profile" / "test-task.json"
    )
    assert agg_path.exists()
    agg = json.loads(agg_path.read_text())
    assert agg["total_runs"] == 3
    assert agg["successful_runs"] == 3
    assert agg["success_rate"] == 1.0


def test_matrix_handles_failed_runs(
    task_setup, mock_workspace, mock_results_dir
):
    """Failed runs are logged but don't abort the benchmark."""
    call_count = 0

    async def _mock_execute(
        workspace_dir, prompt, model, run_number, timeout_seconds=300
    ):
        nonlocal call_count
        call_count += 1
        # Fail on run 2
        success = run_number != 2
        return make_mock_result(run_number, success=success)

    with patch(
        "claude_benchmark.engine.orchestrator.execute_run",
        side_effect=_mock_execute,
    ):
        task_dir, profile = task_setup
        task = make_test_task()

        result_path = asyncio.run(
            run_benchmark_matrix(
                tasks=[task],
                task_dirs={"test-task": task_dir},
                profiles=[profile],
                models=["sonnet"],
                runs_per=3,
                quiet=True,
            )
        )

    # All 3 runs executed despite the failure
    assert call_count == 3
    assert result_path == mock_results_dir

    agg_path = (
        mock_results_dir / "aggregates" / "sonnet" / "profile" / "test-task.json"
    )
    agg = json.loads(agg_path.read_text())
    assert agg["total_runs"] == 3
    assert agg["successful_runs"] == 2
    assert agg["failed_runs"] == 1


def test_matrix_quiet_mode(
    task_setup, mock_execute_run, mock_workspace, mock_results_dir
):
    """quiet=True does not crash."""
    task_dir, profile = task_setup
    task = make_test_task()

    result_path = asyncio.run(
        run_benchmark_matrix(
            tasks=[task],
            task_dirs={"test-task": task_dir},
            profiles=[profile],
            models=["sonnet"],
            runs_per=3,
            quiet=True,
        )
    )
    assert result_path == mock_results_dir


def test_matrix_keep_workspaces(task_setup, mock_execute_run, mock_results_dir):
    """keep_workspaces=True preserves temp dirs (cleanup not called)."""
    task_dir, profile = task_setup
    task = make_test_task()

    with (
        patch(
            "claude_benchmark.engine.orchestrator.create_workspace",
            return_value=task_dir,
        ),
        patch(
            "claude_benchmark.engine.orchestrator.cleanup_workspace"
        ) as mock_cleanup,
    ):
        asyncio.run(
            run_benchmark_matrix(
                tasks=[task],
                task_dirs={"test-task": task_dir},
                profiles=[profile],
                models=["sonnet"],
                runs_per=3,
                quiet=True,
                keep_workspaces=True,
            )
        )

    mock_cleanup.assert_not_called()


def test_matrix_multi_model_profile(
    task_setup, mock_execute_run, mock_results_dir
):
    """Multiple models and profiles create correct matrix."""
    task_dir, profile1 = task_setup
    profile2 = profile1.parent / "profile2.md"
    profile2.write_text("# Profile 2\n")

    task = make_test_task()

    with patch(
        "claude_benchmark.engine.orchestrator.create_workspace",
        return_value=task_dir,
    ), patch("claude_benchmark.engine.orchestrator.cleanup_workspace"):
        asyncio.run(
            run_benchmark_matrix(
                tasks=[task],
                task_dirs={"test-task": task_dir},
                profiles=[profile1, profile2],
                models=["sonnet", "haiku"],
                runs_per=3,
                quiet=True,
            )
        )

    # 2 models x 2 profiles x 1 task x 3 runs = 12 calls
    assert mock_execute_run.call_count == 12

    # Check aggregates exist for each combination
    for model in ["sonnet", "haiku"]:
        for profile_name in ["profile", "profile2"]:
            agg_path = (
                mock_results_dir
                / "aggregates"
                / model
                / profile_name
                / "test-task.json"
            )
            assert agg_path.exists(), f"Missing aggregate: {agg_path}"


def test_matrix_run_results_saved_per_run(
    task_setup, mock_execute_run, mock_workspace, mock_results_dir
):
    """Individual run-N.json files are created for each run."""
    task_dir, profile = task_setup
    task = make_test_task()

    asyncio.run(
        run_benchmark_matrix(
            tasks=[task],
            task_dirs={"test-task": task_dir},
            profiles=[profile],
            models=["sonnet"],
            runs_per=3,
            quiet=True,
        )
    )

    runs_dir = mock_results_dir / "runs" / "sonnet" / "profile" / "test-task"
    for i in range(1, 4):
        run_file = runs_dir / f"run_{i:03d}.json"
        assert run_file.exists(), f"Missing {run_file}"
        data = json.loads(run_file.read_text())
        assert data["run_number"] == i
        assert data["success"] is True
