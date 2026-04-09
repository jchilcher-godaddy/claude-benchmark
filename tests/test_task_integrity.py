"""Meta-validation tests for task integrity.

This module validates the internal consistency of benchmark tasks:

1. Reference solutions pass their own tests (correctness guarantee)
2. Bug-fix starter code has actual bugs (starter code fails tests)
3. Refactor starter code is functionally correct (passes functional tests)

These tests catch authoring errors that would corrupt benchmark results:
- A reference solution that doesn't work invalidates all scoring
- A bug-fix task with no bugs is unsolvable
- A refactor task with broken starter code conflates fixing with refactoring

Run with: pytest tests/test_task_integrity.py -v
"""

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest


def discover_tasks() -> list[tuple[str, Path, dict]]:
    """Discover all tasks from builtin directory.

    Returns:
        List of (task_name, task_dir, task_config) tuples.
    """
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    task_dirs = sorted([d for d in tasks_dir.iterdir() if d.is_dir() and (d / "task.toml").exists()])

    tasks = []
    for task_dir in task_dirs:
        toml_path = task_dir / "task.toml"
        with open(toml_path, "rb") as f:
            config = tomllib.load(f)
        tasks.append((task_dir.name, task_dir, config))

    return tasks


def copy_task_files(task_dir: Path, tmp_dir: Path, solution_file: str, task_config: dict) -> None:
    """Copy all task files needed to run tests.

    Args:
        task_dir: Source task directory.
        tmp_dir: Destination temporary directory.
        solution_file: Name of the solution file to copy (starter.py or reference.py).
        task_config: Parsed task.toml configuration.
    """
    src_solution = task_dir / solution_file
    if src_solution.exists():
        expected_files = task_config.get("expected_files", ["solution.py"])
        if expected_files:
            target_name = expected_files[0]
        else:
            target_name = "solution.py"
        shutil.copy(src_solution, tmp_dir / target_name)

    test_file = task_dir / "test_solution.py"
    if test_file.exists():
        shutil.copy(test_file, tmp_dir / "test_solution.py")

    for item in task_dir.iterdir():
        if item.is_file() and item.name not in ["task.toml", "starter.py", "reference.py", "solution.py", "test_solution.py"]:
            if not item.name.endswith(".pyc"):
                shutil.copy(item, tmp_dir / item.name)


def get_tasks_with_reference() -> list[tuple[str, Path, dict]]:
    """Get all tasks that have a reference_solution defined."""
    all_tasks = discover_tasks()
    return [
        (name, path, config)
        for name, path, config in all_tasks
        if config.get("scoring", {}).get("reference_solution")
    ]


def get_bugfix_tasks() -> list[tuple[str, Path, dict]]:
    """Get all bug-fix tasks."""
    all_tasks = discover_tasks()
    return [
        (name, path, config)
        for name, path, config in all_tasks
        if config.get("task_type") == "bug-fix"
    ]


def get_refactor_tasks() -> list[tuple[str, Path, dict]]:
    """Get all refactor tasks."""
    all_tasks = discover_tasks()
    return [
        (name, path, config)
        for name, path, config in all_tasks
        if config.get("task_type") == "refactor"
    ]


@pytest.mark.slow
@pytest.mark.parametrize("task_name,task_dir,task_config", get_tasks_with_reference())
def test_reference_solutions_pass_tests(task_name: str, task_dir: Path, task_config: dict, tmp_path: Path) -> None:
    """Verify that reference solutions pass their own tests.

    This validates that the reference solution is correct and the tests
    are properly calibrated. If this fails, the task cannot be used for
    benchmarking because the scoring baseline is invalid.

    Args:
        task_name: Name of the task.
        task_dir: Path to the task directory.
        task_config: Parsed task.toml configuration.
        tmp_path: Pytest temporary directory fixture.
    """
    reference_file = task_config["scoring"]["reference_solution"]
    copy_task_files(task_dir, tmp_path, reference_file, task_config)

    result = subprocess.run(
        ["python", "-m", "pytest", "test_solution.py", "-v"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Reference solution for {task_name} failed tests:\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


@pytest.mark.slow
@pytest.mark.parametrize("task_name,task_dir,task_config", get_bugfix_tasks())
def test_bugfix_starters_have_bugs(task_name: str, task_dir: Path, task_config: dict, tmp_path: Path) -> None:
    """Verify that bug-fix starter code fails tests.

    This validates that the starter code actually contains bugs to fix.
    If the starter code passes tests, the task is unsolvable and results
    will be invalid.

    Args:
        task_name: Name of the task.
        task_dir: Path to the task directory.
        task_config: Parsed task.toml configuration.
        tmp_path: Pytest temporary directory fixture.
    """
    starter_file = task_config.get("starter_code")
    if not starter_file:
        pytest.skip(f"{task_name} has no starter_code field")

    copy_task_files(task_dir, tmp_path, starter_file, task_config)

    result = subprocess.run(
        ["python", "-m", "pytest", "test_solution.py", "-v"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0, (
        f"Bug-fix starter for {task_name} passed all tests (no bugs found!).\n"
        f"Bug-fix tasks must have failing tests to demonstrate the presence of bugs.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


@pytest.mark.slow
@pytest.mark.parametrize("task_name,task_dir,task_config", get_refactor_tasks())
def test_refactor_starters_are_functional(task_name: str, task_dir: Path, task_config: dict, tmp_path: Path) -> None:
    """Verify that refactor starter code is functionally correct.

    This validates that the starter code works correctly but needs refactoring.
    We skip structural validation tests (those checking for helper functions,
    nesting depth, duplication, etc.) and only run functional correctness tests.

    If functional tests fail, the task conflates bug-fixing with refactoring,
    which invalidates the benchmark.

    Args:
        task_name: Name of the task.
        task_dir: Path to the task directory.
        task_config: Parsed task.toml configuration.
        tmp_path: Pytest temporary directory fixture.
    """
    starter_file = task_config.get("starter_code")
    if not starter_file:
        pytest.skip(f"{task_name} has no starter_code field")

    copy_task_files(task_dir, tmp_path, starter_file, task_config)

    skip_patterns = [
        "test_no_duplicated",
        "test_has_helper",
        "test_max_nesting",
        "test_uses_early",
        "test_has_classes",
        "test_no_procedural",
        "test_no_duplicated_loops",
        "test_has_helper_functions",
    ]
    deselect_args = [f"--deselect=test_solution.py::{pattern}" for pattern in skip_patterns]

    result = subprocess.run(
        ["python", "-m", "pytest", "test_solution.py", "-v"] + deselect_args,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Refactor starter for {task_name} failed functional tests.\n"
        f"Refactor tasks must have working starter code that only needs structural improvements.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
