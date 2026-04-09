"""Tests for catalog store operations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_benchmark.catalog.models import Catalog, CatalogEntry
from claude_benchmark.catalog.store import (
    default_catalog_path,
    find_entries,
    intake_run,
    load_catalog,
    next_run_id,
    remove_entry,
    save_catalog,
    tag_entry,
    validate_results_dir,
)


def test_default_catalog_path():
    """Test that default_catalog_path returns expected path."""
    path = default_catalog_path()
    assert path == Path("results/catalog.json")


def test_load_catalog_missing_file(tmp_path):
    """Test loading catalog when file doesn't exist returns empty Catalog."""
    catalog_path = tmp_path / "catalog.json"
    catalog = load_catalog(catalog_path)
    assert isinstance(catalog, Catalog)
    assert catalog.version == 1
    assert len(catalog.entries) == 0


def test_save_and_load_catalog(tmp_path):
    """Test round-trip save and load of catalog."""
    catalog = Catalog(
        version=1,
        entries=[
            CatalogEntry(
                run_id="run-001",
                name="test run",
                timestamp="2024-01-01T00:00:00Z",
                results_path="/path/to/results",
                tags=["test"],
                models=["model1"],
                profiles=["profile1"],
                tasks=["task1"],
                variants=[],
                total_runs=5,
                experiment_name=None,
                intake_timestamp="2024-01-01T01:00:00Z",
            )
        ],
    )

    catalog_path = tmp_path / "catalog.json"
    save_catalog(catalog, catalog_path)

    assert catalog_path.exists()

    loaded = load_catalog(catalog_path)
    assert loaded.version == catalog.version
    assert len(loaded.entries) == 1
    assert loaded.entries[0].run_id == "run-001"
    assert loaded.entries[0].name == "test run"
    assert loaded.entries[0].tags == ["test"]


def test_next_run_id_empty():
    """Test next_run_id with empty catalog returns run-001."""
    catalog = Catalog()
    assert next_run_id(catalog) == "run-001"


def test_next_run_id_increments():
    """Test next_run_id increments from highest existing."""
    catalog = Catalog(
        entries=[
            CatalogEntry(
                run_id="run-001",
                name="first",
                timestamp="",
                results_path="/path/1",
                total_runs=1,
            ),
            CatalogEntry(
                run_id="run-005",
                name="fifth",
                timestamp="",
                results_path="/path/5",
                total_runs=1,
            ),
            CatalogEntry(
                run_id="run-003",
                name="third",
                timestamp="",
                results_path="/path/3",
                total_runs=1,
            ),
        ]
    )
    assert next_run_id(catalog) == "run-006"


def test_validate_results_dir_missing(tmp_path):
    """Test validate_results_dir returns False for missing directory."""
    missing_dir = tmp_path / "missing"
    is_valid, error = validate_results_dir(missing_dir)
    assert not is_valid
    assert "does not exist" in error


def test_validate_results_dir_no_manifest(tmp_path):
    """Test validate_results_dir returns False when manifest.json missing."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    is_valid, error = validate_results_dir(results_dir)
    assert not is_valid
    assert "manifest.json" in error


def test_validate_results_dir_no_runs(tmp_path):
    """Test validate_results_dir returns False when no run files exist."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    manifest = {"timestamp": "2024-01-01T00:00:00Z", "models": [], "profiles": [], "tasks": []}
    (results_dir / "manifest.json").write_text(json.dumps(manifest))

    is_valid, error = validate_results_dir(results_dir)
    assert not is_valid
    assert "No run result files" in error


def test_validate_results_dir_valid(tmp_path):
    """Test validate_results_dir returns True for valid directory."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    manifest = {"timestamp": "2024-01-01T00:00:00Z", "models": [], "profiles": [], "tasks": []}
    (results_dir / "manifest.json").write_text(json.dumps(manifest))

    # Create a run file
    run_file = results_dir / "run-1.json"
    run_file.write_text(json.dumps({"status": "success"}))

    is_valid, error = validate_results_dir(results_dir)
    assert is_valid
    assert error == ""


def test_intake_run(tmp_path):
    """Test intake_run creates correct CatalogEntry."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    manifest = {
        "timestamp": "2024-01-01T00:00:00Z",
        "models": ["model1", "model2"],
        "profiles": ["profile1"],
        "tasks": ["task1", "task2"],
        "variants": [],
    }
    (results_dir / "manifest.json").write_text(json.dumps(manifest))

    # Create run files
    (results_dir / "run-1.json").write_text(json.dumps({"status": "success"}))
    (results_dir / "run-2.json").write_text(json.dumps({"status": "success"}))

    catalog = Catalog()
    entry = intake_run(catalog, results_dir, name="Test Run", tags=["experiment"])

    assert entry.run_id == "run-001"
    assert entry.name == "Test Run"
    assert entry.timestamp == "2024-01-01T00:00:00Z"
    assert Path(entry.results_path) == results_dir.resolve()
    assert entry.tags == ["experiment"]
    assert entry.models == ["model1", "model2"]
    assert entry.profiles == ["profile1"]
    assert entry.tasks == ["task1", "task2"]
    assert entry.total_runs == 2
    assert entry.intake_timestamp != ""

    assert len(catalog.entries) == 1
    assert catalog.entries[0] == entry


def test_intake_run_duplicate_raises(tmp_path):
    """Test intake_run raises ValueError on duplicate path."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    manifest = {"timestamp": "2024-01-01T00:00:00Z", "models": [], "profiles": [], "tasks": []}
    (results_dir / "manifest.json").write_text(json.dumps(manifest))
    (results_dir / "run-1.json").write_text(json.dumps({"status": "success"}))

    catalog = Catalog()
    intake_run(catalog, results_dir)

    with pytest.raises(ValueError, match="already in catalog"):
        intake_run(catalog, results_dir)


def test_intake_run_force(tmp_path):
    """Test intake_run with force=True replaces existing entry."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    manifest = {"timestamp": "2024-01-01T00:00:00Z", "models": [], "profiles": [], "tasks": []}
    (results_dir / "manifest.json").write_text(json.dumps(manifest))
    (results_dir / "run-1.json").write_text(json.dumps({"status": "success"}))

    catalog = Catalog()
    entry1 = intake_run(catalog, results_dir, name="First")
    assert len(catalog.entries) == 1

    entry2 = intake_run(catalog, results_dir, name="Second", force=True)
    assert len(catalog.entries) == 1
    assert catalog.entries[0].name == "Second"
    # Old entry removed, new entry added with regenerated ID
    assert entry2.run_id == "run-001"  # Regenerated after removal


def test_find_entries_by_id():
    """Test finding entries by run_id."""
    catalog = Catalog(
        entries=[
            CatalogEntry(run_id="run-001", name="first", timestamp="", results_path="/path/1", total_runs=1),
            CatalogEntry(run_id="run-002", name="second", timestamp="", results_path="/path/2", total_runs=1),
            CatalogEntry(run_id="run-003", name="third", timestamp="", results_path="/path/3", total_runs=1),
        ]
    )

    results = find_entries(catalog, run_ids=["run-001", "run-003"])
    assert len(results) == 2
    assert {e.run_id for e in results} == {"run-001", "run-003"}


def test_find_entries_by_tag():
    """Test finding entries by tag."""
    catalog = Catalog(
        entries=[
            CatalogEntry(run_id="run-001", name="first", timestamp="", results_path="/path/1", tags=["exp1"], total_runs=1),
            CatalogEntry(run_id="run-002", name="second", timestamp="", results_path="/path/2", tags=["exp2"], total_runs=1),
            CatalogEntry(run_id="run-003", name="third", timestamp="", results_path="/path/3", tags=["exp1", "baseline"], total_runs=1),
        ]
    )

    results = find_entries(catalog, tags=["exp1"])
    assert len(results) == 2
    assert {e.run_id for e in results} == {"run-001", "run-003"}


def test_find_entries_by_name():
    """Test finding entries by name substring."""
    catalog = Catalog(
        entries=[
            CatalogEntry(run_id="run-001", name="baseline experiment", timestamp="", results_path="/path/1", total_runs=1),
            CatalogEntry(run_id="run-002", name="test run", timestamp="", results_path="/path/2", total_runs=1),
            CatalogEntry(run_id="run-003", name="baseline control", timestamp="", results_path="/path/3", total_runs=1),
        ]
    )

    results = find_entries(catalog, names=["baseline"])
    assert len(results) == 2
    assert {e.run_id for e in results} == {"run-001", "run-003"}


def test_remove_entry():
    """Test removing an entry from catalog."""
    catalog = Catalog(
        entries=[
            CatalogEntry(run_id="run-001", name="first", timestamp="", results_path="/path/1", total_runs=1),
            CatalogEntry(run_id="run-002", name="second", timestamp="", results_path="/path/2", total_runs=1),
        ]
    )

    removed = remove_entry(catalog, "run-001")
    assert removed.run_id == "run-001"
    assert len(catalog.entries) == 1
    assert catalog.entries[0].run_id == "run-002"


def test_remove_entry_not_found():
    """Test remove_entry raises KeyError when ID not found."""
    catalog = Catalog()

    with pytest.raises(KeyError, match="not found"):
        remove_entry(catalog, "run-999")


def test_tag_entry():
    """Test adding tags to an entry."""
    catalog = Catalog(
        entries=[
            CatalogEntry(run_id="run-001", name="first", timestamp="", results_path="/path/1", tags=["initial"], total_runs=1),
        ]
    )

    updated = tag_entry(catalog, "run-001", ["new", "tags"])
    assert set(updated.tags) == {"initial", "new", "tags"}
    assert set(catalog.entries[0].tags) == {"initial", "new", "tags"}


def test_tag_entry_not_found():
    """Test tag_entry raises KeyError when ID not found."""
    catalog = Catalog()

    with pytest.raises(KeyError, match="not found"):
        tag_entry(catalog, "run-999", ["tag"])
