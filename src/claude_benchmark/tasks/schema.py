from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    CODE_GEN = "code-gen"
    BUG_FIX = "bug-fix"
    REFACTOR = "refactor"
    INSTRUCTION = "instruction"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Language(str, Enum):
    PYTHON = "python"
    GO = "go"
    JAVASCRIPT = "javascript"
    CSHARP = "csharp"


class RubricCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    weight: float = 1.0


class ScoringCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_file: str
    lint_rules: Optional[list[str]] = None
    ruff_rules: Optional[list[str]] = None  # deprecated: use lint_rules
    judge_rubric: Optional[str] = None
    reference_solution: Optional[str] = None
    weight_override: Optional[dict[str, float]] = None

    @property
    def effective_lint_rules(self) -> list[str] | None:
        """Return lint_rules if set, falling back to ruff_rules for backward compat."""
        return self.lint_rules or self.ruff_rules

    @model_validator(mode="after")
    def validate_lint_rules(self):
        if self.lint_rules and self.ruff_rules:
            logger.warning(
                "Both lint_rules and ruff_rules set; lint_rules takes precedence. "
                "ruff_rules is deprecated — use lint_rules instead."
            )
        return self


class TaskDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    task_type: TaskType
    difficulty: Difficulty
    description: str
    prompt: str
    language: Language = Language.PYTHON
    starter_code: Optional[str] = None
    starter_files: Optional[list[str]] = None
    expected_files: Optional[list[str]] = None
    claudemd_rules: Optional[str] = None
    prompt_rules: Optional[list[str]] = None
    scoring: ScoringCriteria
    tags: Optional[list[str]] = None
    size: str = "function"

    @model_validator(mode="after")
    def validate_type_requirements(self):
        if self.task_type in (TaskType.BUG_FIX, TaskType.REFACTOR):
            if not self.starter_code and not self.starter_files:
                raise ValueError(
                    f"{self.task_type.value} tasks must have starter_code or starter_files"
                )

        if self.task_type == TaskType.INSTRUCTION:
            if not self.claudemd_rules and not self.prompt_rules:
                raise ValueError(
                    "instruction tasks must have claudemd_rules or prompt_rules (or both)"
                )

        if self.size not in ("function", "module"):
            raise ValueError(f"size must be 'function' or 'module', got '{self.size}'")

        return self
