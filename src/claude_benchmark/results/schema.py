from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class RunResult(BaseModel):
    run_number: int
    success: bool
    wall_clock_seconds: float
    duration_ms: int = 0
    duration_api_ms: int = 0
    total_cost_usd: Optional[float] = None
    num_turns: int = 0
    session_id: Optional[str] = None
    usage: Optional[TokenUsage] = None
    output_files: dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class StatsSummary(BaseModel):
    mean: float
    variance: float
    stdev: float


class AggregateResult(BaseModel):
    task_name: str
    profile_name: str
    model: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    wall_clock: Optional[StatsSummary] = None
    input_tokens: Optional[StatsSummary] = None
    output_tokens: Optional[StatsSummary] = None
    cost_usd: Optional[StatsSummary] = None
    failed_details: list[str] = Field(default_factory=list)


class BenchmarkManifest(BaseModel):
    timestamp: datetime
    models: list[str]
    profiles: list[str]
    tasks: list[str]
    runs_per_combination: int
    total_combinations: int
    total_runs: int
    cli_args: dict[str, str] = Field(default_factory=dict)
    scoring_version: str = Field(default="1.0")
