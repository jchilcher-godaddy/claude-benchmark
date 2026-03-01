"""Pydantic v2 models for the claude-benchmark scoring subsystem.

These are the shared type contracts for all scoring plans in Phase 4.
All scores are normalized to 0-100 scale per locked decisions.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class StaticScore(BaseModel):
    """Result of static analysis scoring (Ruff, pytest, radon)."""

    test_pass_rate: float = Field(ge=0, le=100, description="Percentage of tests passing")
    tests_passed: int = Field(ge=0)
    tests_total: int = Field(ge=0)
    lint_score: float = Field(ge=0, le=100, description="Lint cleanliness (fewer errors = higher)")
    lint_errors: int = Field(ge=0, description="Total lint violations found")
    lint_details: list[dict] = Field(
        default_factory=list, description="Individual lint violations"
    )
    complexity_score: float = Field(
        ge=0, le=100, description="Complexity score (lower complexity = higher)"
    )
    avg_complexity: float = Field(ge=0, description="Average cyclomatic complexity")
    complexity_details: list[dict] = Field(
        default_factory=list, description="Per-function complexity"
    )
    weighted_total: float = Field(
        ge=0, le=100, description="Weighted composite per locked decision"
    )
    lines_of_code: int = Field(ge=0, default=0, description="LOC for normalization reference")


class LLMCriterionScore(BaseModel):
    """Score for a single LLM judge criterion."""

    name: str
    score: int = Field(ge=1, le=5)
    reasoning: str = Field(description="1-2 sentence justification")


class LLMScore(BaseModel):
    """Result of LLM-as-judge scoring."""

    criteria: list[LLMCriterionScore]
    average: float = Field(ge=1.0, le=5.0, description="Average across all criteria")
    normalized: float = Field(
        ge=0, le=100, description="Mapped to 0-100 (1->0, 2->25, 3->50, 4->75, 5->100)"
    )
    model_used: str = Field(description="Which model was used as judge")


class CompositeScore(BaseModel):
    """Combined static + LLM score."""

    static_score: StaticScore
    llm_score: Optional[LLMScore] = None
    composite: float = Field(ge=0, le=100, description="50% static + 50% LLM")
    static_only: bool = Field(default=False, description="True if LLM scoring failed/skipped")


class AggregateStats(BaseModel):
    """Statistical aggregates across multiple runs."""

    n: int = Field(ge=1, description="Number of runs")
    mean: float
    stdev: float = Field(ge=0)
    ci_lower: float = Field(description="95% CI lower bound")
    ci_upper: float = Field(description="95% CI upper bound")
    min_val: float
    max_val: float
    values: list[float] = Field(default_factory=list, description="Raw values for transparency")


class TokenEfficiency(BaseModel):
    """Token efficiency metrics for quality-per-token analysis."""

    composite_score: float
    total_tokens: int
    claudemd_tokens: int
    task_io_tokens: int
    points_per_1k_tokens: float = Field(
        description="(composite / total_tokens) * 1000, higher is better"
    )


class ScoringWeights(BaseModel):
    """Configurable weights for static scoring components.

    Default weights per locked decision: test(50%) + lint(30%) + complexity(20%).
    """

    test_pass_rate: float = Field(default=0.50, ge=0, le=1.0)
    lint_score: float = Field(default=0.30, ge=0, le=1.0)
    complexity_score: float = Field(default=0.20, ge=0, le=1.0)

    @model_validator(mode="after")
    def validate_weights_sum(self) -> ScoringWeights:
        total = self.test_pass_rate + self.lint_score + self.complexity_score
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0 (got {total:.4f}): "
                f"test_pass_rate={self.test_pass_rate}, "
                f"lint_score={self.lint_score}, "
                f"complexity_score={self.complexity_score}"
            )
        return self
