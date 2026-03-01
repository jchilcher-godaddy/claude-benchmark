"""Integration tests for CLI export command."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer.testing

from claude_benchmark.cli.main import app

runner = typer.testing.CliRunner()


def _normalize_output(text: str) -> str:
    """Collapse Rich line-wrapping so long paths can be matched in assertions."""
    import re
    return re.sub(r"\s*\n\s*", "", text)


def _create_results_dir(base: Path) -> Path:
    """Create a valid results directory with manifest.json, run files, and results.json.

    Builds a minimal but complete test fixture with 2 profiles (empty, test),
    1 task (code-gen-01), 1 model (sonnet), and 3 runs per profile/task combo.
    """
    results_dir = base / "results" / "20260226_151821_686"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Write manifest.json
    manifest = {
        "timestamp": "2026-02-26T15:18:21",
        "models": ["sonnet"],
        "profiles": ["empty", "test"],
        "tasks": ["code-gen-01"],
        "runs_per_combination": 3,
        "total_combinations": 2,
        "total_runs": 6,
        "cli_args": {},
    }
    (results_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    # Create run files in storage format
    for profile in ["empty", "test"]:
        for i in range(1, 4):
            run_dir = results_dir / "runs" / "sonnet" / profile / "code-gen-01"
            run_dir.mkdir(parents=True, exist_ok=True)
            run_data = {
                "run_number": i,
                "success": True,
                "usage": {"input_tokens": 1000, "output_tokens": 500},
                "output_files": {"solution.py": "def hello(): pass"},
                "error": None,
            }
            (run_dir / f"run_{i:03d}.json").write_text(
                json.dumps(run_data), encoding="utf-8"
            )

    return results_dir


def test_export_no_results(tmp_path: Path) -> None:
    """Export command should fail with clear error when results dir is invalid."""
    nonexistent = tmp_path / "nonexistent"
    result = runner.invoke(app, ["export", "--results-dir", str(nonexistent)])
    assert result.exit_code != 0
    assert "Error" in result.output or "not found" in result.output.lower()


def test_export_both_formats(tmp_path: Path) -> None:
    """Export command should produce both JSON and CSV by default."""
    results_dir = _create_results_dir(tmp_path)
    result = runner.invoke(
        app,
        ["export", "--results-dir", str(results_dir)],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert (results_dir / "benchmark-results.json").exists()
    assert (results_dir / "benchmark-results.csv").exists()
    # Check absolute paths in output (normalize to handle Rich line-wrapping)
    output = _normalize_output(result.output)
    assert str((results_dir / "benchmark-results.json").resolve()) in output
    assert str((results_dir / "benchmark-results.csv").resolve()) in output
    # Check data summary
    assert "Profiles:" in result.output
    assert "Tasks:" in result.output
    assert "Total runs:" in result.output


def test_export_json_only(tmp_path: Path) -> None:
    """Export --format json should only produce JSON file."""
    results_dir = _create_results_dir(tmp_path)
    # Remove any pre-existing files
    for f in results_dir.glob("benchmark-results.*"):
        f.unlink()
    result = runner.invoke(
        app,
        ["export", "--results-dir", str(results_dir), "--format", "json"],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert (results_dir / "benchmark-results.json").exists()
    # CSV should NOT be created by the export command itself
    assert not (results_dir / "benchmark-results.csv").exists()


def test_export_csv_only(tmp_path: Path) -> None:
    """Export --format csv should only produce CSV file."""
    results_dir = _create_results_dir(tmp_path)
    # Remove any pre-existing files
    for f in results_dir.glob("benchmark-results.*"):
        f.unlink()
    result = runner.invoke(
        app,
        ["export", "--results-dir", str(results_dir), "--format", "csv"],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert (results_dir / "benchmark-results.csv").exists()
    # JSON should NOT be created by the export command itself
    assert not (results_dir / "benchmark-results.json").exists()


def test_export_invalid_format(tmp_path: Path) -> None:
    """Export --format xml should fail with invalid format error."""
    results_dir = _create_results_dir(tmp_path)
    result = runner.invoke(
        app,
        ["export", "--results-dir", str(results_dir), "--format", "xml"],
    )
    assert result.exit_code != 0
    assert "Invalid format" in result.output


def test_export_filter_flags(tmp_path: Path) -> None:
    """Export with --profile filter should export only matching data."""
    results_dir = _create_results_dir(tmp_path)
    result = runner.invoke(
        app,
        [
            "export",
            "--results-dir", str(results_dir),
            "--profile", "empty",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    # Verify data summary shows 1 profile
    assert "Profiles: 1" in result.output
    # Verify the exported JSON contains only the empty profile
    json_path = results_dir / "benchmark-results.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "empty" in data.get("profiles", {})
    assert "test" not in data.get("profiles", {})


def test_export_output_dir(tmp_path: Path) -> None:
    """Export --output-dir should write files to custom directory."""
    results_dir = _create_results_dir(tmp_path)
    custom_dir = tmp_path / "custom_export"
    result = runner.invoke(
        app,
        [
            "export",
            "--results-dir", str(results_dir),
            "--output-dir", str(custom_dir),
        ],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert (custom_dir / "benchmark-results.json").exists()
    assert (custom_dir / "benchmark-results.csv").exists()
    assert str(custom_dir.resolve()) in _normalize_output(result.output)
