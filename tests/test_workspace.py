import tempfile
from pathlib import Path

from claude_benchmark.engine.workspace import (
    capture_workspace_files,
    cleanup_workspace,
    create_workspace,
)
from claude_benchmark.results.schema import (
    AggregateResult,
    BenchmarkManifest,
    RunResult,
    StatsSummary,
)
from claude_benchmark.results.storage import (
    create_results_directory,
    save_aggregate,
    save_manifest,
    save_run_result,
)
from claude_benchmark.tasks.schema import ScoringCriteria, TaskDefinition, TaskType, Difficulty


def test_create_workspace_copies_claude_md(tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    profile_path = tmp_path / "profile.md"
    profile_path.write_text("# Profile Rules")

    test_file = task_dir / "test.py"
    test_file.write_text("def test(): pass")

    task = TaskDefinition(
        name="test-task",
        task_type=TaskType.CODE_GEN,
        difficulty=Difficulty.EASY,
        description="Test",
        prompt="Test prompt",
        scoring=ScoringCriteria(test_file="test.py"),
    )

    workspace = create_workspace(task_dir, profile_path, task)

    assert workspace.exists()
    assert (workspace / "CLAUDE.md").exists()
    assert (workspace / "CLAUDE.md").read_text() == "# Profile Rules"

    cleanup_workspace(workspace)


def test_create_workspace_copies_starter_code_for_bug_fix(tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    profile_path = tmp_path / "profile.md"
    profile_path.write_text("# Profile")

    starter = task_dir / "buggy.py"
    starter.write_text("def broken(): return 1/0")

    test_file = task_dir / "test.py"
    test_file.write_text("def test(): pass")

    task = TaskDefinition(
        name="bug-fix-task",
        task_type=TaskType.BUG_FIX,
        difficulty=Difficulty.MEDIUM,
        description="Fix bug",
        prompt="Fix the bug",
        starter_code="buggy.py",
        scoring=ScoringCriteria(test_file="test.py"),
    )

    workspace = create_workspace(task_dir, profile_path, task)

    assert (workspace / "buggy.py").exists()
    assert (workspace / "buggy.py").read_text() == "def broken(): return 1/0"

    cleanup_workspace(workspace)


def test_create_workspace_copies_test_file(tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    profile_path = tmp_path / "profile.md"
    profile_path.write_text("# Profile")

    test_file = task_dir / "test_main.py"
    test_file.write_text("def test_main(): assert True")

    task = TaskDefinition(
        name="test-task",
        task_type=TaskType.CODE_GEN,
        difficulty=Difficulty.EASY,
        description="Test",
        prompt="Test prompt",
        scoring=ScoringCriteria(test_file="test_main.py"),
    )

    workspace = create_workspace(task_dir, profile_path, task)

    assert (workspace / "test_main.py").exists()
    assert (workspace / "test_main.py").read_text() == "def test_main(): assert True"

    cleanup_workspace(workspace)


def test_capture_workspace_files_returns_relative_paths(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "main.py").write_text("print('hello')")
    subdir = workspace / "subdir"
    subdir.mkdir()
    (subdir / "util.py").write_text("def util(): pass")

    files = capture_workspace_files(workspace)

    assert "main.py" in files
    assert files["main.py"] == "print('hello')"
    assert "subdir/util.py" in files
    assert files["subdir/util.py"] == "def util(): pass"


def test_capture_workspace_files_excludes_claude_md(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "CLAUDE.md").write_text("# Rules")
    (workspace / "main.py").write_text("code")

    files = capture_workspace_files(workspace)

    assert "CLAUDE.md" not in files
    assert "main.py" in files


def test_capture_workspace_files_excludes_claude_dir(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    claude_dir = workspace / ".claude"
    claude_dir.mkdir()
    (claude_dir / "session.json").write_text("{}")
    (workspace / "main.py").write_text("code")

    files = capture_workspace_files(workspace)

    assert ".claude/session.json" not in files
    assert "main.py" in files


def test_cleanup_workspace_removes_directory(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file.py").write_text("test")

    cleanup_workspace(workspace)

    assert not workspace.exists()


def test_cleanup_workspace_handles_already_gone_directory(tmp_path):
    workspace = tmp_path / "nonexistent"

    cleanup_workspace(workspace)

    assert not workspace.exists()


def test_create_results_directory(tmp_path):
    results_dir = create_results_directory(tmp_path)

    assert results_dir.exists()
    assert results_dir.parent == tmp_path
    assert len(results_dir.name) > 0


def test_save_run_result(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    result = RunResult(
        run_number=1,
        success=True,
        wall_clock_seconds=2.5,
    )

    file_path = save_run_result(
        results_dir, "claude-opus-4", "default", "test-task", 1, result
    )

    assert file_path.exists()
    assert file_path.name == "run_001.json"
    assert "claude-opus-4" in str(file_path)
    assert "default" in str(file_path)
    assert "test-task" in str(file_path)


def test_save_aggregate(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    aggregate = AggregateResult(
        task_name="test-task",
        profile_name="default",
        model="claude-opus-4",
        total_runs=5,
        successful_runs=5,
        failed_runs=0,
        success_rate=1.0,
    )

    file_path = save_aggregate(
        results_dir, "claude-opus-4", "default", "test-task", aggregate
    )

    assert file_path.exists()
    assert file_path.name == "test-task.json"


def test_save_manifest(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    from datetime import datetime

    manifest = BenchmarkManifest(
        timestamp=datetime.now(),
        models=["claude-opus-4"],
        profiles=["default"],
        tasks=["task1"],
        runs_per_combination=5,
        total_combinations=1,
        total_runs=5,
    )

    file_path = save_manifest(results_dir, manifest)

    assert file_path.exists()
    assert file_path.name == "manifest.json"
    assert file_path.parent == results_dir
