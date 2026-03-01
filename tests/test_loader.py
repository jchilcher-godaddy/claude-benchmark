import tomllib
from pathlib import Path

import pytest
import tomli_w

from claude_benchmark.tasks import (
    Difficulty,
    TaskLoadError,
    TaskRegistry,
    TaskType,
    TaskValidationError,
    discover_tasks,
    load_task,
)


def create_valid_task(task_dir: Path, task_type: str = "code-gen", include_files: bool = True):
    task_data = {
        "name": "test-task",
        "task_type": task_type,
        "difficulty": "medium",
        "size": "function",
        "description": "Test task",
        "prompt": "Test prompt",
        "tags": [],
        "scoring": {"test_file": "test_solution.py"},
    }

    if task_type in ("bug-fix", "refactor"):
        task_data["starter_code"] = "starter.py"

    if task_type == "instruction":
        task_data["prompt_rules"] = ["rule1", "rule2"]

    task_dir.mkdir(parents=True, exist_ok=True)
    toml_path = task_dir / "task.toml"
    with open(toml_path, "wb") as f:
        tomli_w.dump(task_data, f)

    if include_files:
        (task_dir / "test_solution.py").write_text("def test_foo(): pass")
        if task_type in ("bug-fix", "refactor"):
            (task_dir / "starter.py").write_text("# starter code")

    return task_data


def test_load_task_valid_code_gen(tmp_path):
    task_dir = tmp_path / "task1"
    create_valid_task(task_dir, "code-gen")

    task = load_task(task_dir)

    assert task.name == "test-task"
    assert task.task_type == TaskType.CODE_GEN
    assert task.difficulty == Difficulty.MEDIUM


def test_load_task_valid_bug_fix(tmp_path):
    task_dir = tmp_path / "task2"
    create_valid_task(task_dir, "bug-fix")

    task = load_task(task_dir)

    assert task.name == "test-task"
    assert task.task_type == TaskType.BUG_FIX
    assert task.starter_code == "starter.py"


def test_load_task_missing_toml(tmp_path):
    task_dir = tmp_path / "task3"
    task_dir.mkdir()

    with pytest.raises(TaskLoadError, match="task.toml not found"):
        load_task(task_dir)


def test_load_task_invalid_toml_syntax(tmp_path):
    task_dir = tmp_path / "task4"
    task_dir.mkdir()
    toml_path = task_dir / "task.toml"
    toml_path.write_text("invalid toml [ syntax")

    with pytest.raises(TaskLoadError, match="Invalid TOML syntax"):
        load_task(task_dir)


def test_load_task_missing_starter_code(tmp_path):
    task_dir = tmp_path / "task5"
    create_valid_task(task_dir, "bug-fix", include_files=False)
    (task_dir / "test_solution.py").write_text("def test_foo(): pass")

    with pytest.raises(TaskLoadError, match="references missing files.*starter.py"):
        load_task(task_dir)


def test_load_task_missing_test_file(tmp_path):
    task_dir = tmp_path / "task6"
    create_valid_task(task_dir, "code-gen", include_files=False)

    with pytest.raises(TaskLoadError, match="references missing files.*test_solution.py"):
        load_task(task_dir)


def test_discover_tasks_finds_multiple(tmp_path):
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"

    create_valid_task(dir1 / "task1", "code-gen")
    create_valid_task(dir1 / "task2", "bug-fix")
    create_valid_task(dir2 / "task3", "code-gen")

    valid_tasks, errors = discover_tasks(dir1, dir2)

    assert len(valid_tasks) == 3
    assert len(errors) == 0


def test_discover_tasks_returns_errors_without_crashing(tmp_path):
    dir1 = tmp_path / "dir1"

    create_valid_task(dir1 / "task1", "code-gen")

    invalid_dir = dir1 / "task2"
    invalid_dir.mkdir()
    (invalid_dir / "task.toml").write_text("invalid toml [ syntax")

    valid_tasks, errors = discover_tasks(dir1)

    assert len(valid_tasks) == 1
    assert len(errors) == 1
    assert "task2" in errors[0]


def test_task_registry_by_type(tmp_path):
    registry = TaskRegistry()

    dir1 = tmp_path / "dir1"
    create_valid_task(dir1 / "task1", "code-gen")
    create_valid_task(dir1 / "task2", "bug-fix")

    task1 = load_task(dir1 / "task1")
    task2 = load_task(dir1 / "task2")

    registry.add(task1)
    registry.add(task2)

    code_gen_tasks = registry.by_type(TaskType.CODE_GEN)
    assert len(code_gen_tasks) == 1
    assert code_gen_tasks[0].task_type == TaskType.CODE_GEN


def test_task_registry_by_difficulty(tmp_path):
    registry = TaskRegistry()

    dir1 = tmp_path / "dir1"
    task_data = create_valid_task(dir1 / "task1", "code-gen")
    task1 = load_task(dir1 / "task1")

    registry.add(task1)

    medium_tasks = registry.by_difficulty(Difficulty.MEDIUM)
    assert len(medium_tasks) == 1
    assert medium_tasks[0].difficulty == Difficulty.MEDIUM


def test_task_registry_by_name_returns_none(tmp_path):
    registry = TaskRegistry()

    result = registry.by_name("nonexistent")
    assert result is None


def test_task_registry_from_directories(tmp_path):
    dir1 = tmp_path / "dir1"
    create_valid_task(dir1 / "task1", "code-gen")
    create_valid_task(dir1 / "task2", "bug-fix")

    registry = TaskRegistry.from_directories(dir1)

    assert len(registry.all) == 2
