"""C#-specific static analysis scorer for claude-benchmark.

Implements CSharpStaticScorer using dotnet format, dotnet test, and a
keyword-based complexity heuristic (v1; Roslyn upgrade planned for v2).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from .base_scorer import BaseStaticScorer
from .errors import StaticAnalysisError

logger = logging.getLogger(__name__)


def _check_tool(name: str) -> None:
    """Raise StaticAnalysisError if a required CLI tool is not on PATH."""
    if shutil.which(name) is None:
        raise StaticAnalysisError(
            f"{name} not found on PATH. Install .NET SDK:\n"
            f"  https://dotnet.microsoft.com/download",
            tool=name,
        )


class CSharpStaticScorer(BaseStaticScorer):
    """C# static scorer using dotnet format, dotnet test, and keyword heuristic."""

    def source_glob(self) -> str:
        return "*.cs"

    def test_glob_patterns(self) -> list[str]:
        return ["*Tests.cs", "*Test.cs", "*_test.cs", "*_tests.cs"]

    def comment_prefixes(self) -> list[str]:
        return ["//", "///"]

    def run_lint(self, target_dir: Path, rules: list[str] | None = None) -> dict:
        """Run dotnet format to check for style violations.

        `dotnet format --verify-no-changes` returns exit 0 if clean, non-zero
        if there are violations. We parse the diagnostics from stderr/stdout.

        Returns: {"violations": list, "count": int}
        """
        # Resolve to absolute to avoid cwd-relative mismatches
        target_dir = target_dir.resolve()
        cs_files = list(target_dir.rglob("*.cs"))
        if not cs_files:
            return {"violations": [], "count": 0}

        # Find .csproj — dotnet format needs a project/solution
        csproj_files = list(target_dir.rglob("*.csproj"))
        if not csproj_files:
            return {"violations": [], "count": 0}

        _check_tool("dotnet")

        report_path = target_dir / ".format-report.json"
        cmd = [
            "dotnet", "format",
            str(csproj_files[0]),
            "--verify-no-changes",
            "--report", str(report_path),
        ]

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
                "dotnet format timed out after 120 seconds", tool="dotnet"
            )

        violations = []

        # Try to read the format report
        if report_path.exists():
            try:
                import json
                with open(report_path) as f:
                    report_data = json.load(f)
                for entry in report_data:
                    for change in entry.get("FileChanges", []):
                        violations.append({
                            "code": change.get("DiagnosticId", "format"),
                            "message": change.get("FormatDescription", "formatting issue"),
                            "filename": entry.get("FilePath", ""),
                            "location": {
                                "row": change.get("LineNumber", 0),
                                "column": change.get("CharNumber", 0),
                            },
                        })
            except Exception:
                logger.warning("Failed to parse dotnet format report")

        # If no report, count based on exit code
        if not violations and result.returncode != 0:
            # Parse stderr for diagnostic lines
            for line in result.stderr.splitlines() + result.stdout.splitlines():
                # Pattern: filepath(line,col): severity code: message
                m = re.match(r"(.+?)\((\d+),(\d+)\):\s+\w+\s+(\w+):\s+(.+)", line)
                if m:
                    violations.append({
                        "code": m.group(4),
                        "message": m.group(5),
                        "filename": m.group(1),
                        "location": {"row": int(m.group(2)), "column": int(m.group(3))},
                    })

        return {"violations": violations, "count": len(violations)}

    def run_tests(self, test_file: Path, workspace: Path) -> dict:
        """Run dotnet test with TRX logger and parse results.

        Returns: dict with exit_code, passed, failed, skipped, total, duration, error.
        """
        _check_tool("dotnet")

        # Resolve all paths to absolute to avoid cwd-relative mismatches
        workspace = workspace.resolve()
        csproj_files = list(workspace.rglob("*.csproj"))
        if not csproj_files:
            return {
                "exit_code": -1,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "duration": 0,
                "error": f"No .csproj found in {workspace}",
            }

        csproj = str(csproj_files[0])
        trx_dir = str(workspace / "TestResults")
        trx_path = workspace / "TestResults" / "results.trx"

        try:
            result = subprocess.run(
                [
                    "dotnet", "test", csproj,
                    "--logger", "trx;LogFileName=results.trx",
                    "--results-directory", trx_dir,
                    "--no-build",
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
                "error": "dotnet test timed out after 120 seconds",
            }

        # Retry with full build if --no-build didn't produce results.
        # This covers: no prior build, stale artifacts, or framework mismatch.
        if not trx_path.exists():
            try:
                result = subprocess.run(
                    [
                        "dotnet", "test", csproj,
                        "--logger", "trx;LogFileName=results.trx",
                        "--results-directory", trx_dir,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180,
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
                    "error": "dotnet test timed out after 180 seconds",
                }

        # Parse TRX (XML) results
        if trx_path.exists():
            return self._parse_trx(trx_path, result.returncode)

        return {
            "exit_code": result.returncode,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "duration": 0,
            "error": result.stderr or "dotnet test did not produce a TRX report",
        }

    def _parse_trx(self, trx_path: Path, exit_code: int) -> dict:
        """Parse a Visual Studio TRX test results file."""
        try:
            tree = ET.parse(trx_path)
            root = tree.getroot()

            # TRX uses a namespace
            ns = ""
            if root.tag.startswith("{"):
                ns = root.tag.split("}")[0] + "}"

            counters = root.find(f".//{ns}Counters")
            if counters is not None:
                passed = int(counters.get("passed", 0))
                failed = int(counters.get("failed", 0))
                total = int(counters.get("total", 0))
                skipped = total - passed - failed

                times = root.find(f".//{ns}Times")
                duration = 0.0
                if times is not None:
                    # Duration is in the format HH:MM:SS.mmm
                    finish = times.get("finish", "")
                    start = times.get("start", "")
                    # Simple approach: just report 0 for duration if parsing fails
                    try:
                        from datetime import datetime
                        fmt = "%Y-%m-%dT%H:%M:%S.%f"
                        # Handle timezone offset by stripping it
                        start_clean = re.sub(r"[+-]\d{2}:\d{2}$", "", start)
                        finish_clean = re.sub(r"[+-]\d{2}:\d{2}$", "", finish)
                        d = datetime.strptime(finish_clean, fmt) - datetime.strptime(start_clean, fmt)
                        duration = d.total_seconds()
                    except (ValueError, TypeError):
                        pass

                return {
                    "exit_code": exit_code,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "total": total,
                    "duration": duration,
                }
        except ET.ParseError:
            logger.warning("Failed to parse TRX file: %s", trx_path)

        return {
            "exit_code": exit_code,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "duration": 0,
            "error": f"Failed to parse TRX report at {trx_path}",
        }

    def analyze_complexity(self, source_files: list[Path]) -> dict:
        """Analyze cyclomatic complexity using keyword heuristic (v1).

        Counts branching keywords per method. A Roslyn-based analyzer
        is planned for v2.

        Returns: {"blocks": list[dict], "average_complexity": float, "max_complexity": int}
        """
        if not source_files:
            return {"blocks": [], "average_complexity": 0.0, "max_complexity": 0}

        all_blocks: list[dict] = []

        for filepath in source_files:
            try:
                source = filepath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                all_blocks.append({
                    "file": str(filepath.name),
                    "name": "<unreadable>",
                    "type": "?",
                    "complexity": 50,
                    "rank": "F",
                    "lineno": 0,
                })
                continue

            all_blocks.extend(self._analyze_methods(filepath.name, source))

        if not all_blocks:
            return {"blocks": [], "average_complexity": 0.0, "max_complexity": 0}

        complexities = [b["complexity"] for b in all_blocks]
        return {
            "blocks": all_blocks,
            "average_complexity": sum(complexities) / len(complexities),
            "max_complexity": max(complexities),
        }

    def _analyze_methods(self, filename: str, source: str) -> list[dict]:
        """Extract methods and estimate their cyclomatic complexity."""
        blocks = []
        # Simple regex to find method declarations
        # Matches: access modifier, optional static/async/override, return type, name, (
        method_pattern = re.compile(
            r"(?:public|private|protected|internal)"
            r"(?:\s+(?:static|async|override|virtual|abstract|sealed))*"
            r"\s+\w[\w<>\[\],\s]*?"  # return type
            r"\s+(\w+)\s*\(",        # method name
            re.MULTILINE,
        )

        for match in method_pattern.finditer(source):
            method_name = match.group(1)
            method_start = match.start()
            lineno = source[:method_start].count("\n") + 1

            # Find the method body by brace matching
            body = self._extract_body(source, match.end())
            complexity = self._count_complexity(body)

            blocks.append({
                "file": str(filename),
                "name": method_name,
                "type": "M",
                "complexity": complexity,
                "rank": self._rank(complexity),
                "lineno": lineno,
            })

        return blocks

    @staticmethod
    def _extract_body(source: str, start_after: int) -> str:
        """Extract a brace-delimited body starting from a position in source."""
        depth = 0
        body_start = None
        for i in range(start_after, len(source)):
            if source[i] == "{":
                if depth == 0:
                    body_start = i
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0 and body_start is not None:
                    return source[body_start:i + 1]
        return ""

    @staticmethod
    def _count_complexity(body: str) -> int:
        """Count branching keywords in a method body for complexity estimate."""
        if not body:
            return 1

        # Each keyword adds one to the base complexity of 1
        # Each keyword represents one decision point. \bif\b already matches
        # the "if" inside "else if", so we don't list "else if" separately.
        keywords = [
            r"\bif\b", r"\bfor\b", r"\bforeach\b",
            r"\bwhile\b", r"\bcase\b", r"\bcatch\b", r"\?\?",
            r"&&", r"\|\|", r"\?(?!=)",  # ternary ? but not ??
        ]

        complexity = 1
        for kw in keywords:
            complexity += len(re.findall(kw, body))
        return complexity

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
