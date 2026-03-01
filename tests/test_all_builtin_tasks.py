"""Integration tests for all builtin tasks."""

from pathlib import Path

from claude_benchmark.tasks.loader import discover_tasks
from claude_benchmark.tasks.schema import Difficulty, TaskType


def test_discover_all_builtin_tasks():
    """Test that all builtin tasks can be discovered and loaded."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, errors = discover_tasks(tasks_dir)

    assert len(errors) == 0, f"Task loading errors: {errors}"
    assert len(tasks) == 12, f"Expected 12 tasks, got {len(tasks)}"


def test_task_type_distribution():
    """Test that we have correct distribution of task types."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    type_counts = {task_type: 0 for task_type in TaskType}
    for task in tasks:
        type_counts[task.task_type] += 1

    assert type_counts[TaskType.CODE_GEN] == 3, "Expected 3 code-gen tasks"
    assert type_counts[TaskType.BUG_FIX] == 3, "Expected 3 bug-fix tasks"
    assert type_counts[TaskType.REFACTOR] == 3, "Expected 3 refactor tasks"
    assert type_counts[TaskType.INSTRUCTION] == 3, "Expected 3 instruction tasks"


def test_difficulty_distribution():
    """Test that we have correct distribution of difficulty levels."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    difficulty_counts = {diff: 0 for diff in Difficulty}
    for task in tasks:
        difficulty_counts[task.difficulty] += 1

    assert difficulty_counts[Difficulty.EASY] == 4, "Expected 4 easy tasks"
    assert difficulty_counts[Difficulty.MEDIUM] == 4, "Expected 4 medium tasks"
    assert difficulty_counts[Difficulty.HARD] == 4, "Expected 4 hard tasks"


def test_all_tasks_have_test_file():
    """Test that all tasks have valid scoring.test_file."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    for task in tasks:
        assert task.scoring.test_file is not None, f"Task {task.name} missing test_file"
        assert len(task.scoring.test_file) > 0, f"Task {task.name} has empty test_file"


def test_bugfix_and_refactor_have_starter_code():
    """Test that bug-fix and refactor tasks have starter_code or starter_files."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    for task in tasks:
        if task.task_type in (TaskType.BUG_FIX, TaskType.REFACTOR):
            assert (
                task.starter_code is not None or task.starter_files is not None
            ), f"Task {task.name} missing starter_code or starter_files"


def test_instruction_tasks_have_rules():
    """Test that instruction tasks have prompt_rules or claudemd_rules."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    for task in tasks:
        if task.task_type == TaskType.INSTRUCTION:
            assert (
                task.prompt_rules is not None or task.claudemd_rules is not None
            ), f"Task {task.name} missing prompt_rules or claudemd_rules"


def test_at_least_one_instruction_task_has_both_rules():
    """Test that at least one instruction task has BOTH claudemd_rules AND prompt_rules."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    instruction_tasks = [t for t in tasks if t.task_type == TaskType.INSTRUCTION]
    tasks_with_both = [
        t for t in instruction_tasks if t.claudemd_rules and t.prompt_rules
    ]

    assert len(tasks_with_both) >= 1, "Expected at least one instruction task with both claudemd_rules and prompt_rules"


def test_no_duplicate_task_names():
    """Test that all task names are unique."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    task_names = [task.name for task in tasks]
    assert len(task_names) == len(set(task_names)), "Duplicate task names found"


def test_refactor_tasks_have_reference_solutions():
    """Test that refactor tasks have reference solutions."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    for task in tasks:
        if task.task_type == TaskType.REFACTOR:
            assert (
                task.scoring.reference_solution is not None
            ), f"Refactor task {task.name} missing reference_solution"


def test_all_tasks_have_tags():
    """Test that all tasks have tags."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    for task in tasks:
        assert task.tags is not None, f"Task {task.name} missing tags"
        assert len(task.tags) > 0, f"Task {task.name} has empty tags list"


def test_all_tasks_have_description():
    """Test that all tasks have non-empty descriptions."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    for task in tasks:
        assert task.description is not None, f"Task {task.name} missing description"
        assert len(task.description.strip()) > 0, f"Task {task.name} has empty description"


def test_all_tasks_have_prompt():
    """Test that all tasks have non-empty prompts."""
    tasks_dir = Path(__file__).parent.parent / "tasks" / "builtin"
    tasks, _ = discover_tasks(tasks_dir)

    for task in tasks:
        assert task.prompt is not None, f"Task {task.name} missing prompt"
        assert len(task.prompt.strip()) > 0, f"Task {task.name} has empty prompt"
