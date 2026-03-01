import pytest
from pydantic import ValidationError

from claude_benchmark.tasks.errors import TaskValidationError
from claude_benchmark.tasks.schema import (
    Difficulty,
    ScoringCriteria,
    TaskDefinition,
    TaskType,
)


def test_valid_code_gen_task():
    task_dict = {
        "name": "test-task",
        "task_type": "code-gen",
        "difficulty": "easy",
        "description": "Test description",
        "prompt": "Test prompt",
        "scoring": {"test_file": "test_solution.py"},
    }
    task = TaskDefinition(**task_dict)
    assert task.name == "test-task"
    assert task.task_type == TaskType.CODE_GEN
    assert task.difficulty == Difficulty.EASY


def test_valid_bug_fix_task_with_starter_code():
    task_dict = {
        "name": "bug-fix-task",
        "task_type": "bug-fix",
        "difficulty": "medium",
        "description": "Fix the bug",
        "prompt": "Fix this code",
        "starter_code": "buggy.py",
        "scoring": {"test_file": "test_solution.py"},
    }
    task = TaskDefinition(**task_dict)
    assert task.task_type == TaskType.BUG_FIX
    assert task.starter_code == "buggy.py"


def test_valid_instruction_task_with_prompt_rules():
    task_dict = {
        "name": "instruction-task",
        "task_type": "instruction",
        "difficulty": "hard",
        "description": "Follow instructions",
        "prompt": "Use these rules",
        "prompt_rules": ["rule1", "rule2"],
        "scoring": {"test_file": "test_solution.py"},
    }
    task = TaskDefinition(**task_dict)
    assert task.task_type == TaskType.INSTRUCTION
    assert task.prompt_rules == ["rule1", "rule2"]


def test_bug_fix_missing_starter_code_and_files():
    task_dict = {
        "name": "bug-fix-task",
        "task_type": "bug-fix",
        "difficulty": "medium",
        "description": "Fix the bug",
        "prompt": "Fix this code",
        "scoring": {"test_file": "test_solution.py"},
    }
    with pytest.raises(ValidationError) as exc_info:
        TaskDefinition(**task_dict)
    assert "must have starter_code or starter_files" in str(exc_info.value)


def test_instruction_missing_rules():
    task_dict = {
        "name": "instruction-task",
        "task_type": "instruction",
        "difficulty": "hard",
        "description": "Follow instructions",
        "prompt": "Use these rules",
        "scoring": {"test_file": "test_solution.py"},
    }
    with pytest.raises(ValidationError) as exc_info:
        TaskDefinition(**task_dict)
    assert "must have claudemd_rules or prompt_rules" in str(exc_info.value)


def test_invalid_task_type():
    task_dict = {
        "name": "test-task",
        "task_type": "invalid-type",
        "difficulty": "easy",
        "description": "Test description",
        "prompt": "Test prompt",
        "scoring": {"test_file": "test_solution.py"},
    }
    with pytest.raises(ValidationError):
        TaskDefinition(**task_dict)


def test_invalid_difficulty():
    task_dict = {
        "name": "test-task",
        "task_type": "code-gen",
        "difficulty": "impossible",
        "description": "Test description",
        "prompt": "Test prompt",
        "scoring": {"test_file": "test_solution.py"},
    }
    with pytest.raises(ValidationError):
        TaskDefinition(**task_dict)


def test_missing_required_field_name():
    task_dict = {
        "task_type": "code-gen",
        "difficulty": "easy",
        "description": "Test description",
        "prompt": "Test prompt",
        "scoring": {"test_file": "test_solution.py"},
    }
    with pytest.raises(ValidationError):
        TaskDefinition(**task_dict)


def test_missing_required_field_prompt():
    task_dict = {
        "name": "test-task",
        "task_type": "code-gen",
        "difficulty": "easy",
        "description": "Test description",
        "scoring": {"test_file": "test_solution.py"},
    }
    with pytest.raises(ValidationError):
        TaskDefinition(**task_dict)


def test_missing_required_field_scoring():
    task_dict = {
        "name": "test-task",
        "task_type": "code-gen",
        "difficulty": "easy",
        "description": "Test description",
        "prompt": "Test prompt",
    }
    with pytest.raises(ValidationError):
        TaskDefinition(**task_dict)


def test_task_validation_error_formatting():
    task_name = "my-task"
    try:
        task_dict = {
            "task_type": "code-gen",
            "difficulty": "easy",
            "description": "Test description",
            "prompt": "Test prompt",
            "scoring": {"test_file": "test_solution.py"},
        }
        TaskDefinition(**task_dict)
    except ValidationError as e:
        error = TaskValidationError(task_name, e)
        assert "my-task" in error.message
        assert "Validation failed" in error.message
        assert "name" in error.message
