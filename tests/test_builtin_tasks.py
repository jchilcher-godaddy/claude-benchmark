from pathlib import Path

import pytest

from claude_benchmark.tasks.loader import discover_tasks
from claude_benchmark.tasks.schema import Difficulty, TaskType


@pytest.fixture
def builtin_tasks():
    builtin_path = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, errors = discover_tasks(builtin_path)
    assert not errors, f"Task discovery errors: {errors}"
    return tasks


def test_minimum_task_count(builtin_tasks):
    assert len(builtin_tasks) >= 6, f"Expected at least 6 tasks, got {len(builtin_tasks)}"


def test_expected_task_names(builtin_tasks):
    task_names = {task.name for task in builtin_tasks}
    expected_names = {
        "code-gen-01",
        "code-gen-02",
        "code-gen-03",
        "bug-fix-01",
        "bug-fix-02",
        "bug-fix-03",
    }
    assert expected_names.issubset(task_names), f"Missing tasks: {expected_names - task_names}"


def test_task_type_distribution(builtin_tasks):
    type_counts = {}
    for task in builtin_tasks:
        type_counts[task.task_type] = type_counts.get(task.task_type, 0) + 1

    assert type_counts.get(TaskType.CODE_GEN, 0) >= 3, "Expected at least 3 code-gen tasks"
    assert type_counts.get(TaskType.BUG_FIX, 0) >= 3, "Expected at least 3 bug-fix tasks"


def test_difficulty_distribution(builtin_tasks):
    difficulty_counts = {}
    for task in builtin_tasks:
        difficulty_counts[task.difficulty] = difficulty_counts.get(task.difficulty, 0) + 1

    assert difficulty_counts.get(Difficulty.EASY, 0) >= 2, "Expected at least 2 easy tasks"
    assert difficulty_counts.get(Difficulty.MEDIUM, 0) >= 2, "Expected at least 2 medium tasks"
    assert difficulty_counts.get(Difficulty.HARD, 0) >= 2, "Expected at least 2 hard tasks"


def test_bug_fix_tasks_have_starter_code(builtin_tasks):
    builtin_path = Path(__file__).parent.parent / "tasks" / "builtin"
    bug_fix_tasks = [task for task in builtin_tasks if task.task_type == TaskType.BUG_FIX]
    for task in bug_fix_tasks:
        assert task.starter_code or task.starter_files, f"Bug-fix task {task.name} missing starter_code"
        # Verify the starter_code file actually exists on disk
        if task.starter_code:
            starter_path = builtin_path / task.name / task.starter_code
            assert starter_path.exists(), f"Starter file not found for {task.name}: {starter_path}"


def test_scoring_test_files_exist(builtin_tasks):
    builtin_path = Path(__file__).parent.parent / "tasks" / "builtin"
    for task in builtin_tasks:
        if task.scoring.test_file:
            task_dir = builtin_path / task.name
            test_path = task_dir / task.scoring.test_file
            assert test_path.exists(), f"Test file not found for {task.name}: {test_path}"
