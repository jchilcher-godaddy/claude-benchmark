"""Tests for resume detection and run filtering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from claude_benchmark.execution.resume import (
    detect_completed_runs,
    filter_remaining_runs,
)


@dataclass
class FakeRun:
    """Minimal run-like object with a result_key attribute."""

    result_key: str


class TestDetectCompletedRunsNonExistent:
    """detect_completed_runs returns empty set for non-existent directory."""

    def test_missing_directory(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist"
        result = detect_completed_runs(missing)
        assert result == set()


class TestDetectCompletedRunsFindsValid:
    """detect_completed_runs finds valid run files."""

    def test_finds_success_runs(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "sonnet" / "empty" / "code-gen"
        run_dir.mkdir(parents=True)
        (run_dir / "run-1.json").write_text(json.dumps({"status": "success"}))
        (run_dir / "run-2.json").write_text(json.dumps({"status": "failure"}))

        completed = detect_completed_runs(tmp_path)
        assert "sonnet/empty/code-gen/run-1" in completed
        assert "sonnet/empty/code-gen/run-2" in completed
        assert len(completed) == 2

    def test_finds_nested_runs(self, tmp_path: Path) -> None:
        # Multiple models/profiles/tasks
        for model in ["haiku", "sonnet"]:
            for profile in ["empty", "large"]:
                run_dir = tmp_path / model / profile / "task-1"
                run_dir.mkdir(parents=True)
                (run_dir / "run-1.json").write_text(
                    json.dumps({"status": "success"})
                )

        completed = detect_completed_runs(tmp_path)
        assert len(completed) == 4
        assert "haiku/empty/task-1/run-1" in completed
        assert "sonnet/large/task-1/run-1" in completed


class TestDetectCompletedRunsSkipsCorrupt:
    """detect_completed_runs skips corrupt JSON files."""

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "sonnet" / "empty" / "task-1"
        run_dir.mkdir(parents=True)
        (run_dir / "run-1.json").write_text("not valid json {{{")
        (run_dir / "run-2.json").write_text(json.dumps({"status": "success"}))

        completed = detect_completed_runs(tmp_path)
        assert len(completed) == 1
        assert "sonnet/empty/task-1/run-2" in completed


class TestDetectCompletedRunsSkipsMissingStatus:
    """detect_completed_runs skips files without status field."""

    def test_skips_no_status(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "sonnet" / "empty" / "task-1"
        run_dir.mkdir(parents=True)
        (run_dir / "run-1.json").write_text(json.dumps({"result": "ok"}))
        (run_dir / "run-2.json").write_text(
            json.dumps({"status": "in-progress"})
        )
        (run_dir / "run-3.json").write_text(json.dumps({"status": "success"}))

        completed = detect_completed_runs(tmp_path)
        assert len(completed) == 1
        assert "sonnet/empty/task-1/run-3" in completed


class TestRetryFailures:
    """detect_completed_runs with retry_failures=True excludes failed runs."""

    def test_retry_failures_excludes_failed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "sonnet" / "empty" / "code-gen"
        run_dir.mkdir(parents=True)
        (run_dir / "run-1.json").write_text(json.dumps({"status": "success"}))
        (run_dir / "run-2.json").write_text(json.dumps({"status": "failure"}))

        completed = detect_completed_runs(tmp_path, retry_failures=True)
        assert "sonnet/empty/code-gen/run-1" in completed
        assert "sonnet/empty/code-gen/run-2" not in completed
        assert len(completed) == 1

    def test_retry_failures_deletes_failed_files(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "sonnet" / "empty" / "code-gen"
        run_dir.mkdir(parents=True)
        fail_file = run_dir / "run-2.json"
        fail_file.write_text(json.dumps({"status": "failure"}))

        detect_completed_runs(tmp_path, retry_failures=True)
        assert not fail_file.exists()

    def test_retry_failures_false_includes_failed(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "sonnet" / "empty" / "code-gen"
        run_dir.mkdir(parents=True)
        (run_dir / "run-1.json").write_text(json.dumps({"status": "failure"}))

        completed = detect_completed_runs(tmp_path, retry_failures=False)
        assert "sonnet/empty/code-gen/run-1" in completed


class TestFilterRemainingRuns:
    """filter_remaining_runs removes completed runs from list."""

    def test_removes_completed(self) -> None:
        runs = [
            FakeRun(result_key="sonnet/empty/task-1/run-1"),
            FakeRun(result_key="sonnet/empty/task-1/run-2"),
            FakeRun(result_key="sonnet/empty/task-1/run-3"),
        ]
        completed = {"sonnet/empty/task-1/run-1", "sonnet/empty/task-1/run-3"}

        remaining = filter_remaining_runs(runs, completed)
        assert len(remaining) == 1
        assert remaining[0].result_key == "sonnet/empty/task-1/run-2"

    def test_all_completed(self) -> None:
        runs = [
            FakeRun(result_key="sonnet/empty/task-1/run-1"),
        ]
        completed = {"sonnet/empty/task-1/run-1"}

        remaining = filter_remaining_runs(runs, completed)
        assert len(remaining) == 0

    def test_none_completed(self) -> None:
        runs = [
            FakeRun(result_key="sonnet/empty/task-1/run-1"),
            FakeRun(result_key="sonnet/empty/task-1/run-2"),
        ]
        completed: set[str] = set()

        remaining = filter_remaining_runs(runs, completed)
        assert len(remaining) == 2
