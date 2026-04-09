import logging
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from .errors import TaskLoadError, TaskValidationError
from .schema import TaskDefinition

logger = logging.getLogger(__name__)


def load_judge_rubric(rubric_path: Path) -> list[dict[str, str]]:
    """Load judge rubric criteria from a TOML file.

    The rubric file should contain an array of criteria tables:

        [[criteria]]
        name = "tone_adherence"
        description = "How well the code follows the requested tone"
        weight = 1.0

    Args:
        rubric_path: Path to the rubric TOML file.

    Returns:
        List of criteria dicts with "name" and "description" keys,
        matching the format used by BUILTIN_CRITERIA in scoring/prompts.py.

    Raises:
        TaskLoadError: If the file cannot be read or parsed.
    """
    if not rubric_path.exists():
        raise TaskLoadError(f"Rubric file not found: {rubric_path}")

    try:
        with open(rubric_path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise TaskLoadError(f"Invalid TOML syntax in {rubric_path}: {e}") from e

    criteria_raw = raw.get("criteria")
    if not criteria_raw or not isinstance(criteria_raw, list):
        raise TaskLoadError(
            f"Rubric file {rubric_path} must contain a 'criteria' array"
        )

    criteria = []
    for i, criterion in enumerate(criteria_raw):
        if not isinstance(criterion, dict):
            raise TaskLoadError(
                f"Criterion {i} in {rubric_path} is not a table"
            )
        name = criterion.get("name")
        description = criterion.get("description")
        if not name or not description:
            raise TaskLoadError(
                f"Criterion {i} in {rubric_path} missing 'name' or 'description'"
            )
        criteria.append({"name": str(name), "description": str(description)})

    return criteria


@lru_cache(maxsize=64)
def _load_task_cached(task_dir_str: str) -> TaskDefinition:
    """Cache-friendly inner loader keyed on the resolved string path."""
    return _load_task_impl(Path(task_dir_str))


def load_task(task_dir: Path) -> TaskDefinition:
    """Load and validate a TaskDefinition from a task directory.

    Results are cached by resolved path to avoid redundant TOML parsing
    when the same task is loaded multiple times (e.g., across scoring phases).
    """
    return _load_task_cached(str(task_dir.resolve()))


def _load_task_impl(task_dir: Path) -> TaskDefinition:
    toml_path = task_dir / "task.toml"

    if not toml_path.exists():
        raise TaskLoadError(f"task.toml not found in {task_dir}")

    try:
        with open(toml_path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise TaskLoadError(f"Invalid TOML syntax in {toml_path}: {e}") from e

    try:
        task = TaskDefinition.model_validate(raw)
    except ValidationError as e:
        raise TaskValidationError(task_dir.name, e) from e

    missing_files = []

    if task.scoring.test_file:
        test_path = task_dir / task.scoring.test_file
        if not test_path.exists():
            missing_files.append(task.scoring.test_file)

    if task.starter_code:
        starter_path = task_dir / task.starter_code
        if not starter_path.exists():
            missing_files.append(task.starter_code)

    if task.starter_files:
        for starter_file in task.starter_files:
            file_path = task_dir / starter_file
            if not file_path.exists():
                missing_files.append(starter_file)

    if task.scoring.reference_solution:
        ref_path = task_dir / task.scoring.reference_solution
        if not ref_path.exists():
            missing_files.append(task.scoring.reference_solution)

    if task.scoring.judge_rubric:
        rubric_path = task_dir / task.scoring.judge_rubric
        if not rubric_path.exists():
            missing_files.append(task.scoring.judge_rubric)

    if task.claudemd_rules:
        claudemd_path = task_dir / task.claudemd_rules
        if not claudemd_path.exists():
            missing_files.append(task.claudemd_rules)

    if missing_files:
        raise TaskLoadError(
            f"Task '{task.name}' in {task_dir} references missing files: {', '.join(missing_files)}"
        )

    return task


def discover_tasks(*search_dirs: Path) -> tuple[list[TaskDefinition], list[str]]:
    valid_tasks = []
    error_messages = []

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue

        task_dirs = sorted([d for d in search_dir.iterdir() if d.is_dir() and (d / "task.toml").exists()])

        for task_dir in task_dirs:
            try:
                task = load_task(task_dir)
                valid_tasks.append(task)
            except (TaskLoadError, TaskValidationError) as e:
                error_messages.append(f"{task_dir.name}: {e.message}")

    return valid_tasks, error_messages
