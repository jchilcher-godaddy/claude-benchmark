"""Scoring pipeline orchestrator for claude-benchmark.

Bridges the scoring subsystem to the execution engine by orchestrating
StaticScorer, LLMJudgeScorer, CompositeScorer, token efficiency, and
statistical aggregation into a unified pipeline.

Provides two entry points:
- score_run(): Score a single RunResult
- score_all_runs(): Score all successful results in batch phases
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

from claude_benchmark.execution.parallel import RunResult
from claude_benchmark.profiles.token_counter import count_tokens_approx
from claude_benchmark.scoring.aggregator import StatisticalAggregator
from claude_benchmark.scoring.composite import CompositeScorer
from claude_benchmark.scoring.errors import LLMJudgeError, ScoringError, is_deterministic_llm_error
from claude_benchmark.scoring.llm_judge import LLMJudgeScorer
from claude_benchmark.scoring.models import AggregateStats, CompositeScore, TokenEfficiency
from claude_benchmark.scoring.static import StaticScorer
from claude_benchmark.scoring.token_efficiency import compute_token_efficiency
from claude_benchmark.tasks.loader import load_judge_rubric, load_task

logger = logging.getLogger(__name__)

_STATIC_SCORING_CONCURRENCY = 10
_LLM_SCORING_CONCURRENCY = 20


def _score_static_single(
    i: int,
    result: RunResult,
    strict: bool,
) -> tuple[int, object, object]:
    """Score a single result with static analysis.

    Returns:
        Tuple of (index, task_def, static_score_or_None).
    """
    task_def = load_task(result.run.task_dir)
    try:
        test_file = result.run.task_dir / task_def.scoring.test_file

        weights = None
        if task_def.scoring.weight_override:
            from claude_benchmark.scoring.models import ScoringWeights
            weights = ScoringWeights(**task_def.scoring.weight_override)

        static_score = StaticScorer(weights=weights).score(
            result.output_dir, test_file, ruff_rules=task_def.scoring.ruff_rules
        )
        return (i, task_def, static_score)
    except Exception as exc:
        logger.warning("Static scoring failed for %s: %s", result.run.result_key, exc)
        if strict:
            raise ScoringError(f"Static scoring failed: {exc}") from exc
        return (i, task_def, None)


def _score_llm_single(
    i: int,
    result: RunResult,
    task_def: object,
    strict: bool,
) -> tuple[int, object]:
    """Score a single result with LLM judge (includes retry logic).

    Returns:
        Tuple of (index, llm_score_or_None).
    """
    ref_path = None
    if task_def.scoring.reference_solution:
        ref_path = result.run.task_dir / task_def.scoring.reference_solution

    custom_criteria = None
    if task_def.scoring.judge_rubric:
        rubric_path = result.run.task_dir / task_def.scoring.judge_rubric
        custom_criteria = load_judge_rubric(rubric_path)

    llm_score = None
    backoff = [0, 1, 2]
    for attempt in range(3):
        try:
            if backoff[attempt] > 0:
                time.sleep(backoff[attempt])
            llm_score = LLMJudgeScorer(
                use_gocode=result.run.use_gocode,
            ).score(
                result.output_dir,
                task_def.description,
                custom_criteria=custom_criteria,
                reference_solution_path=ref_path,
            )
            return (i, llm_score)
        except (LLMJudgeError, Exception) as exc:
            if isinstance(exc, LLMJudgeError) and is_deterministic_llm_error(exc):
                logger.info(
                    "Deterministic LLM failure for %s: %s (no retry)",
                    result.run.result_key,
                    exc,
                )
                if strict:
                    raise ScoringError(f"LLM scoring failed (deterministic): {exc}") from exc
                return (i, None)
            logger.warning(
                "LLM scoring attempt %d/3 failed for %s: %s",
                attempt + 1,
                result.run.result_key,
                exc,
            )
            if attempt == 2:
                if strict:
                    raise ScoringError(
                        f"LLM scoring failed after 3 attempts: {exc}"
                    ) from exc
                llm_score = None

    return (i, llm_score)


@runtime_checkable
class ScoringProgressCallback(Protocol):
    """Protocol for receiving scoring progress updates."""

    def scoring_started(self, phase: str, total: int) -> None:
        """Called when a scoring phase begins.

        Args:
            phase: Phase name ("static", "llm", "composite").
            total: Total number of items to score in this phase.
        """
        ...

    def scoring_progress(self, phase: str, completed: int, total: int, run_key: str) -> None:
        """Called after each run is scored.

        Args:
            phase: Phase name ("static", "llm", "composite").
            completed: Number of items completed so far.
            total: Total number of items in this phase.
            run_key: Unique key identifying the run.
        """
        ...

    def scoring_completed(self, phase: str) -> None:
        """Called when a scoring phase finishes.

        Args:
            phase: Phase name ("static", "llm", "composite").
        """
        ...


def score_run(
    result: RunResult,
    task_dir: Path,
    skip_llm: bool = False,
    strict: bool = False,
) -> dict:
    """Score a single benchmark run result.

    Orchestrates static analysis, LLM-as-judge (with retry), composite
    scoring, and token efficiency computation for one run.

    Args:
        result: The RunResult to score (must have output_dir set).
        task_dir: Path to the task directory containing task.toml.
        skip_llm: If True, skip LLM-as-judge scoring.
        strict: If True, re-raise scorer failures instead of degrading.

    Returns:
        Dict with keys: static, llm, composite, token_efficiency, degraded, failed_scorers.
    """
    task_def = load_task(task_dir)

    scores: dict = {
        "static": None,
        "llm": None,
        "composite": None,
        "token_efficiency": None,
        "degraded": False,
        "failed_scorers": [],
    }

    static_score = None
    llm_score = None

    # --- Static scoring ---
    try:
        test_file = task_dir / task_def.scoring.test_file

        weights = None
        if task_def.scoring.weight_override:
            from claude_benchmark.scoring.models import ScoringWeights
            weights = ScoringWeights(**task_def.scoring.weight_override)

        static_score = StaticScorer(weights=weights).score(
            result.output_dir, test_file, ruff_rules=task_def.scoring.ruff_rules
        )
        scores["static"] = static_score.model_dump()
    except Exception as exc:
        logger.warning("Static scoring failed for %s: %s", result.run.result_key, exc)
        if strict:
            raise ScoringError(f"Static scoring failed: {exc}") from exc
        scores["failed_scorers"].append("static")
        scores["degraded"] = True

    # --- LLM scoring (optional) ---
    if not skip_llm:
        ref_path = None
        if task_def.scoring.reference_solution:
            ref_path = task_dir / task_def.scoring.reference_solution

        custom_criteria = None
        if task_def.scoring.judge_rubric:
            rubric_path = task_dir / task_def.scoring.judge_rubric
            custom_criteria = load_judge_rubric(rubric_path)

        backoff = [0, 1, 2]
        for attempt in range(3):
            try:
                if backoff[attempt] > 0:
                    time.sleep(backoff[attempt])
                llm_score = LLMJudgeScorer(
                    use_gocode=result.run.use_gocode,
                ).score(
                    result.output_dir,
                    task_def.description,
                    custom_criteria=custom_criteria,
                    reference_solution_path=ref_path,
                )
                scores["llm"] = llm_score.model_dump()
                break
            except (LLMJudgeError, Exception) as exc:
                if isinstance(exc, LLMJudgeError) and is_deterministic_llm_error(exc):
                    logger.info(
                        "Deterministic LLM failure for %s: %s (no retry)",
                        result.run.result_key,
                        exc,
                    )
                    if strict:
                        raise ScoringError(f"LLM scoring failed (deterministic): {exc}") from exc
                    scores["failed_scorers"].append("llm_judge")
                    scores["degraded"] = True
                    llm_score = None
                    break
                logger.warning(
                    "LLM scoring attempt %d/3 failed for %s: %s",
                    attempt + 1,
                    result.run.result_key,
                    exc,
                )
                if attempt == 2:
                    # Last attempt exhausted
                    if strict:
                        raise ScoringError(f"LLM scoring failed after 3 attempts: {exc}") from exc
                    scores["failed_scorers"].append("llm_judge")
                    scores["degraded"] = True
                    llm_score = None

    # --- Composite scoring ---
    if static_score is not None:
        try:
            composite = CompositeScorer().compute(static_score, llm_score if llm_score else None)
            scores["composite"] = composite.model_dump()
        except Exception as exc:
            logger.warning("Composite scoring failed for %s: %s", result.run.result_key, exc)
            if strict:
                raise ScoringError(f"Composite scoring failed: {exc}") from exc
            scores["failed_scorers"].append("composite")
            scores["degraded"] = True
            composite = None
    else:
        composite = None

    # --- Token efficiency ---
    if composite is not None:
        try:
            profile_text = ""
            if result.run.profile_path and result.run.profile_path.exists():
                try:
                    profile_text = result.run.profile_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    profile_text = ""

            claudemd_tokens = count_tokens_approx(profile_text)
            efficiency = compute_token_efficiency(
                composite.composite, claudemd_tokens, result.total_tokens
            )
            scores["token_efficiency"] = efficiency.model_dump()
        except Exception as exc:
            logger.warning("Token efficiency failed for %s: %s", result.run.result_key, exc)
            if strict:
                raise ScoringError(f"Token efficiency failed: {exc}") from exc

    return scores


def score_all_runs(
    results: list[RunResult],
    skip_llm: bool = False,
    strict: bool = False,
    progress: ScoringProgressCallback | None = None,
) -> tuple[list[RunResult], dict[str, dict[str, AggregateStats]]]:
    """Score all successful benchmark results in batch phases.

    Processes results in three phases:
    1. Static scoring for all successful results
    2. LLM-as-judge scoring (if not skipped) for all successful results
    3. Composite + token efficiency computation

    Then aggregates results by variant (task_name, profile_name, model).

    Args:
        results: List of RunResult instances from the execution engine.
        skip_llm: If True, skip LLM-as-judge scoring.
        strict: If True, re-raise scorer failures instead of degrading.
        progress: Optional callback for scoring progress updates.

    Returns:
        Tuple of (results_with_scores, aggregation_dict).
        results_with_scores: The input results list with .scores populated.
        aggregation_dict: Per-variant aggregation keyed by "task|profile|model".
    """
    successful = [r for r in results if r.status == "success" and r.output_dir]

    if not successful:
        return results, {}

    # Storage for intermediate scoring results
    static_scores: dict[int, object] = {}  # index -> StaticScore or None
    llm_scores: dict[int, object] = {}  # index -> LLMScore or None
    task_defs: dict[int, object] = {}  # index -> TaskDefinition
    scores_dicts: dict[int, dict] = {}  # index -> scores dict

    # --- Phase A: Static scoring (parallel) ---
    if progress:
        progress.scoring_started("static", len(successful))

    completed_static = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=_STATIC_SCORING_CONCURRENCY) as executor:
        futures = {
            executor.submit(_score_static_single, i, r, strict): i
            for i, r in enumerate(successful)
        }
        for future in concurrent.futures.as_completed(futures):
            idx, task_def, static_score = future.result()
            task_defs[idx] = task_def
            static_scores[idx] = static_score
            completed_static += 1
            if progress:
                progress.scoring_progress(
                    "static", completed_static, len(successful),
                    successful[idx].run.result_key,
                )

    if progress:
        progress.scoring_completed("static")

    # --- Phase B: LLM scoring (parallel, optional) ---
    if not skip_llm:
        if progress:
            progress.scoring_started("llm", len(successful))

        completed_llm = 0
        executor_params = {"max_workers": _LLM_SCORING_CONCURRENCY}
        with concurrent.futures.ThreadPoolExecutor(**executor_params) as executor:
            futures = {
                executor.submit(_score_llm_single, i, r, task_defs[i], strict): i
                for i, r in enumerate(successful)
            }
            for future in concurrent.futures.as_completed(futures):
                idx, llm_score = future.result()
                llm_scores[idx] = llm_score
                completed_llm += 1
                if progress:
                    progress.scoring_progress(
                        "llm", completed_llm, len(successful),
                        successful[idx].run.result_key,
                    )

        if progress:
            progress.scoring_completed("llm")

    # --- Phase C: Composite + Token Efficiency ---
    if progress:
        progress.scoring_started("composite", len(successful))

    for i, result in enumerate(successful):
        static_score = static_scores.get(i)
        llm_score = llm_scores.get(i) if not skip_llm else None

        scores: dict = {
            "static": None,
            "llm": None,
            "composite": None,
            "token_efficiency": None,
            "degraded": False,
            "failed_scorers": [],
        }

        if static_score is not None:
            scores["static"] = static_score.model_dump()
        else:
            scores["failed_scorers"].append("static")
            scores["degraded"] = True

        if not skip_llm and llm_score is not None:
            scores["llm"] = llm_score.model_dump()
        elif not skip_llm and llm_score is None:
            scores["failed_scorers"].append("llm_judge")
            scores["degraded"] = True

        # Composite
        composite = None
        if static_score is not None:
            try:
                composite = CompositeScorer().compute(
                    static_score, llm_score if llm_score else None
                )
                scores["composite"] = composite.model_dump()
            except Exception as exc:
                logger.warning("Composite scoring failed for %s: %s", result.run.result_key, exc)
                if strict:
                    raise ScoringError(f"Composite scoring failed: {exc}") from exc

        # Token efficiency
        if composite is not None:
            try:
                profile_text = ""
                if result.run.profile_path and result.run.profile_path.exists():
                    try:
                        profile_text = result.run.profile_path.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        profile_text = ""

                claudemd_tokens = count_tokens_approx(profile_text)
                efficiency = compute_token_efficiency(
                    composite.composite, claudemd_tokens, result.total_tokens
                )
                scores["token_efficiency"] = efficiency.model_dump()
            except Exception as exc:
                logger.warning(
                    "Token efficiency failed for %s: %s", result.run.result_key, exc
                )
                if strict:
                    raise ScoringError(f"Token efficiency failed: {exc}") from exc

        result.scores = scores
        scores_dicts[i] = scores

        if progress:
            progress.scoring_progress("composite", i + 1, len(successful), result.run.result_key)

    if progress:
        progress.scoring_completed("composite")

    # --- Aggregation (SCOR-03) ---
    aggregation: dict[str, dict[str, AggregateStats]] = {}

    # Group by variant key: (task_name, profile_name, model[, variant_label])
    variant_groups: dict[str, list[int]] = {}
    for i, result in enumerate(successful):
        key = f"{result.run.task_name}|{result.run.profile_name}|{result.run.model}"
        if result.run.variant_label:
            key = f"{key}|{result.run.variant_label}"
        variant_groups.setdefault(key, []).append(i)

    aggregator = StatisticalAggregator()

    for variant_key, indices in variant_groups.items():
        # Extract CompositeScore objects for runs that have composite scores
        composites = []
        efficiencies = []
        for idx in indices:
            sd = scores_dicts.get(idx, {})
            if sd.get("composite"):
                composites.append(CompositeScore.model_validate(sd["composite"]))
            if sd.get("token_efficiency"):
                efficiencies.append(TokenEfficiency.model_validate(sd["token_efficiency"]))

        if composites:
            score_aggs = aggregator.aggregate_run_scores(composites)
            # Convert AggregateStats to dicts for JSON serialization
            score_aggs_dict = {k: v.model_dump() for k, v in score_aggs.items()}
        else:
            score_aggs_dict = {}

        efficiency_agg_dict = {}
        if efficiencies:
            efficiency_agg = aggregator.aggregate_token_efficiency(efficiencies)
            efficiency_agg_dict = efficiency_agg.model_dump()

        aggregation[variant_key] = {
            "scores": score_aggs_dict,
            "token_efficiency": efficiency_agg_dict,
        }

    return results, aggregation
