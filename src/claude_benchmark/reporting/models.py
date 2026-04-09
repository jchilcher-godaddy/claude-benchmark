"""Pydantic v2 data models for benchmark reporting.

These are the shared data contracts for all reporting modules in Phase 6.
Models represent the structured output of benchmark runs, ready for
export (JSON/CSV), visualization (charts), and analysis (regression detection).
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RunResult(BaseModel):
    """Single run output for one profile/task/model combination."""

    model_config = ConfigDict(frozen=True)

    profile: str
    task: str
    model: str
    scores: dict[str, float] = Field(default_factory=dict)
    score_details: dict = Field(default_factory=dict)
    token_count: int = 0
    code_output: str = ""
    success: bool = True
    error: Optional[str] = None
    output_dir: Optional[str] = None
    variant_label: Optional[str] = None


class TaskResult(BaseModel):
    """Aggregated results for one task across multiple runs."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    task_name: str
    runs: list[RunResult] = Field(default_factory=list)
    mean_scores: dict[str, float] = Field(default_factory=dict)
    std_scores: dict[str, float] = Field(default_factory=dict)


class ProfileResult(BaseModel):
    """All results for one profile across all tasks."""

    model_config = ConfigDict(frozen=True)

    profile_id: str
    profile_name: str
    tasks: dict[str, TaskResult] = Field(default_factory=dict)
    aggregate_scores: dict[str, float] = Field(default_factory=dict)
    total_tokens: int = 0


class ReportMetadata(BaseModel):
    """Metadata about the benchmark run."""

    model_config = ConfigDict(frozen=True)

    date: str
    models_tested: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    profile_count: int = 0
    total_runs: int = 0
    wall_clock_seconds: float = 0.0


class RegressionResult(BaseModel):
    """Result of a statistical regression test between baseline and profile."""

    model_config = ConfigDict(frozen=True)

    profile: str
    task: str
    dimension: str
    baseline_mean: float
    profile_mean: float
    delta_pct: float
    p_value: float
    is_regression: bool
    test_used: str


def _sanitize_value(v: object) -> object:
    """Replace NaN/Infinity float values with None for JSON safety."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _sanitize_dict(d: object) -> object:
    """Recursively sanitize a dict/list structure, replacing NaN/Infinity with None."""
    if isinstance(d, dict):
        return {k: _sanitize_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_sanitize_dict(item) for item in d]
    return _sanitize_value(d)


class BenchmarkResults(BaseModel):
    """Top-level container for all benchmark results.

    This is the primary data structure consumed by exporters,
    report generators, and regression detection.
    """

    model_config = ConfigDict(frozen=True)

    profiles: dict[str, ProfileResult] = Field(default_factory=dict)
    models: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    metadata: ReportMetadata = Field(default_factory=lambda: ReportMetadata(date=""))

    def to_export_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON export.

        NaN and Infinity values are replaced with None for JSON safety.
        """
        raw = self.model_dump()
        return _sanitize_dict(raw)

    def to_csv_rows(self) -> list[dict]:
        """Flatten to list of flat dicts (one row per run) for CSV export.

        Each row contains: profile, task, model, success, error,
        token_count, code_output, and individual score dimensions as columns.
        """
        rows: list[dict] = []
        for profile_id, profile_result in self.profiles.items():
            for task_id, task_result in profile_result.tasks.items():
                for run in task_result.runs:
                    row: dict[str, object] = {
                        "profile": run.profile,
                        "task": run.task,
                        "model": run.model,
                        "success": run.success,
                        "error": run.error or "",
                        "token_count": run.token_count,
                        "code_output": run.code_output,
                    }
                    if run.variant_label:
                        row["variant_label"] = run.variant_label
                    # Flatten score dimensions into individual columns
                    for dim, score in run.scores.items():
                        row[f"score_{dim}"] = _sanitize_value(score)
                    rows.append(row)
        return rows
