"""Data bridge: transforms execution-format results into reporting BenchmarkResults.

Reads individual per-run JSON files (both storage and parallel formats) plus
manifest.json, and assembles a BenchmarkResults model suitable for reporting,
export, and regression detection.

Two execution result formats are supported:

1. **Storage format** (from results/storage.py):
   ``runs/{model}/{profile}/{task}/run_{NNN}.json`` matching results.schema.RunResult.

2. **Parallel format** (from execution/parallel.py):
   ``{model}/{profile}/{task}/run-{N}.json`` matching RunResult.to_dict().
"""

from __future__ import annotations

import json
import logging
import statistics
import tomllib
from collections import defaultdict
from pathlib import Path

from claude_benchmark.reporting.models import (
    BenchmarkResults,
    ProfileResult,
    ReportMetadata,
    RunResult as ReportRunResult,
    TaskResult,
)

logger = logging.getLogger(__name__)


def load_results_dir(results_dir: Path) -> BenchmarkResults:
    """Walk results directory and assemble BenchmarkResults.

    Reads manifest.json for metadata (if present), then walks per-run JSON
    files to build the full reporting data structure.  Handles both storage
    format (``run_NNN.json``) and parallel format (``run-N.json``).

    Args:
        results_dir: Path to a results directory.

    Returns:
        Populated BenchmarkResults ready for reporting.

    Raises:
        FileNotFoundError: If *results_dir* does not exist or is not a directory.
    """
    results_dir = Path(results_dir)
    if not results_dir.exists() or not results_dir.is_dir():
        raise FileNotFoundError(
            f"Results directory not found: {results_dir}. "
            "Run `claude-benchmark run` first."
        )

    # 1. Read manifest for metadata (optional)
    manifest: dict = {}
    manifest_path = results_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read manifest.json: %s", exc)

    # 2. Discover all run files (both naming conventions)
    storage_files = list(results_dir.rglob("run_*.json"))
    parallel_files = list(results_dir.rglob("run-*.json"))
    run_files = storage_files + parallel_files

    if not run_files:
        logger.warning("No run result files found in %s", results_dir)
        return BenchmarkResults(
            profiles={},
            models=manifest.get("models", []),
            tasks=manifest.get("tasks", []),
            metadata=_build_metadata(manifest, total_runs=0),
        )

    # 3. Parse each run file
    parsed_runs: list[ReportRunResult] = []
    for path in run_files:
        data = _load_run_file(path)
        if data is None:
            continue

        run = _parse_run(data, path)
        if run is not None:
            parsed_runs.append(run)

    if not parsed_runs:
        logger.warning("All run files were corrupt or unparseable in %s", results_dir)
        return BenchmarkResults(
            profiles={},
            models=manifest.get("models", []),
            tasks=manifest.get("tasks", []),
            metadata=_build_metadata(manifest, total_runs=0),
        )

    # 4. Group runs by (profile, task)
    grouped: dict[tuple[str, str], list[ReportRunResult]] = defaultdict(list)
    for run in parsed_runs:
        grouped[(run.profile, run.task)].append(run)

    # 5. Build TaskResult for each group
    task_results_by_profile: dict[str, dict[str, TaskResult]] = defaultdict(dict)
    for (profile, task), runs in grouped.items():
        mean_scores = _compute_mean_scores(runs)
        std_scores = _compute_std_scores(runs)
        task_results_by_profile[profile][task] = TaskResult(
            task_id=task,
            task_name=task,
            runs=runs,
            mean_scores=mean_scores,
            std_scores=std_scores,
        )

    # 6. Build ProfileResult for each profile
    profiles: dict[str, ProfileResult] = {}
    for profile_name, tasks_dict in task_results_by_profile.items():
        aggregate_scores = _compute_aggregate_scores(tasks_dict)
        total_tokens = sum(
            run.token_count
            for tr in tasks_dict.values()
            for run in tr.runs
        )
        profiles[profile_name] = ProfileResult(
            profile_id=profile_name,
            profile_name=profile_name,
            tasks=tasks_dict,
            aggregate_scores=aggregate_scores,
            total_tokens=total_tokens,
        )

    # 7. Derive models/tasks lists from parsed data (more reliable than manifest alone)
    all_models = sorted({run.model for run in parsed_runs})
    all_tasks = sorted({run.task for run in parsed_runs})

    # Union of manifest and discovered: never hide data that exists on disk
    manifest_models = manifest.get("models") or []
    models_list = sorted(set(manifest_models) | set(all_models))
    manifest_tasks = manifest.get("tasks") or []
    tasks_list = sorted(set(manifest_tasks) | set(all_tasks))

    return BenchmarkResults(
        profiles=profiles,
        models=models_list,
        tasks=tasks_list,
        metadata=_build_metadata(manifest, total_runs=len(parsed_runs), models=models_list),
    )


def find_latest_results(base_dir: Path | None = None) -> Path | None:
    """Find the most recent results directory by lexicographic sort.

    Scans *base_dir* for subdirectories containing ``manifest.json`` and
    returns the one whose name sorts last (both ``YYYYMMDD_HHMMSS_fff``
    and ``YYYYMMDD-HHMMSS`` formats sort correctly).

    Args:
        base_dir: Directory containing results subdirectories.
            Defaults to ``Path("results")``.

    Returns:
        Path to the most recent results directory, or ``None`` if none found.
    """
    if base_dir is None:
        base_dir = Path("results")

    if not base_dir.is_dir():
        return None

    candidates = sorted(
        [
            d
            for d in base_dir.iterdir()
            if d.is_dir() and (d / "manifest.json").exists()
        ],
        key=lambda d: d.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def filter_results(
    results: BenchmarkResults,
    task_names: list[str] | None = None,
    profile_names: list[str] | None = None,
    model_names: list[str] | None = None,
) -> BenchmarkResults:
    """Return a new BenchmarkResults filtered by task, profile, and/or model.

    Does NOT mutate the input (all models are frozen).  Recomputes
    aggregate scores and token totals for filtered data.

    Args:
        results: Source benchmark results.
        task_names: Keep only these tasks (None = keep all).
        profile_names: Keep only these profiles (None = keep all).
        model_names: Keep only runs from these models (None = keep all).

    Returns:
        New BenchmarkResults containing only matching data.
    """
    profiles = dict(results.profiles)

    # Filter profiles
    if profile_names is not None:
        profiles = {k: v for k, v in profiles.items() if k in profile_names}

    # Filter tasks within each profile
    if task_names is not None:
        new_profiles: dict[str, ProfileResult] = {}
        for pid, pr in profiles.items():
            filtered_tasks = {
                tid: tr for tid, tr in pr.tasks.items() if tid in task_names
            }
            aggregate_scores = _compute_aggregate_scores(filtered_tasks)
            total_tokens = sum(
                run.token_count
                for tr in filtered_tasks.values()
                for run in tr.runs
            )
            new_profiles[pid] = ProfileResult(
                profile_id=pr.profile_id,
                profile_name=pr.profile_name,
                tasks=filtered_tasks,
                aggregate_scores=aggregate_scores,
                total_tokens=total_tokens,
            )
        profiles = new_profiles

    # Filter model-specific runs within tasks
    if model_names is not None:
        new_profiles2: dict[str, ProfileResult] = {}
        for pid, pr in profiles.items():
            new_tasks: dict[str, TaskResult] = {}
            for tid, tr in pr.tasks.items():
                filtered_runs = [r for r in tr.runs if r.model in model_names]
                mean_scores = _compute_mean_scores(filtered_runs)
                std_scores = _compute_std_scores(filtered_runs)
                new_tasks[tid] = TaskResult(
                    task_id=tr.task_id,
                    task_name=tr.task_name,
                    runs=filtered_runs,
                    mean_scores=mean_scores,
                    std_scores=std_scores,
                )
            aggregate_scores = _compute_aggregate_scores(new_tasks)
            total_tokens = sum(
                run.token_count
                for tr in new_tasks.values()
                for run in tr.runs
            )
            new_profiles2[pid] = ProfileResult(
                profile_id=pr.profile_id,
                profile_name=pr.profile_name,
                tasks=new_tasks,
                aggregate_scores=aggregate_scores,
                total_tokens=total_tokens,
            )
        profiles = new_profiles2

    # Rebuild metadata
    all_tasks = sorted({tid for pr in profiles.values() for tid in pr.tasks})
    all_models = sorted(
        {
            r.model
            for pr in profiles.values()
            for tr in pr.tasks.values()
            for r in tr.runs
        }
    )
    total_runs = sum(
        len(tr.runs)
        for pr in profiles.values()
        for tr in pr.tasks.values()
    )

    return BenchmarkResults(
        profiles=profiles,
        models=all_models,
        tasks=all_tasks,
        metadata=ReportMetadata(
            date=results.metadata.date,
            models_tested=all_models,
            profile_count=len(profiles),
            total_runs=total_runs,
            wall_clock_seconds=results.metadata.wall_clock_seconds,
        ),
    )


def load_task_descriptions(tasks_dir: Path) -> dict[str, str]:
    """Load task descriptions from task.toml files for report display.

    Scans subdirectories of *tasks_dir* for ``task.toml`` files and extracts
    the ``name`` and ``description`` fields.  Uses lightweight TOML parsing
    (not full TaskDefinition validation) so tasks with incomplete files are
    silently skipped.

    Args:
        tasks_dir: Directory containing task subdirectories (e.g. ``tasks/builtin/``).

    Returns:
        Dict mapping task name to description, e.g.
        ``{"bug-fix-01": "Fix off-by-one error in binary search"}``.
    """
    descriptions: dict[str, str] = {}
    if not tasks_dir.is_dir():
        return descriptions

    for task_toml in tasks_dir.rglob("task.toml"):
        try:
            data = tomllib.loads(task_toml.read_text(encoding="utf-8"))
            name = data.get("name")
            description = data.get("description")
            if name and description:
                descriptions[name] = description
        except Exception:
            logger.debug("Skipping unreadable task.toml: %s", task_toml)
            continue

    return descriptions


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_run_file(path: Path) -> dict | None:
    """Load a single run JSON file, returning None on failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("Skipping non-dict result file: %s", path)
            return None
        return data
    except (json.JSONDecodeError, OSError):
        logger.warning("Skipping corrupt result file: %s", path)
        return None


def _parse_run(data: dict, path: Path) -> ReportRunResult | None:
    """Determine format and parse a run dict into a ReportRunResult."""
    if "status" in data:
        return _parse_parallel_run(data, path)
    if "run_number" in data:
        return _parse_storage_run(data, path)
    logger.warning("Skipping unrecognised run format: %s", path)
    return None


def _extract_flat_scores(scores_raw: dict | None) -> dict[str, float]:
    """Extract flat {dimension: float} scores from either nested or flat format.

    The scoring pipeline produces a nested dict like::

        {"static": {...}, "llm": {...}, "composite": {"composite": 72.5, ...}, ...}

    but the report layer expects a flat ``{dimension: float}`` dict.  This
    helper normalises both formats.
    """
    if not scores_raw:
        return {}

    # Nested format from scoring pipeline (has "composite" key as dict)
    if isinstance(scores_raw.get("composite"), dict):
        flat: dict[str, float] = {}
        composite = scores_raw["composite"]
        if "composite" in composite:
            flat["composite"] = float(composite["composite"])

        static = scores_raw.get("static")
        if isinstance(static, dict):
            for key in ("test_pass_rate", "lint_score", "complexity_score"):
                if key in static:
                    flat[key] = float(static[key])

        llm = scores_raw.get("llm")
        if isinstance(llm, dict) and "normalized" in llm:
            flat["llm_quality"] = float(llm["normalized"])

        return flat

    # Flat format (already {dim: float})
    result: dict[str, float] = {}
    for k, v in scores_raw.items():
        try:
            result[k] = float(v)
        except (TypeError, ValueError):
            continue
    return result


def _parse_parallel_run(data: dict, path: Path) -> ReportRunResult:
    """Parse a parallel-format run (from execution/parallel.py)."""
    scores = _extract_flat_scores(data.get("scores"))

    code_output = _read_code_output_from_output_dir(data.get("output_dir"))

    return ReportRunResult(
        profile=data.get("profile_name", "unknown"),
        task=data.get("task_name", "unknown"),
        model=data.get("model", "unknown"),
        scores=scores,
        score_details=data.get("scores") or {},
        token_count=data.get("total_tokens", 0) or 0,
        code_output=code_output,
        success=data.get("status") == "success",
        error=data.get("error"),
        output_dir=data.get("output_dir"),
    )


def _parse_storage_run(data: dict, path: Path) -> ReportRunResult:
    """Parse a storage-format run (from results/storage.py).

    Infers profile, task, and model from the file path.
    Convention: ``runs/{model}/{profile}/{task}/run_{NNN}.json``.
    """
    model, profile, task = _infer_from_path(path)

    usage = data.get("usage") or {}
    token_count = (usage.get("input_tokens", 0) or 0) + (
        usage.get("output_tokens", 0) or 0
    )

    code_output = _read_code_output_from_output_files(data.get("output_files"))

    return ReportRunResult(
        profile=profile,
        task=task,
        model=model,
        scores={},  # Storage format has no scores (scoring wired in Phase 7)
        token_count=token_count,
        code_output=code_output,
        success=data.get("success", False),
        error=data.get("error"),
    )


def _infer_from_path(path: Path) -> tuple[str, str, str]:
    """Extract (model, profile, task) from a storage-format file path.

    Looks for ``runs`` in the path parts and takes the next three levels.
    Falls back to ``("unknown", "unknown", "unknown")`` if structure unexpected.
    """
    parts = path.parts
    try:
        idx = parts.index("runs")
        model = parts[idx + 1]
        profile = parts[idx + 2]
        task = parts[idx + 3]
        return model, profile, task
    except (ValueError, IndexError):
        logger.warning(
            "Could not infer model/profile/task from path: %s", path
        )
        return "unknown", "unknown", "unknown"


def _read_code_output_from_output_dir(
    output_dir: str | None,
) -> str:
    """Read code output from a parallel-format output directory."""
    if not output_dir:
        return ""
    output_path = Path(output_dir)
    if not output_path.is_dir():
        return ""
    for py_file in sorted(output_path.glob("*.py")):
        try:
            return py_file.read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


def _read_code_output_from_output_files(
    output_files: dict[str, str] | None,
) -> str:
    """Read code output from storage-format output_files mapping."""
    if not output_files:
        return ""
    for name, content in output_files.items():
        if name.endswith(".py"):
            return content
    # Return first value if no .py files
    for content in output_files.values():
        return content
    return ""


def _compute_mean_scores(
    runs: list[ReportRunResult],
) -> dict[str, float]:
    """Compute mean score per dimension across runs."""
    if not runs:
        return {}
    dim_values: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        for dim, val in run.scores.items():
            dim_values[dim].append(val)
    return {dim: statistics.mean(vals) for dim, vals in dim_values.items()}


def _compute_std_scores(
    runs: list[ReportRunResult],
) -> dict[str, float]:
    """Compute stdev per dimension across runs (0.0 if < 2 runs)."""
    if not runs:
        return {}
    dim_values: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        for dim, val in run.scores.items():
            dim_values[dim].append(val)
    result: dict[str, float] = {}
    for dim, vals in dim_values.items():
        if len(vals) >= 2:
            result[dim] = statistics.stdev(vals)
        else:
            result[dim] = 0.0
    return result


def _compute_aggregate_scores(
    tasks: dict[str, TaskResult],
) -> dict[str, float]:
    """Compute aggregate scores: mean of mean_scores across all tasks per dimension."""
    if not tasks:
        return {}
    dim_values: dict[str, list[float]] = defaultdict(list)
    for tr in tasks.values():
        for dim, val in tr.mean_scores.items():
            dim_values[dim].append(val)
    return {dim: statistics.mean(vals) for dim, vals in dim_values.items()}


def _build_metadata(
    manifest: dict,
    total_runs: int,
    models: list[str] | None = None,
) -> ReportMetadata:
    """Build ReportMetadata from manifest dict and actual run count.

    Args:
        manifest: Parsed manifest.json dict.
        total_runs: Number of parsed run files.
        models: Resolved models list (union of manifest + discovered).
            Falls back to manifest ``models`` if not provided.
    """
    return ReportMetadata(
        date=str(manifest.get("timestamp", "")),
        models_tested=models if models is not None else manifest.get("models", []),
        profile_count=len(manifest.get("profiles", [])),
        total_runs=total_runs,
        wall_clock_seconds=0.0,
    )
