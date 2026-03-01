from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from claude_benchmark.results.schema import AggregateResult, BenchmarkManifest, RunResult


def create_results_directory(base_dir: Optional[Path] = None) -> Path:
    if base_dir is None:
        base_dir = Path.cwd() / "results"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    results_dir = base_dir / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    return results_dir


def save_run_result(
    results_dir: Path,
    model: str,
    profile_name: str,
    task_name: str,
    run_number: int,
    result: RunResult,
) -> Path:
    run_dir = results_dir / "runs" / model / profile_name / task_name
    run_dir.mkdir(parents=True, exist_ok=True)

    file_path = run_dir / f"run_{run_number:03d}.json"
    with open(file_path, "w") as f:
        f.write(result.model_dump_json(indent=2))

    return file_path


def save_aggregate(
    results_dir: Path,
    model: str,
    profile_name: str,
    task_name: str,
    aggregate: AggregateResult,
) -> Path:
    agg_dir = results_dir / "aggregates" / model / profile_name
    agg_dir.mkdir(parents=True, exist_ok=True)

    file_path = agg_dir / f"{task_name}.json"
    with open(file_path, "w") as f:
        f.write(aggregate.model_dump_json(indent=2))

    return file_path


def save_manifest(results_dir: Path, manifest: BenchmarkManifest) -> Path:
    file_path = results_dir / "manifest.json"
    with open(file_path, "w") as f:
        f.write(manifest.model_dump_json(indent=2))

    return file_path
