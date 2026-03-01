"""Scoring subsystem for claude-benchmark.

Provides Pydantic models for all score types, custom error classes,
scorers for static analysis and LLM-as-judge evaluation, composite
scoring, statistical aggregation, and token efficiency metrics.
"""

from .aggregator import StatisticalAggregator, compute_aggregate
from .composite import CompositeScorer
from .errors import LLMJudgeError, ScoringError, StaticAnalysisError
from .llm_judge import LLMJudgeScorer
from .models import (
    AggregateStats,
    CompositeScore,
    LLMCriterionScore,
    LLMScore,
    ScoringWeights,
    StaticScore,
    TokenEfficiency,
)
from .pipeline import ScoringProgressCallback, score_all_runs, score_run
from .static import StaticScorer
from .token_efficiency import compute_token_efficiency

__all__ = [
    "AggregateStats",
    "CompositeScore",
    "CompositeScorer",
    "LLMCriterionScore",
    "LLMJudgeError",
    "LLMJudgeScorer",
    "LLMScore",
    "ScoringError",
    "ScoringProgressCallback",
    "ScoringWeights",
    "StaticAnalysisError",
    "StaticScore",
    "StaticScorer",
    "StatisticalAggregator",
    "TokenEfficiency",
    "compute_aggregate",
    "compute_token_efficiency",
    "score_all_runs",
    "score_run",
]
