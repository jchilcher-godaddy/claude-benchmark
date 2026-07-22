"""Load benchmark runs from results directories into a tidy DataFrame."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

TIDY_COLUMNS: tuple[str, ...] = (
    "experiment",
    "model",
    "profile",
    "task",
    "variant",
    "run_number",
    "composite",
    "test_pass_rate",
    "lint_score",
    "complexity_score",
    "llm_quality",
    "input_tokens",
    "output_tokens",
    "cost",
    "status",
)


@dataclass
class LoadStats:
    """Counts emitted while loading a results directory."""

    runs_total: int = 0
    runs_loaded: int = 0
    runs_skipped_status: int = 0
    runs_skipped_no_score: int = 0
    runs_skipped_no_variant: int = 0
    sources: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "runs_total": self.runs_total,
            "runs_loaded": self.runs_loaded,
            "runs_skipped_status": self.runs_skipped_status,
            "runs_skipped_no_score": self.runs_skipped_no_score,
            "runs_skipped_no_variant": self.runs_skipped_no_variant,
            "sources": dict(self.sources),
        }


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_scores(run: dict[str, Any]) -> dict[str, float | None]:
    """Pull the five scalar score fields out of a run dict.

    Per-run JSONs nest scores under scores.composite (a dict) or scores.static / scores.llm.
    Rolled-up runs put a scores dict with flat keys. Both shapes are handled.
    """
    scores = run.get("scores", {}) or {}

    composite_block = scores.get("composite")
    if isinstance(composite_block, dict):
        composite = _coerce_float(composite_block.get("composite"))
    else:
        composite = _coerce_float(composite_block)

    static_block = scores.get("static") or (
        composite_block.get("static_score") if isinstance(composite_block, dict) else None
    )
    if isinstance(static_block, dict):
        test_pass_rate = _coerce_float(static_block.get("test_pass_rate"))
        lint_score = _coerce_float(static_block.get("lint_score"))
        complexity_score = _coerce_float(static_block.get("complexity_score"))
    else:
        test_pass_rate = _coerce_float(scores.get("test_pass_rate"))
        lint_score = _coerce_float(scores.get("lint_score"))
        complexity_score = _coerce_float(scores.get("complexity_score"))

    llm_block = scores.get("llm") or (
        composite_block.get("llm_score") if isinstance(composite_block, dict) else None
    )
    if isinstance(llm_block, dict):
        llm_quality = _coerce_float(llm_block.get("normalized"))
        if llm_quality is None:
            avg = _coerce_float(llm_block.get("average"))
            llm_quality = avg * 20.0 if avg is not None else None
    else:
        llm_quality = _coerce_float(scores.get("llm_quality"))

    return {
        "composite": composite,
        "test_pass_rate": test_pass_rate,
        "lint_score": lint_score,
        "complexity_score": complexity_score,
        "llm_quality": llm_quality,
    }


def _row_from_run(
    run: dict[str, Any],
    *,
    experiment: str,
    model: str,
    profile: str,
    task: str,
    variant: str,
    run_number: int | None,
    stats: LoadStats,
) -> dict[str, Any] | None:
    status = str(run.get("status") or "success").lower()
    if status != "success":
        stats.runs_skipped_status += 1
        return None

    score_fields = _extract_scores(run)
    if score_fields["composite"] is None:
        stats.runs_skipped_no_score += 1
        return None

    if not variant:
        stats.runs_skipped_no_variant += 1
        return None

    row: dict[str, Any] = {
        "experiment": experiment,
        "model": model,
        "profile": profile,
        "task": task,
        "variant": variant,
        "run_number": int(run_number) if run_number is not None else None,
        "input_tokens": _coerce_float(run.get("input_tokens")),
        "output_tokens": _coerce_float(run.get("output_tokens")),
        "cost": _coerce_float(run.get("cost")),
        "status": status,
        **score_fields,
    }
    return row


def _iter_per_run_files(results_dir: Path) -> list[Path]:
    """Find run-N.json files at depth 4 below the experiment dir.

    Layout: <results_dir>/<model>/<profile>/<task>/<variant>/run-N.json
    """
    out: list[Path] = []
    for path in results_dir.glob("*/*/*/*/run-*.json"):
        if path.is_file():
            out.append(path)
    return out


def _load_per_run_jsons(
    results_dir: Path,
    *,
    experiment: str,
    stats: LoadStats,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    files = _iter_per_run_files(results_dir)
    for path in files:
        stats.runs_total += 1
        try:
            run = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("failed to read %s: %s", path, exc)
            stats.runs_skipped_status += 1
            continue

        # Path: <results_dir>/<model>/<profile>/<task>/<variant>/run-N.json
        rel = path.relative_to(results_dir)
        parts = rel.parts
        if len(parts) < 5:
            continue
        model = run.get("model") or parts[0]
        profile = run.get("profile_name") or parts[1]
        task = run.get("task_name") or parts[2]
        variant = run.get("variant_label") or parts[3]
        run_number = run.get("run_number")
        if run_number is None:
            stem = path.stem  # run-N
            try:
                run_number = int(stem.split("-")[-1])
            except (ValueError, IndexError):
                run_number = None

        row = _row_from_run(
            run,
            experiment=experiment,
            model=str(model),
            profile=str(profile),
            task=str(task),
            variant=str(variant),
            run_number=run_number,
            stats=stats,
        )
        if row is not None:
            rows.append(row)
    return rows


def _split_profile_variant(key: str) -> tuple[str, str]:
    if ":" in key:
        prof, _, variant = key.partition(":")
        return prof, variant
    return key, ""


def _load_rolled_up(
    rollup_path: Path,
    *,
    experiment: str,
    stats: LoadStats,
) -> list[dict[str, Any]]:
    try:
        data = json.loads(rollup_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("failed to read rollup %s: %s", rollup_path, exc)
        return []

    rows: list[dict[str, Any]] = []
    profiles_block = data.get("profiles") or {}
    for prof_key, prof_block in profiles_block.items():
        profile, variant = _split_profile_variant(prof_key)
        tasks_block = (prof_block or {}).get("tasks") or {}
        for task_name, task_block in tasks_block.items():
            for run in (task_block or {}).get("runs", []) or []:
                stats.runs_total += 1
                row = _row_from_run(
                    run,
                    experiment=experiment,
                    model=str(run.get("model") or ""),
                    profile=str(run.get("profile") or profile),
                    task=str(run.get("task") or task_name),
                    variant=variant,
                    run_number=run.get("run_number"),
                    stats=stats,
                )
                if row is not None:
                    rows.append(row)
    return rows


def load_runs(
    results_dir: Path | str,
    *,
    experiment: str | None = None,
    prefer: str = "per_run",
) -> tuple[pd.DataFrame, LoadStats]:
    """Load all successful runs from a single experiment results directory.

    Parameters
    ----------
    results_dir
        Path to ``results/experiment-<name>-<timestamp>/`` (or any dir
        following the same layout).
    experiment
        Override for the experiment name embedded in each row. Defaults to the
        directory's name.
    prefer
        ``"per_run"`` (default) tries per-run JSONs first and falls back to
        ``benchmark-results.json``. ``"rollup"`` reverses the preference.

    Returns
    -------
    (DataFrame, LoadStats)
        DataFrame conforms to :data:`TIDY_COLUMNS`. Failed runs and runs without
        a composite score are excluded; counts are reported in the stats object.
    """
    results_dir = Path(results_dir)
    if not results_dir.exists():
        raise FileNotFoundError(f"results directory not found: {results_dir}")
    if not results_dir.is_dir():
        raise NotADirectoryError(f"not a directory: {results_dir}")

    experiment_name = experiment or results_dir.name
    stats = LoadStats()
    rollup_path = results_dir / "benchmark-results.json"

    rows: list[dict[str, Any]] = []
    if prefer == "per_run":
        rows = _load_per_run_jsons(results_dir, experiment=experiment_name, stats=stats)
        stats.sources["per_run"] = len(rows)
        if not rows and rollup_path.exists():
            rows = _load_rolled_up(rollup_path, experiment=experiment_name, stats=stats)
            stats.sources["rollup"] = len(rows)
    else:
        if rollup_path.exists():
            rows = _load_rolled_up(rollup_path, experiment=experiment_name, stats=stats)
            stats.sources["rollup"] = len(rows)
        if not rows:
            rows = _load_per_run_jsons(results_dir, experiment=experiment_name, stats=stats)
            stats.sources["per_run"] = len(rows)

    df = pd.DataFrame(rows, columns=list(TIDY_COLUMNS))
    if not df.empty:
        for col in (
            "composite",
            "test_pass_rate",
            "lint_score",
            "complexity_score",
            "llm_quality",
            "input_tokens",
            "output_tokens",
            "cost",
        ):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["run_number"] = pd.to_numeric(df["run_number"], errors="coerce").astype("Int64")
        for col in ("experiment", "model", "profile", "task", "variant", "status"):
            df[col] = df[col].astype("string")

    stats.runs_loaded = int(len(df))
    return df, stats


def load_runs_multi(
    root: Path | str,
    *,
    pattern: str = "experiment-*",
    prefer: str = "per_run",
) -> tuple[pd.DataFrame, dict[str, LoadStats]]:
    """Walk a parent directory containing ``experiment-*`` subdirs and load all.

    Each experiment's runs are tagged with the experiment name; the same task
    name across experiments stays the same so it can act as a clustering key
    when desired (callers can rebuild a unique task id with
    ``experiment + "::" + task`` if cross-experiment task identity is suspect).
    """
    root = Path(root)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"not a directory: {root}")

    frames: list[pd.DataFrame] = []
    stats_per_exp: dict[str, LoadStats] = {}
    for child in sorted(root.glob(pattern)):
        if not child.is_dir():
            continue
        if child.name.endswith(".bak"):
            continue
        df, stats = load_runs(child, prefer=prefer)
        stats_per_exp[child.name] = stats
        if not df.empty:
            frames.append(df)

    if frames:
        combined = pd.concat(frames, ignore_index=True)
    else:
        combined = pd.DataFrame(columns=list(TIDY_COLUMNS))
    return combined, stats_per_exp
