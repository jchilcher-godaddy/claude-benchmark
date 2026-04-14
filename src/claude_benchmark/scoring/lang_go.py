"""Go-specific static analysis scorer for claude-benchmark.

Implements GoStaticScorer using golangci-lint, go test, and gocyclo.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from .base_scorer import BaseStaticScorer
from .errors import StaticAnalysisError

logger = logging.getLogger(__name__)


def _check_tool(name: str) -> None:
    """Raise StaticAnalysisError if a required CLI tool is not on PATH."""
    if shutil.which(name) is None:
        raise StaticAnalysisError(
            f"{name} not found on PATH. Install it:\n"
            f"  go: https://go.dev/doc/install\n"
            f"  golangci-lint: https://golangci-lint.run/welcome/install/\n"
            f"  gocyclo: go install github.com/fzipp/gocyclo/cmd/gocyclo@latest",
            tool=name,
        )


class GoStaticScorer(BaseStaticScorer):
    """Go static scorer using golangci-lint, go test, and gocyclo."""

    def source_glob(self) -> str:
        return "*.go"

    def test_glob_patterns(self) -> list[str]:
        return ["*_test.go"]

    def comment_prefixes(self) -> list[str]:
        return ["//"]

    def run_lint(self, target_dir: Path, rules: list[str] | None = None) -> dict:
        """Run golangci-lint and return parsed results.

        Returns: {"violations": list, "count": int}
        """
        go_files = list(target_dir.rglob("*.go"))
        if not go_files:
            return {"violations": [], "count": 0}

        _check_tool("golangci-lint")

        cmd = ["golangci-lint", "run", "--out-format", "json", "./..."]
        if rules:
            cmd.extend(["--enable", ",".join(rules)])

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
                "golangci-lint timed out after 120 seconds", tool="golangci-lint"
            )

        # golangci-lint returns exit 1 for violations found (expected),
        # exit 3+ for tool failures.
        if result.returncode >= 3:
            raise StaticAnalysisError(
                f"golangci-lint failed: {result.stderr}", tool="golangci-lint"
            )

        violations = []
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                for issue in data.get("Issues", []) or []:
                    violations.append({
                        "code": issue.get("FromLinter", "unknown"),
                        "message": issue.get("Text", ""),
                        "filename": issue.get("Pos", {}).get("Filename", ""),
                        "location": {
                            "row": issue.get("Pos", {}).get("Line", 0),
                            "column": issue.get("Pos", {}).get("Column", 0),
                        },
                    })
            except json.JSONDecodeError:
                logger.warning("Failed to parse golangci-lint JSON output")

        return {"violations": violations, "count": len(violations)}

    def run_tests(self, test_file: Path, workspace: Path) -> dict:
        """Run go test with JSON output and return structured results.

        The test_file parameter identifies the package to test. For Go,
        we run `go test -json ./...` in the workspace directory.

        Returns: dict with exit_code, passed, failed, skipped, total, duration, error.
        """
        _check_tool("go")

        # Ensure go.mod exists — go test requires a module
        go_mod = workspace / "go.mod"
        if not go_mod.exists():
            return {
                "exit_code": -1,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "duration": 0,
                "error": f"No go.mod found in {workspace}",
            }

        try:
            result = subprocess.run(
                ["go", "test", "-json", "-count=1", "./..."],
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
                "error": "go test timed out after 120 seconds",
            }

        passed = 0
        failed = 0
        skipped = 0
        duration = 0.0

        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            action = event.get("Action")
            test_name = event.get("Test")

            # Only count individual test results (not package-level)
            if test_name is None:
                if action == "pass" and "Elapsed" in event:
                    duration += event.get("Elapsed", 0)
                continue

            if action == "pass":
                passed += 1
            elif action == "fail":
                failed += 1
            elif action == "skip":
                skipped += 1

        total = passed + failed + skipped

        return {
            "exit_code": result.returncode,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": total,
            "duration": duration,
        }

    def analyze_complexity(self, source_files: list[Path]) -> dict:
        """Analyze cyclomatic complexity using gocyclo.

        gocyclo outputs lines like:
            9 pkg (*Type).Method file.go:10:1

        Returns: {"blocks": list[dict], "average_complexity": float, "max_complexity": int}
        """
        if not source_files:
            return {"blocks": [], "average_complexity": 0.0, "max_complexity": 0}

        _check_tool("gocyclo")

        file_args = [str(f) for f in source_files]
        try:
            result = subprocess.run(
                ["gocyclo", "-over", "0"] + file_args,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise StaticAnalysisError(
                "gocyclo timed out after 60 seconds", tool="gocyclo"
            )

        all_blocks: list[dict] = []
        # Pattern: complexity package function file:line:col
        pattern = re.compile(r"^(\d+)\s+(\S+)\s+(\S+)\s+(\S+):(\d+):\d+")

        for line in result.stdout.splitlines():
            m = pattern.match(line.strip())
            if m:
                complexity = int(m.group(1))
                all_blocks.append({
                    "file": m.group(4),
                    "name": m.group(3),
                    "type": "F",
                    "complexity": complexity,
                    "rank": self._rank(complexity),
                    "lineno": int(m.group(5)),
                })

        if not all_blocks:
            return {"blocks": [], "average_complexity": 0.0, "max_complexity": 0}

        complexities = [b["complexity"] for b in all_blocks]
        return {
            "blocks": all_blocks,
            "average_complexity": sum(complexities) / len(complexities),
            "max_complexity": max(complexities),
        }

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
