"""Python-specific static analysis scorer for claude-benchmark.

Implements PythonStaticScorer (ruff, pytest, radon) as a subclass of
BaseStaticScorer. Also re-exports normalization functions and count_loc
for backward compatibility with existing imports.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from radon.complexity import cc_rank, cc_visit

from .base_scorer import (
    BaseStaticScorer,
    normalize_complexity_score,
    normalize_lint_score,
    normalize_test_pass_rate,
)
from .errors import StaticAnalysisError
from .models import ScoringWeights

logger = logging.getLogger(__name__)


# Re-export normalization functions for backward compatibility.
# Existing code imports these from claude_benchmark.scoring.static.
__all__ = [
    "normalize_test_pass_rate",
    "normalize_lint_score",
    "normalize_complexity_score",
    "count_loc",
    "PythonStaticScorer",
    "StaticScorer",
]


def count_loc(source_files: list[Path]) -> int:
    """Count non-empty, non-comment lines across all Python files.

    Used for lint normalization (errors per LOC).
    Kept for backward compat — new code should use scorer.count_loc().
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
# PythonStaticScorer
# ---------------------------------------------------------------------------


class PythonStaticScorer(BaseStaticScorer):
    """Python-specific static scorer using ruff, pytest, and radon.

    Extends BaseStaticScorer with Python toolchain implementations.
    """

    def source_glob(self) -> str:
        return "*.py"

    def test_glob_patterns(self) -> list[str]:
        return ["test_*.py", "*_test.py"]

    def comment_prefixes(self) -> list[str]:
        return ["#"]

    def run_ruff(self, target_dir: Path, rules: list[str] | None = None) -> dict:
        """Backward-compatible alias for run_lint."""
        return self.run_lint(target_dir, rules)

    def run_pytest(self, test_file: Path, workspace: Path) -> dict:
        """Backward-compatible alias for run_tests."""
        return self.run_tests(test_file, workspace)

    def run_lint(self, target_dir: Path, rules: list[str] | None = None) -> dict:
        """Run ruff check and return parsed JSON results.

        CRITICAL: Does NOT use check=True. Ruff returns exit code 1 for
        "violations found" which is expected. Only raises StaticAnalysisError
        if returncode >= 2.

        Returns: {"violations": list, "count": int}
        """
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

        if result.returncode >= 2:
            raise StaticAnalysisError(f"Ruff failed: {result.stderr}", tool="ruff")

        violations = json.loads(result.stdout) if result.stdout.strip() else []
        return {"violations": violations, "count": len(violations)}

    def run_tests(self, test_file: Path, workspace: Path) -> dict:
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

        test_file_abs = test_file.resolve()
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

        Handles SyntaxError gracefully: unparseable code gets F-rank (complexity=50).

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


# Backward-compatible alias
StaticScorer = PythonStaticScorer
