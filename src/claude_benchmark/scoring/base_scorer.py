"""Abstract base class for language-specific static scorers.

Provides shared orchestration (score, count_loc, find_source_files) and
normalization functions. Language-specific subclasses implement lint, test,
and complexity analysis using their own toolchains.

Normalization functions are defined here (not in static.py) to avoid
circular imports — static.py subclasses BaseStaticScorer.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from .models import ScoringWeights, StaticScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalization functions (module-level, language-agnostic, testable)
# ---------------------------------------------------------------------------


def normalize_test_pass_rate(passed: int, total: int) -> float:
    """Test pass rate as percentage. 0-100 scale.

    If total == 0 (no tests), returns 0.0 -- no tests means no credit.
    """
    if total == 0:
        return 0.0
    return (passed / total) * 100.0


def normalize_lint_score(error_count: int, loc: int) -> float:
    """Lint score: fewer errors per LOC = higher score. 0-100 scale.

    Formula: max(0, 100 - (error_count / loc) * 1000)
    This means ~10 errors per 100 LOC gives score 0.
    If loc == 0 (no code), returns 100.0 (nothing to lint).
    """
    if loc == 0:
        return 100.0
    score = 100.0 - (error_count / loc) * 1000.0
    return max(0.0, min(100.0, score))


def normalize_complexity_score(avg_complexity: float) -> float:
    """Complexity score: lower complexity = higher score. 0-100 scale.

    Maps radon's A-F grades to linear segments:
      A (1-5):   100 -> 80
      B (6-10):  80 -> 60
      C (11-20): 60 -> 40
      D (21-30): 40 -> 20
      E (31-40): 20 -> 5
      F (41+):   5 -> 0

    If avg_complexity == 0 (no functions), returns 100.0.
    """
    if avg_complexity <= 0:
        return 100.0
    if avg_complexity <= 5:
        return 100.0 - (avg_complexity - 1) * 5.0  # 100 -> 80
    elif avg_complexity <= 10:
        return 80.0 - (avg_complexity - 5) * 4.0  # 80 -> 60
    elif avg_complexity <= 20:
        return 60.0 - (avg_complexity - 10) * 2.0  # 60 -> 40
    elif avg_complexity <= 30:
        return 40.0 - (avg_complexity - 20) * 2.0  # 40 -> 20
    elif avg_complexity <= 40:
        return 20.0 - (avg_complexity - 30) * 1.5  # 20 -> 5
    else:
        return max(0.0, 5.0 - (avg_complexity - 40) * 0.5)


# ---------------------------------------------------------------------------
# BaseStaticScorer ABC
# ---------------------------------------------------------------------------


class BaseStaticScorer(ABC):
    """Abstract base for language-specific static analysis scorers.

    Subclasses must implement:
    - source_glob(): file pattern for source files (e.g., "*.py", "*.go")
    - test_glob_patterns(): patterns to exclude test files from source analysis
    - comment_prefixes(): line-comment prefixes for LOC counting
    - run_lint(): language-specific linter
    - run_tests(): language-specific test runner
    - analyze_complexity(): language-specific complexity analysis
    """

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self.weights = weights or ScoringWeights()

    @abstractmethod
    def source_glob(self) -> str:
        """Return the glob pattern for source files (e.g., '*.py', '*.go')."""

    @abstractmethod
    def test_glob_patterns(self) -> list[str]:
        """Return glob patterns that identify test files to exclude from source analysis."""

    @abstractmethod
    def comment_prefixes(self) -> list[str]:
        """Return comment line prefixes for LOC counting (e.g., ['#'] or ['//'])."""

    @abstractmethod
    def run_lint(self, target_dir: Path, rules: list[str] | None = None) -> dict:
        """Run language-specific linter.

        Returns: {"violations": list, "count": int}
        """

    @abstractmethod
    def run_tests(self, test_file: Path, workspace: Path) -> dict:
        """Run language-specific test runner.

        Returns: dict with keys: exit_code, passed, failed, skipped, total, duration,
                 and optionally error.
        """

    @abstractmethod
    def analyze_complexity(self, source_files: list[Path]) -> dict:
        """Analyze cyclomatic complexity for source files.

        Returns: {"blocks": list[dict], "average_complexity": float, "max_complexity": int}
        """

    def count_loc(self, source_files: Sequence[Path]) -> int:
        """Count non-empty, non-comment lines across source files.

        Uses self.comment_prefixes() to detect language-appropriate comments.
        """
        prefixes = tuple(self.comment_prefixes())
        total = 0
        for filepath in source_files:
            try:
                content = filepath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line in content.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith(prefixes):
                    total += 1
        return total

    def find_source_files(self, output_dir: Path) -> list[Path]:
        """Find source files in output_dir, excluding test files and cache dirs."""
        test_patterns = self.test_glob_patterns()
        source_files = []
        for f in output_dir.rglob(self.source_glob()):
            if "__pycache__" in str(f):
                continue
            if any(f.match(pat) for pat in test_patterns):
                continue
            source_files.append(f)
        return source_files

    def score(
        self,
        output_dir: Path,
        test_file: Path,
        lint_rules: list[str] | None = None,
    ) -> StaticScore:
        """Orchestrate the full static scoring pipeline.

        1. Find source files in output_dir
        2. Count LOC
        3. Run linter, normalize lint score
        4. Run tests, normalize test pass rate
        5. Analyze complexity, normalize complexity score
        6. Compute weighted_total
        7. Return StaticScore
        """
        source_files = self.find_source_files(output_dir)

        if not source_files:
            return StaticScore(
                test_pass_rate=0,
                tests_passed=0,
                tests_total=0,
                lint_score=0,
                lint_errors=0,
                complexity_score=0,
                avg_complexity=0,
                weighted_total=0,
                lines_of_code=0,
            )

        loc = self.count_loc(source_files)

        # Lint
        try:
            lint_result = self.run_lint(output_dir, rules=lint_rules)
            lint_errors = lint_result["count"]
            lint_details = lint_result["violations"]
            lint_score_val = normalize_lint_score(lint_errors, loc)
        except Exception as exc:
            logger.warning("Linter failed: %s", exc)
            lint_errors = 0
            lint_details = []
            lint_score_val = 0.0

        # Tests
        test_result = self.run_tests(test_file, output_dir)
        passed = test_result["passed"]
        total = test_result["total"]
        test_pass_rate = normalize_test_pass_rate(passed, total)

        # Complexity
        complexity_result = self.analyze_complexity(source_files)
        avg_complexity = complexity_result["average_complexity"]
        complexity_details = complexity_result["blocks"]
        complexity_score_val = normalize_complexity_score(avg_complexity)

        w = self.weights
        weighted_total = (
            test_pass_rate * w.test_pass_rate
            + lint_score_val * w.lint_score
            + complexity_score_val * w.complexity_score
        )

        return StaticScore(
            test_pass_rate=round(test_pass_rate, 2),
            tests_passed=passed,
            tests_total=total,
            lint_score=round(lint_score_val, 2),
            lint_errors=lint_errors,
            lint_details=lint_details,
            complexity_score=round(complexity_score_val, 2),
            avg_complexity=round(avg_complexity, 2),
            complexity_details=complexity_details,
            weighted_total=round(weighted_total, 2),
            lines_of_code=loc,
        )
