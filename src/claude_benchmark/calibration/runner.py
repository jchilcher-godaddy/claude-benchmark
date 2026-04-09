"""Score calibration samples with multiple judge models.

Uses LLMJudgeScorer.judge_code() directly — no temp dirs needed since
code is in-memory strings.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

from claude_benchmark.calibration.degrader import CalibrationSample
from claude_benchmark.scoring.errors import LLMJudgeError
from claude_benchmark.scoring.llm_judge import LLMJudgeScorer
from claude_benchmark.scoring.models import LLMScore

logger = logging.getLogger(__name__)

# Default repetitions per model (cost control: opus is expensive)
DEFAULT_REPS: dict[str, int] = {
    "haiku": 5,
    "sonnet": 5,
    "opus": 3,
}


@dataclass
class ScoringResult:
    sample: CalibrationSample
    model: str
    rep: int
    score: LLMScore | None  # None if scoring failed
    error: str | None = None


@dataclass
class CalibrationResults:
    results: list[ScoringResult]
    models: list[str]
    samples: list[CalibrationSample]
    reps_per_model: dict[str, int]
    started_at: str = ""
    finished_at: str = ""


def _score_one(
    sample: CalibrationSample,
    model: str,
    rep: int,
) -> ScoringResult:
    """Score a single sample with a single model. Thread-safe."""
    scorer = LLMJudgeScorer(model=model)
    try:
        score = scorer.judge_code(
            code=sample.code,
            task_description=sample.task_description,
            reference_solution=sample.reference_solution,
        )
        return ScoringResult(sample=sample, model=model, rep=rep, score=score)
    except LLMJudgeError as exc:
        logger.warning(
            "Scoring failed: model=%s task=%s tier=%s rep=%d: %s",
            model, sample.task_name, sample.tier, rep, exc,
        )
        return ScoringResult(
            sample=sample, model=model, rep=rep, score=None, error=str(exc),
        )


def run_calibration(
    samples: list[CalibrationSample],
    models: list[str] | None = None,
    reps_per_model: dict[str, int] | None = None,
    concurrency: int = 5,
    progress_callback=None,
) -> CalibrationResults:
    """Score every sample with every model N times.

    Args:
        samples: Calibration samples to score.
        models: Judge model names (default: haiku, sonnet, opus).
        reps_per_model: Repetitions per model. Defaults from DEFAULT_REPS.
        concurrency: Max parallel API calls.
        progress_callback: Optional callable(completed, total) for progress updates.

    Returns:
        CalibrationResults with all scoring outcomes.
    """
    if models is None:
        models = ["haiku", "sonnet", "opus"]
    if reps_per_model is None:
        reps_per_model = {m: DEFAULT_REPS.get(m, 5) for m in models}

    started_at = datetime.now().isoformat()
    results: list[ScoringResult] = []

    # Build work items
    work_items: list[tuple[CalibrationSample, str, int]] = []
    for sample in samples:
        for model in models:
            reps = reps_per_model.get(model, 5)
            for rep in range(reps):
                work_items.append((sample, model, rep))

    total = len(work_items)
    completed = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(_score_one, sample, model, rep): (sample, model, rep)
            for sample, model, rep in work_items
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            if progress_callback:
                progress_callback(completed, total)

    finished_at = datetime.now().isoformat()

    return CalibrationResults(
        results=results,
        models=models,
        samples=samples,
        reps_per_model=reps_per_model,
        started_at=started_at,
        finished_at=finished_at,
    )
