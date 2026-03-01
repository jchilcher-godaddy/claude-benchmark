import logging
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from .errors import TaskLoadError, TaskValidationError
from .schema import TaskDefinition

logger = logging.getLogger(__name__)


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

    # TODO: judge_rubric is validated here but not yet wired to LLMJudgeScorer.score().
    # When rubric-based scoring is implemented, pass this path through the pipeline.
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
