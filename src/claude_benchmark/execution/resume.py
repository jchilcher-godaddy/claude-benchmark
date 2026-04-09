"""Resume detection for benchmark execution.

Scans a results directory for completed run files and filters out
already-completed runs from the execution queue.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_benchmark.execution.parallel import BenchmarkRun


def detect_completed_runs(
    results_dir: Path,
    *,
    retry_failures: bool = False,
) -> set[str]:
    """Scan results directory for completed runs.

    Returns a set of run keys like 'sonnet/empty-profile/code-gen-01/run-1'.
    Files that fail JSON parsing or are missing a status field are skipped
    (treated as incomplete).

    Args:
        results_dir: Root results directory to scan.
        retry_failures: When True, only treat ``"success"`` as completed.
            Failed run files are deleted so they can be re-executed cleanly.
    """
    completed: set[str] = set()
    if not results_dir.exists():
        return completed

    valid_statuses = {"success"} if retry_failures else {"success", "failure"}

    for run_file in results_dir.rglob("run-*.json"):
        try:
            data = json.loads(run_file.read_text())
            status = data.get("status")
            if status in valid_statuses:
                rel = run_file.relative_to(results_dir)
                completed.add(str(rel.with_suffix("")))
            elif retry_failures and status == "failure":
                # Remove stale failure file so a fresh result can be written
                run_file.unlink(missing_ok=True)
        except (json.JSONDecodeError, KeyError, OSError):
            continue  # Corrupted or unreadable file, treat as incomplete

    return completed


def filter_remaining_runs(
    all_runs: list[BenchmarkRun],
    completed: set[str],
) -> list[BenchmarkRun]:
    """Remove already-completed runs from the queue.

    Compares each run's result_key against the set of completed keys.
    """
    return [r for r in all_runs if r.result_key not in completed]
