"""Tests for raw data export (JSON and CSV)."""

from __future__ import annotations

import csv
import json
import math

import pytest

from claude_benchmark.reporting.models import (
    BenchmarkResults,
    ProfileResult,
    ReportMetadata,
    RunResult,
    TaskResult,
)
from claude_benchmark.reporting.exporter import export_csv, export_json, export_raw_data


@pytest.fixture
def sample_results() -> BenchmarkResults:
    """Create sample BenchmarkResults with 2 profiles, 2 tasks, 3 runs each."""
    profiles: dict[str, ProfileResult] = {}

    for profile_id, profile_name in [("empty", "Empty Profile"), ("typical", "Typical Profile")]:
        tasks: dict[str, TaskResult] = {}
        for task_id, task_name in [("t1", "Task One"), ("t2", "Task Two")]:
            runs = []
            for i in range(3):
                base = 70.0 if profile_id == "empty" else 80.0
                runs.append(
                    RunResult(
                        profile=profile_id,
                        task=task_id,
                        model="sonnet-4",
                        scores={
                            "correctness": base + i,
                            "style": base + i + 5,
                        },
                        token_count=1000 + i * 100,
                        code_output=f"print('hello {i}')",
                        success=True,
                    )
                )
            tasks[task_id] = TaskResult(
                task_id=task_id,
                task_name=task_name,
                runs=runs,
                mean_scores={"correctness": base + 1, "style": base + 6},
                std_scores={"correctness": 1.0, "style": 1.0},
            )
        profiles[profile_id] = ProfileResult(
            profile_id=profile_id,
            profile_name=profile_name,
            tasks=tasks,
            aggregate_scores={"correctness": 71.0 if profile_id == "empty" else 81.0},
            total_tokens=3300 if profile_id == "empty" else 3600,
        )

    return BenchmarkResults(
        profiles=profiles,
        models=["sonnet-4"],
        tasks=["t1", "t2"],
        metadata=ReportMetadata(
            date="2026-02-26",
            models_tested=["sonnet-4"],
            profile_count=2,
            total_runs=12,
            wall_clock_seconds=120.5,
        ),
    )


class TestExportJson:
    def test_produces_valid_json(self, tmp_path, sample_results):
        json_path = export_json(sample_results, tmp_path)
        assert json_path.exists()
        with open(json_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_json_structure(self, tmp_path, sample_results):
        json_path = export_json(sample_results, tmp_path)
        with open(json_path) as f:
            data = json.load(f)
        assert "profiles" in data
        assert "models" in data
        assert "tasks" in data
        assert "metadata" in data
        assert data["models"] == ["sonnet-4"]
        assert len(data["profiles"]) == 2

    def test_json_filename(self, tmp_path, sample_results):
        json_path = export_json(sample_results, tmp_path)
        assert json_path.name == "benchmark-results.json"

    def test_nan_sanitized(self, tmp_path):
        """NaN and Infinity values are replaced with None in JSON export."""
        results = BenchmarkResults(
            profiles={
                "test": ProfileResult(
                    profile_id="test",
                    profile_name="Test",
                    tasks={
                        "t1": TaskResult(
                            task_id="t1",
                            task_name="Task",
                            runs=[
                                RunResult(
                                    profile="test",
                                    task="t1",
                                    model="sonnet-4",
                                    scores={"quality": float("nan"), "style": float("inf")},
                                )
                            ],
                            mean_scores={"quality": float("nan")},
                            std_scores={},
                        )
                    },
                    aggregate_scores={},
                )
            },
            models=["sonnet-4"],
            tasks=["t1"],
            metadata=ReportMetadata(date="2026-02-26"),
        )
        json_path = export_json(results, tmp_path)
        with open(json_path) as f:
            data = json.load(f)
        # NaN/Inf should be None, not crash json.load
        run_scores = data["profiles"]["test"]["tasks"]["t1"]["runs"][0]["scores"]
        assert run_scores["quality"] is None
        assert run_scores["style"] is None


class TestExportCsv:
    def test_produces_csv_file(self, tmp_path, sample_results):
        csv_path = export_csv(sample_results, tmp_path)
        assert csv_path.exists()

    def test_csv_filename(self, tmp_path, sample_results):
        csv_path = export_csv(sample_results, tmp_path)
        assert csv_path.name == "benchmark-results.csv"

    def test_csv_correct_headers(self, tmp_path, sample_results):
        csv_path = export_csv(sample_results, tmp_path)
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        assert "profile" in fieldnames
        assert "task" in fieldnames
        assert "model" in fieldnames
        assert "success" in fieldnames
        assert "token_count" in fieldnames
        assert "score_correctness" in fieldnames
        assert "score_style" in fieldnames

    def test_csv_row_count(self, tmp_path, sample_results):
        """2 profiles x 2 tasks x 3 runs = 12 rows."""
        csv_path = export_csv(sample_results, tmp_path)
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 12

    def test_csv_empty_results(self, tmp_path):
        results = BenchmarkResults(
            profiles={},
            models=[],
            tasks=[],
            metadata=ReportMetadata(date="2026-02-26"),
        )
        csv_path = export_csv(results, tmp_path)
        assert csv_path.exists()
        content = csv_path.read_text()
        assert content == ""


class TestExportRawData:
    def test_creates_both_files(self, tmp_path, sample_results):
        json_path, csv_path = export_raw_data(sample_results, tmp_path)
        assert json_path.exists()
        assert csv_path.exists()

    def test_returns_correct_paths(self, tmp_path, sample_results):
        json_path, csv_path = export_raw_data(sample_results, tmp_path)
        assert json_path.name == "benchmark-results.json"
        assert csv_path.name == "benchmark-results.csv"

    def test_prints_paths(self, tmp_path, sample_results, capsys):
        export_raw_data(sample_results, tmp_path)
        captured = capsys.readouterr()
        assert "Exported:" in captured.out
        assert "benchmark-results.json" in captured.out
        assert "benchmark-results.csv" in captured.out

    def test_creates_output_dir(self, tmp_path, sample_results):
        nested_dir = tmp_path / "deep" / "nested" / "output"
        assert not nested_dir.exists()
        json_path, csv_path = export_raw_data(sample_results, nested_dir)
        assert nested_dir.exists()
        assert json_path.exists()
        assert csv_path.exists()
