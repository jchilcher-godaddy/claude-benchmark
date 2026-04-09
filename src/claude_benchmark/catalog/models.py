"""Data models for the result catalog and cross-run comparison system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class CatalogEntry(BaseModel):
    run_id: str              # Auto-generated "run-001" or user-provided
    name: str                # User label or directory name
    timestamp: str           # ISO from manifest
    results_path: str        # Absolute path to results dir
    tags: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    profiles: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    total_runs: int = 0
    experiment_name: str | None = None
    intake_timestamp: str = ""  # When ingested


class Catalog(BaseModel):
    version: int = 1
    entries: list[CatalogEntry] = Field(default_factory=list)


@dataclass(frozen=True)
class ComparisonKey:
    model: str
    profile: str
    task: str


class PairwiseComparison(BaseModel):
    key_model: str
    key_profile: str
    key_task: str
    dimension: str
    run_a_id: str
    run_a_name: str
    run_a_mean: float
    run_a_n: int
    run_b_id: str
    run_b_name: str
    run_b_mean: float
    run_b_n: int
    delta_pct: float
    p_value: float
    effect_size: float
    effect_label: str
    is_significant: bool
    test_used: str


class ComparisonReport(BaseModel):
    entries: list[CatalogEntry] = Field(default_factory=list)
    overlapping_keys: list[dict[str, str]] = Field(default_factory=list)  # serialized ComparisonKeys
    unique_keys: dict[str, list[dict[str, str]]] = Field(default_factory=dict)  # run_id -> unique keys
    comparisons: list[PairwiseComparison] = Field(default_factory=list)
