"""Scoring error hierarchy for the claude-benchmark scoring subsystem."""

from __future__ import annotations


class ScoringError(Exception):
    """Base class for all scoring errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class StaticAnalysisError(ScoringError):
    """Raised when a static analysis tool (Ruff, pytest, radon) fails unexpectedly.

    This is for actual tool crashes, not for lint violations or test failures
    which are expected outcomes.
    """

    def __init__(self, message: str, tool: str | None = None) -> None:
        self.tool = tool
        super().__init__(message)


class LLMJudgeError(ScoringError):
    """Raised when LLM-as-judge scoring fails.

    Covers API errors, invalid responses, and validation failures.
    """

    def __init__(self, message: str, retry_attempted: bool = False) -> None:
        self.retry_attempted = retry_attempted
        super().__init__(message)


_DETERMINISTIC_PATTERNS = [
    "No Python files found",
    "Could not read any Python files",
    "aws_credentials_expired",
]


def is_deterministic_llm_error(exc: LLMJudgeError) -> bool:
    """Check if an LLM judge error is deterministic and should not be retried."""
    return any(pat in str(exc) for pat in _DETERMINISTIC_PATTERNS)
