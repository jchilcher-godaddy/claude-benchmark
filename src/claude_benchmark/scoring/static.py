"""Static analysis scorer for claude-benchmark.

Runs Ruff (lint), pytest (test pass rate), and radon (cyclomatic complexity)
against benchmark output directories. Produces normalized 0-100 scores and
a weighted composite per the locked decisions.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from radon.complexity import cc_rank, cc_visit

from .errors import StaticAnalysisError
from .models import ScoringWeights, StaticScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalization functions (module-level, testable independently)
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


def count_loc(source_files: list[Path]) -> int:
    """Count non-empty, non-comment lines across all Python files.

    Used for lint normalization (errors per LOC).
    """
    total = 0
    for filepath in source_files:
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                total += 1
    return total


# ---------------------------------------------------------------------------
# StaticScorer class
# ---------------------------------------------------------------------------


class StaticScorer:
    """Runs static analysis tools and produces a normalized StaticScore.

    Orchestrates Ruff (lint), pytest (test pass rate), and radon (complexity)
    against a benchmark output directory.
    """

    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self.weights = weights or ScoringWeights()

    def run_ruff(self, target_dir: Path, rules: list[str] | None = None) -> dict:
        """Run ruff check and return parsed JSON results.

        CRITICAL: Does NOT use check=True. Ruff returns exit code 1 for
        "violations found" which is expected. Only raises StaticAnalysisError
        if returncode >= 2.

        Returns: {"violations": list, "count": int}
        """
        # Check if there are any .py files to lint
        py_files = list(target_dir.rglob("*.py"))
        if not py_files:
            return {"violations": [], "count": 0}

        cmd = ["ruff", "check", str(target_dir), "--output-format", "json"]
        if rules:
            cmd.extend(["--select", ",".join(rules)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise StaticAnalysisError("Ruff timed out after 60 seconds", tool="ruff")
        except FileNotFoundError:
            raise StaticAnalysisError("Ruff not found -- is it installed?", tool="ruff")

        # Exit code 0 = clean, 1 = violations found, >= 2 = error
        if result.returncode >= 2:
            raise StaticAnalysisError(f"Ruff failed: {result.stderr}", tool="ruff")

        violations = json.loads(result.stdout) if result.stdout.strip() else []
        return {"violations": violations, "count": len(violations)}

    def run_pytest(self, test_file: Path, workspace: Path) -> dict:
        """Run pytest on a test file and return structured results.

        Uses pytest-json-report for machine-readable output.

        Returns: dict with exit_code, passed, failed, skipped, total, duration, error.
        """
        if not test_file.exists():
            return {
                "exit_code": -1,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "duration": 0,
                "error": f"Test file not found: {test_file}",
            }

        # Resolve to absolute path so pytest can find the file regardless
        # of its subprocess cwd (which is set to the workspace/output dir).
        test_file_abs = test_file.resolve()

        # Resolve to absolute so the subprocess (cwd=workspace) and the
        # parent process (cwd=project root) use the same physical path.
        report_path = (workspace / ".test-report.json").resolve()

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(test_file_abs),
                    "--json-report",
                    f"--json-report-file={report_path}",
                    "--tb=short",
                    "-q",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(workspace),
            )
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "duration": 0,
                "error": "pytest timed out after 120 seconds",
            }
        except FileNotFoundError:
            return {
                "exit_code": -1,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "duration": 0,
                "error": f"Python not found at {sys.executable}",
            }

        # Pytest exit codes: 0=pass, 1=fail, 2=interrupt, 3=internal error, 4=usage error, 5=no tests
        if result.returncode in (3, 4):
            return {
                "exit_code": result.returncode,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "duration": 0,
                "error": f"pytest crash (exit {result.returncode}): {result.stderr}",
            }

        # Parse JSON report if it exists
        if report_path.exists():
            try:
                with open(report_path) as f:
                    report = json.load(f)
                summary = report.get("summary", {})
                return {
                    "exit_code": result.returncode,
                    "passed": summary.get("passed", 0),
                    "failed": summary.get("failed", 0),
                    "skipped": summary.get("skipped", 0),
                    "total": summary.get("total", 0),
                    "duration": report.get("duration", 0),
                }
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to parse test report: %s", exc)

        # Fallback: no report generated
        return {
            "exit_code": result.returncode,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "duration": 0,
            "error": result.stderr or "pytest did not produce a report",
        }

    def analyze_complexity(self, source_files: list[Path]) -> dict:
        """Analyze cyclomatic complexity using radon's Python API.

        Handles SyntaxError gracefully: unparseable code gets F-rank (complexity=50)
        per Pitfall 4 in RESEARCH.md.

        Returns: {"blocks": list[dict], "average_complexity": float, "max_complexity": int}
        """
        all_blocks: list[dict] = []

        for filepath in source_files:
            try:
                source = filepath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                all_blocks.append(
                    {
                        "file": str(filepath.name),
                        "name": "<unreadable>",
                        "type": "?",
                        "complexity": 50,
                        "rank": "F",
                        "lineno": 0,
                    }
                )
                continue

            try:
                blocks = cc_visit(source)
                for block in blocks:
                    all_blocks.append(
                        {
                            "file": str(filepath.name),
                            "name": block.name,
                            "type": block.letter,
                            "complexity": block.complexity,
                            "rank": cc_rank(block.complexity),
                            "lineno": block.lineno,
                        }
                    )
            except SyntaxError:
                # Unparseable code gets worst-case complexity
                all_blocks.append(
                    {
                        "file": str(filepath.name),
                        "name": "<unparseable>",
                        "type": "?",
                        "complexity": 50,
                        "rank": "F",
                        "lineno": 0,
                    }
                )

        if not all_blocks:
            return {"blocks": [], "average_complexity": 0.0, "max_complexity": 0}

        complexities = [b["complexity"] for b in all_blocks]
        return {
            "blocks": all_blocks,
            "average_complexity": sum(complexities) / len(complexities),
            "max_complexity": max(complexities),
        }

    def score(
        self,
        output_dir: Path,
        test_file: Path,
        ruff_rules: list[str] | None = None,
    ) -> StaticScore:
        """Orchestrate the full static scoring pipeline.

        1. Find .py files in output_dir (excluding tests and __pycache__)
        2. Count LOC
        3. Run Ruff, normalize lint score
        4. Run pytest, normalize test pass rate
        5. Analyze complexity, normalize complexity score
        6. Compute weighted_total
        7. Return StaticScore with all fields
        """
        # Find source files (exclude test files and __pycache__)
        source_files = [
            f
            for f in output_dir.rglob("*.py")
            if "__pycache__" not in str(f)
            and not f.name.startswith("test_")
            and not f.name.endswith("_test.py")
        ]

        # Edge case: no Python files
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

        # Count LOC
        loc = count_loc(source_files)

        # Run Ruff
        try:
            ruff_result = self.run_ruff(output_dir, rules=ruff_rules)
            lint_errors = ruff_result["count"]
            lint_details = ruff_result["violations"]
            lint_score = normalize_lint_score(lint_errors, loc)
        except StaticAnalysisError as exc:
            logger.warning("Ruff failed: %s", exc)
            lint_errors = 0
            lint_details = []
            lint_score = 0.0

        # Run pytest
        pytest_result = self.run_pytest(test_file, output_dir)
        passed = pytest_result["passed"]
        total = pytest_result["total"]
        test_pass_rate = normalize_test_pass_rate(passed, total)

        # Analyze complexity
        complexity_result = self.analyze_complexity(source_files)
        avg_complexity = complexity_result["average_complexity"]
        complexity_details = complexity_result["blocks"]
        complexity_score = normalize_complexity_score(avg_complexity)

        # Compute weighted total
        w = self.weights
        weighted_total = (
            test_pass_rate * w.test_pass_rate
            + lint_score * w.lint_score
            + complexity_score * w.complexity_score
        )

        return StaticScore(
            test_pass_rate=round(test_pass_rate, 2),
            tests_passed=passed,
            tests_total=total,
            lint_score=round(lint_score, 2),
            lint_errors=lint_errors,
            lint_details=lint_details,
            complexity_score=round(complexity_score, 2),
            avg_complexity=round(avg_complexity, 2),
            complexity_details=complexity_details,
            weighted_total=round(weighted_total, 2),
            lines_of_code=loc,
        )
