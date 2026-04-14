"""Scoring subsystem for claude-benchmark.

Provides Pydantic models for all score types, custom error classes,
scorers for static analysis and LLM-as-judge evaluation, composite
scoring, statistical aggregation, and token efficiency metrics.
"""

from .aggregator import StatisticalAggregator, compute_aggregate
from .base_scorer import BaseStaticScorer
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
from .lang_csharp import CSharpStaticScorer
from .lang_go import GoStaticScorer
from .lang_javascript import JavaScriptStaticScorer
from .registry import get_scorer, register_scorer, registered_languages
from .static import PythonStaticScorer, StaticScorer
from .token_efficiency import compute_token_efficiency

__all__ = [
    "AggregateStats",
    "BaseStaticScorer",
    "CSharpStaticScorer",
    "CompositeScore",
    "CompositeScorer",
    "LLMCriterionScore",
    "LLMJudgeError",
    "LLMJudgeScorer",
    "GoStaticScorer",
    "JavaScriptStaticScorer",
    "LLMScore",
    "PythonStaticScorer",
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
    "get_scorer",
    "register_scorer",
    "registered_languages",
    "score_all_runs",
    "score_run",
]
