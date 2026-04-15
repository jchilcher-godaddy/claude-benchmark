"""JavaScript/TypeScript-specific static analysis scorer for claude-benchmark.

Implements JavaScriptStaticScorer using eslint, jest, and escomplex (cr).
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from .base_scorer import BaseStaticScorer
from .errors import StaticAnalysisError

logger = logging.getLogger(__name__)


def _check_tool(name: str, via_npx: bool = False) -> None:
    """Raise StaticAnalysisError if a required CLI tool is not available."""
    check = "npx" if via_npx else name
    if shutil.which(check) is None:
        raise StaticAnalysisError(
            f"{'npx' if via_npx else name} not found on PATH. Install Node.js:\n"
            f"  https://nodejs.org/\n"
            f"  eslint: npm install -g eslint\n"
            f"  jest: npm install -g jest\n"
            f"  complexity-report: npm install -g complexity-report",
            tool=name,
        )


class JavaScriptStaticScorer(BaseStaticScorer):
    """JavaScript/TypeScript static scorer using eslint, jest, and escomplex."""

    def source_glob(self) -> str:
        return "*.js"

    def source_extensions(self) -> list[str]:
        """Additional extensions beyond the primary glob."""
        return [".js", ".mjs", ".ts"]

    def test_glob_patterns(self) -> list[str]:
        return [
            "*.test.js",
            "*.spec.js",
            "*.test.ts",
            "*.spec.ts",
            "*.test.mjs",
            "*.spec.mjs",
        ]

    def comment_prefixes(self) -> list[str]:
        return ["//"]

    def find_source_files(self, output_dir: Path) -> list[Path]:
        """Override to handle multiple JS/TS extensions."""
        test_patterns = self.test_glob_patterns()
        source_files = []
        for ext in self.source_extensions():
            for f in output_dir.rglob(f"*{ext}"):
                if "node_modules" in f.parts:
                    continue
                if "__pycache__" in f.parts:
                    continue
                if any(f.match(pat) for pat in test_patterns):
                    continue
                source_files.append(f)
        return source_files

    def run_lint(self, target_dir: Path, rules: list[str] | None = None) -> dict:
        """Run eslint and return parsed results.

        Lints only source files (excludes test files copied for scoring).

        Returns: {"violations": list, "count": int}
        """
        js_files = self.find_source_files(target_dir)
        if not js_files:
            return {"violations": [], "count": 0}

        _check_tool("npx", via_npx=True)

        cmd = [
            "npx", "--yes", "eslint",
            "--no-config-lookup",
            "--format", "json",
        ] + [str(f.resolve()) for f in js_files]
        if rules:
            for rule in rules:
                cmd.extend(["--rule", f"{rule}: error"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(target_dir),
            )
        except subprocess.TimeoutExpired:
            raise StaticAnalysisError(
                "eslint timed out after 120 seconds", tool="eslint"
            )

        # eslint returns exit 1 for violations, exit 2 for fatal errors
        if result.returncode >= 2:
            raise StaticAnalysisError(
                f"eslint failed: {result.stderr}", tool="eslint"
            )

        violations = []
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                for file_result in data:
                    for msg in file_result.get("messages", []):
                        violations.append({
                            "code": msg.get("ruleId", "unknown"),
                            "message": msg.get("message", ""),
                            "filename": file_result.get("filePath", ""),
                            "location": {
                                "row": msg.get("line", 0),
                                "column": msg.get("column", 0),
                            },
                        })
            except json.JSONDecodeError:
                logger.warning("Failed to parse eslint JSON output")

        return {"violations": violations, "count": len(violations)}

    def run_tests(self, test_file: Path, workspace: Path) -> dict:
        """Run jest with JSON output and return structured results.

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

        _check_tool("npx", via_npx=True)

        try:
            result = subprocess.run(
                [
                    "npx", "--yes", "jest",
                    "--json",
                    "--no-coverage",
                    "--testPathPatterns", str(test_file.name),
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
                "error": "jest timed out after 120 seconds",
            }

        # Jest writes JSON to stdout even on test failure (exit 1)
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                passed = data.get("numPassedTests", 0)
                failed = data.get("numFailedTests", 0)
                skipped = data.get("numPendingTests", 0)
                total = data.get("numTotalTests", 0)
                # Jest duration is in ms in testResults
                duration = sum(
                    tr.get("perfStats", {}).get("runtime", 0)
                    for tr in data.get("testResults", [])
                ) / 1000.0

                return {
                    "exit_code": result.returncode,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "total": total,
                    "duration": duration,
                }
            except (json.JSONDecodeError, KeyError):
                logger.warning("Failed to parse jest JSON output")

        return {
            "exit_code": result.returncode,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "duration": 0,
            "error": result.stderr or "jest did not produce valid output",
        }

    def analyze_complexity(self, source_files: list[Path]) -> dict:
        """Analyze cyclomatic complexity using escomplex via cr CLI.

        Falls back to a keyword-counting heuristic if cr is unavailable.

        Returns: {"blocks": list[dict], "average_complexity": float, "max_complexity": int}
        """
        if not source_files:
            return {"blocks": [], "average_complexity": 0.0, "max_complexity": 0}

        all_blocks: list[dict] = []

        # Try cr (complexity-report) first
        if shutil.which("npx"):
            for filepath in source_files:
                try:
                    result = subprocess.run(
                        ["npx", "--yes", "cr", "--format", "json", str(filepath)],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        data = json.loads(result.stdout)
                        for report in data if isinstance(data, list) else [data]:
                            for fn in report.get("functions", []):
                                complexity = fn.get("cyclomatic", 1)
                                all_blocks.append({
                                    "file": str(filepath.name),
                                    "name": fn.get("name", "<anonymous>"),
                                    "type": "F",
                                    "complexity": complexity,
                                    "rank": self._rank(complexity),
                                    "lineno": fn.get("line", 0),
                                })
                except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                    # Fall through to heuristic for this file
                    all_blocks.extend(self._heuristic_complexity(filepath))
        else:
            for filepath in source_files:
                all_blocks.extend(self._heuristic_complexity(filepath))

        if not all_blocks:
            return {"blocks": [], "average_complexity": 0.0, "max_complexity": 0}

        complexities = [b["complexity"] for b in all_blocks]
        return {
            "blocks": all_blocks,
            "average_complexity": sum(complexities) / len(complexities),
            "max_complexity": max(complexities),
        }

    @staticmethod
    def _heuristic_complexity(filepath: Path) -> list[dict]:
        """Estimate complexity by counting branching keywords per function."""
        try:
            source = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return [{
                "file": str(filepath.name),
                "name": "<unreadable>",
                "type": "?",
                "complexity": 50,
                "rank": "F",
                "lineno": 0,
            }]

        # Count branching keywords as a rough whole-file complexity
        keywords = ["if", "for", "while", "case", "catch", "&&", "||", "?"]
        count = 1  # base complexity
        for kw in keywords:
            count += source.count(kw)

        if count <= 0:
            return []

        return [{
            "file": str(filepath.name),
            "name": "<file-level-heuristic>",
            "type": "F",
            "complexity": count,
            "rank": JavaScriptStaticScorer._rank(count),
            "lineno": 0,
        }]

    @staticmethod
    def _rank(complexity: int) -> str:
        """Map complexity to radon-style A-F rank for consistency."""
        if complexity <= 5:
            return "A"
        elif complexity <= 10:
            return "B"
        elif complexity <= 20:
            return "C"
        elif complexity <= 30:
            return "D"
        elif complexity <= 40:
            return "E"
        return "F"
