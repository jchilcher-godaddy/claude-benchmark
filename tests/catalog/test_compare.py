"""Tests for catalog comparison logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_benchmark.catalog.compare import (
    compare_entries,
    extract_run_keys,
    find_overlapping_keys,
)
from claude_benchmark.catalog.models import CatalogEntry, ComparisonKey
from claude_benchmark.reporting.loader import load_results_dir
from claude_benchmark.reporting.models import (
    BenchmarkResults,
    ProfileResult,
    ReportMetadata,
    RunResult,
    TaskResult,
)


def test_extract_run_keys():
    """Test extracting comparison keys from BenchmarkResults."""
    results = BenchmarkResults(
        profiles={
            "profile1": ProfileResult(
                profile_id="profile1",
                profile_name="profile1",
                tasks={
                    "task1": TaskResult(
                        task_id="task1",
                        task_name="task1",
                        runs=[
                            RunResult(
                                profile="profile1",
                                task="task1",
                                model="model1",
                                scores={"composite": 85.0},
                            ),
                            RunResult(
                                profile="profile1",
                                task="task1",
                                model="model1",
                                scores={"composite": 87.0},
                            ),
                        ],
                        mean_scores={"composite": 86.0},
                        std_scores={"composite": 1.0},
                    ),
                },
                aggregate_scores={"composite": 86.0},
            ),
        },
        models=["model1"],
        tasks=["task1"],
        metadata=ReportMetadata(date="2024-01-01"),
    )

    key_map = extract_run_keys(results)

    expected_key = ComparisonKey(model="model1", profile="profile1", task="task1")
    assert expected_key in key_map
    assert len(key_map[expected_key]) == 2
    assert key_map[expected_key][0].scores["composite"] == 85.0
    assert key_map[expected_key][1].scores["composite"] == 87.0


def test_find_overlapping_keys():
    """Test finding overlapping keys between key maps."""
    key1 = ComparisonKey(model="model1", profile="profile1", task="task1")
    key2 = ComparisonKey(model="model1", profile="profile1", task="task2")
    key3 = ComparisonKey(model="model2", profile="profile1", task="task1")

    key_map_a = {key1: [], key2: []}
    key_map_b = {key1: [], key3: []}
    key_map_c = {key2: [], key3: []}

    overlaps = find_overlapping_keys([key_map_a, key_map_b, key_map_c])

    # key1 appears in a and b (2 maps)
    # key2 appears in a and c (2 maps)
    # key3 appears in b and c (2 maps)
    assert len(overlaps) == 3
    assert key1 in overlaps
    assert key2 in overlaps
    assert key3 in overlaps


def test_compare_entries_basic(tmp_path):
    """Test basic comparison between two result sets."""
    # Create first results directory
    results_dir_a = tmp_path / "results_a"
    results_dir_a.mkdir()

    manifest_a = {
        "timestamp": "2024-01-01T00:00:00Z",
        "models": ["model1"],
        "profiles": ["profile1"],
        "tasks": ["task1"],
    }
    (results_dir_a / "manifest.json").write_text(json.dumps(manifest_a))

    # Create run files for results_a with scores
    run_a1 = {
        "status": "success",
        "profile_name": "profile1",
        "task_name": "task1",
        "model": "model1",
        "scores": {"composite": 80.0, "llm_quality": 75.0},
        "total_tokens": 100,
    }
    run_a2 = {
        "status": "success",
        "profile_name": "profile1",
        "task_name": "task1",
        "model": "model1",
        "scores": {"composite": 82.0, "llm_quality": 77.0},
        "total_tokens": 110,
    }
    (results_dir_a / "run-1.json").write_text(json.dumps(run_a1))
    (results_dir_a / "run-2.json").write_text(json.dumps(run_a2))

    # Create second results directory
    results_dir_b = tmp_path / "results_b"
    results_dir_b.mkdir()

    manifest_b = {
        "timestamp": "2024-01-02T00:00:00Z",
        "models": ["model1"],
        "profiles": ["profile1"],
        "tasks": ["task1"],
    }
    (results_dir_b / "manifest.json").write_text(json.dumps(manifest_b))

    # Create run files for results_b with different scores
    run_b1 = {
        "status": "success",
        "profile_name": "profile1",
        "task_name": "task1",
        "model": "model1",
        "scores": {"composite": 90.0, "llm_quality": 85.0},
        "total_tokens": 120,
    }
    run_b2 = {
        "status": "success",
        "profile_name": "profile1",
        "task_name": "task1",
        "model": "model1",
        "scores": {"composite": 92.0, "llm_quality": 87.0},
        "total_tokens": 115,
    }
    (results_dir_b / "run-1.json").write_text(json.dumps(run_b1))
    (results_dir_b / "run-2.json").write_text(json.dumps(run_b2))

    # Create catalog entries
    entry_a = CatalogEntry(
        run_id="run-001",
        name="Baseline",
        timestamp="2024-01-01T00:00:00Z",
        results_path=str(results_dir_a.resolve()),
        tags=["baseline"],
        models=["model1"],
        profiles=["profile1"],
        tasks=["task1"],
        variants=[],
        total_runs=2,
    )

    entry_b = CatalogEntry(
        run_id="run-002",
        name="Experiment",
        timestamp="2024-01-02T00:00:00Z",
        results_path=str(results_dir_b.resolve()),
        tags=["experiment"],
        models=["model1"],
        profiles=["profile1"],
        tasks=["task1"],
        variants=[],
        total_runs=2,
    )

    # Compare entries
    report = compare_entries([entry_a, entry_b])

    # Verify report structure
    assert len(report.entries) == 2
    assert len(report.overlapping_keys) == 1
    assert report.overlapping_keys[0] == {
        "model": "model1",
        "profile": "profile1",
        "task": "task1",
    }

    # Should have comparisons for both dimensions (composite and llm_quality)
    assert len(report.comparisons) == 2

    # Check composite comparison
    composite_comp = next(
        (c for c in report.comparisons if c.dimension == "composite"), None
    )
    assert composite_comp is not None
    assert composite_comp.run_a_id == "run-001"
    assert composite_comp.run_b_id == "run-002"
    assert composite_comp.run_a_mean == 81.0  # (80 + 82) / 2
    assert composite_comp.run_b_mean == 91.0  # (90 + 92) / 2
    assert composite_comp.run_a_n == 2
    assert composite_comp.run_b_n == 2
    assert composite_comp.delta_pct > 0  # B is higher than A
    assert composite_comp.test_used in ["mann-whitney-u", "welch-t-test"]

    # Check llm_quality comparison
    llm_comp = next(
        (c for c in report.comparisons if c.dimension == "llm_quality"), None
    )
    assert llm_comp is not None
    assert llm_comp.run_a_mean == 76.0  # (75 + 77) / 2
    assert llm_comp.run_b_mean == 86.0  # (85 + 87) / 2


def test_compare_entries_with_unique_keys(tmp_path):
    """Test comparison tracks unique keys per entry."""
    # Create two results directories with partially overlapping keys
    results_dir_a = tmp_path / "results_a"
    results_dir_a.mkdir()

    manifest_a = {
        "timestamp": "2024-01-01T00:00:00Z",
        "models": ["model1"],
        "profiles": ["profile1"],
        "tasks": ["task1", "task2"],
    }
    (results_dir_a / "manifest.json").write_text(json.dumps(manifest_a))

    # Task1 in A
    (results_dir_a / "run-1.json").write_text(
        json.dumps({
            "status": "success",
            "profile_name": "profile1",
            "task_name": "task1",
            "model": "model1",
            "scores": {"composite": 80.0},
            "total_tokens": 100,
        })
    )
    (results_dir_a / "run-2.json").write_text(
        json.dumps({
            "status": "success",
            "profile_name": "profile1",
            "task_name": "task1",
            "model": "model1",
            "scores": {"composite": 82.0},
            "total_tokens": 110,
        })
    )

    # Task2 in A (unique to A)
    (results_dir_a / "run-3.json").write_text(
        json.dumps({
            "status": "success",
            "profile_name": "profile1",
            "task_name": "task2",
            "model": "model1",
            "scores": {"composite": 70.0},
            "total_tokens": 90,
        })
    )
    (results_dir_a / "run-4.json").write_text(
        json.dumps({
            "status": "success",
            "profile_name": "profile1",
            "task_name": "task2",
            "model": "model1",
            "scores": {"composite": 72.0},
            "total_tokens": 95,
        })
    )

    results_dir_b = tmp_path / "results_b"
    results_dir_b.mkdir()

    manifest_b = {
        "timestamp": "2024-01-02T00:00:00Z",
        "models": ["model1"],
        "profiles": ["profile1"],
        "tasks": ["task1"],
    }
    (results_dir_b / "manifest.json").write_text(json.dumps(manifest_b))

    # Task1 in B (overlaps with A)
    (results_dir_b / "run-1.json").write_text(
        json.dumps({
            "status": "success",
            "profile_name": "profile1",
            "task_name": "task1",
            "model": "model1",
            "scores": {"composite": 90.0},
            "total_tokens": 120,
        })
    )
    (results_dir_b / "run-2.json").write_text(
        json.dumps({
            "status": "success",
            "profile_name": "profile1",
            "task_name": "task1",
            "model": "model1",
            "scores": {"composite": 92.0},
            "total_tokens": 115,
        })
    )

    entry_a = CatalogEntry(
        run_id="run-001",
        name="Run A",
        timestamp="2024-01-01T00:00:00Z",
        results_path=str(results_dir_a.resolve()),
        tags=[],
        models=["model1"],
        profiles=["profile1"],
        tasks=["task1", "task2"],
        variants=[],
        total_runs=4,
    )

    entry_b = CatalogEntry(
        run_id="run-002",
        name="Run B",
        timestamp="2024-01-02T00:00:00Z",
        results_path=str(results_dir_b.resolve()),
        tags=[],
        models=["model1"],
        profiles=["profile1"],
        tasks=["task1"],
        variants=[],
        total_runs=2,
    )

    report = compare_entries([entry_a, entry_b])

    # Verify overlapping keys
    assert len(report.overlapping_keys) == 1
    assert report.overlapping_keys[0] == {
        "model": "model1",
        "profile": "profile1",
        "task": "task1",
    }

    # Verify unique keys
    assert "run-001" in report.unique_keys
    assert "run-002" in report.unique_keys

    # A has task2 unique
    unique_a = report.unique_keys["run-001"]
    assert len(unique_a) == 1
    assert unique_a[0] == {"model": "model1", "profile": "profile1", "task": "task2"}

    # B has no unique keys
    unique_b = report.unique_keys["run-002"]
    assert len(unique_b) == 0
