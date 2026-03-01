import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .loader import discover_tasks
from .schema import Difficulty, TaskDefinition, TaskType

logger = logging.getLogger(__name__)


@dataclass
class TaskRegistry:
    _tasks: list[TaskDefinition] = field(default_factory=list)

    def add(self, task: TaskDefinition):
        self._tasks.append(task)

    @property
    def all(self) -> list[TaskDefinition]:
        return list(self._tasks)

    def by_type(self, task_type: TaskType) -> list[TaskDefinition]:
        return [task for task in self._tasks if task.task_type == task_type]

    def by_difficulty(self, difficulty: Difficulty) -> list[TaskDefinition]:
        return [task for task in self._tasks if task.difficulty == difficulty]

    def by_name(self, name: str) -> Optional[TaskDefinition]:
        for task in self._tasks:
            if task.name == name:
                return task
        return None

    def by_tag(self, tag: str) -> list[TaskDefinition]:
        return [task for task in self._tasks if task.tags and tag in task.tags]

    @classmethod
    def from_directories(cls, *dirs: Path) -> "TaskRegistry":
        registry = cls()
        valid_tasks, errors = discover_tasks(*dirs)
        for task in valid_tasks:
            registry.add(task)
        for error in errors:
            logger.warning("Skipped invalid task: %s", error)
        return registry
