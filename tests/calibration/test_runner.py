"""Tests for calibration runner."""

from unittest.mock import MagicMock, patch

import pytest

from claude_benchmark.calibration.degrader import CalibrationSample
from claude_benchmark.calibration.runner import (
    CalibrationResults,
    ScoringResult,
    run_calibration,
)
from claude_benchmark.scoring.errors import LLMJudgeError
from claude_benchmark.scoring.models import LLMCriterionScore, LLMScore


def _make_sample(task_name: str = "test-task", tier: str = "gold") -> CalibrationSample:
    return CalibrationSample(
        task_name=task_name,
        tier=tier,
        code="def foo(): pass",
        task_description="Test task",
        reference_solution="def foo(): pass",
    )


def _make_mock_score() -> LLMScore:
    return LLMScore(
        criteria=[
            LLMCriterionScore(name="code_readability", score=4, reasoning="good"),
            LLMCriterionScore(name="architecture_quality", score=4, reasoning="good"),
            LLMCriterionScore(name="instruction_adherence", score=4, reasoning="good"),
            LLMCriterionScore(name="correctness_reasoning", score=4, reasoning="good"),
        ],
        average=4.0,
        normalized=75.0,
        model_used="haiku",
    )


class TestRunCalibration:
    @patch("claude_benchmark.calibration.runner.LLMJudgeScorer")
    def test_correct_number_of_results(self, mock_scorer_cls):
        mock_instance = MagicMock()
        mock_instance.judge_code.return_value = _make_mock_score()
        mock_scorer_cls.return_value = mock_instance

        samples = [_make_sample("t1", "gold"), _make_sample("t1", "severe")]

        result = run_calibration(
            samples=samples,
            models=["haiku"],
            reps_per_model={"haiku": 2},
            concurrency=1,
        )

        assert isinstance(result, CalibrationResults)
        # 2 samples * 1 model * 2 reps = 4 results
        assert len(result.results) == 4
        assert all(isinstance(r, ScoringResult) for r in result.results)

    @patch("claude_benchmark.calibration.runner.LLMJudgeScorer")
    def test_handles_llm_judge_error(self, mock_scorer_cls):
        mock_instance = MagicMock()
        mock_instance.judge_code.side_effect = LLMJudgeError("API error")
        mock_scorer_cls.return_value = mock_instance

        samples = [_make_sample()]

        result = run_calibration(
            samples=samples,
            models=["haiku"],
            reps_per_model={"haiku": 1},
            concurrency=1,
        )

        assert len(result.results) == 1
        assert result.results[0].score is None
        assert result.results[0].error is not None

    @patch("claude_benchmark.calibration.runner.LLMJudgeScorer")
    def test_multiple_models(self, mock_scorer_cls):
        mock_instance = MagicMock()
        mock_instance.judge_code.return_value = _make_mock_score()
        mock_scorer_cls.return_value = mock_instance

        samples = [_make_sample()]

        result = run_calibration(
            samples=samples,
            models=["haiku", "sonnet"],
            reps_per_model={"haiku": 2, "sonnet": 1},
            concurrency=2,
        )

        # 1 sample * (2 haiku reps + 1 sonnet rep) = 3 results
        assert len(result.results) == 3
        haiku_results = [r for r in result.results if r.model == "haiku"]
        sonnet_results = [r for r in result.results if r.model == "sonnet"]
        assert len(haiku_results) == 2
        assert len(sonnet_results) == 1

    @patch("claude_benchmark.calibration.runner.LLMJudgeScorer")
    def test_progress_callback(self, mock_scorer_cls):
        mock_instance = MagicMock()
        mock_instance.judge_code.return_value = _make_mock_score()
        mock_scorer_cls.return_value = mock_instance

        samples = [_make_sample()]
        progress_calls = []

        def on_progress(completed, total):
            progress_calls.append((completed, total))

        run_calibration(
            samples=samples,
            models=["haiku"],
            reps_per_model={"haiku": 3},
            concurrency=1,
            progress_callback=on_progress,
        )

        assert len(progress_calls) == 3
        # All calls should have total=3
        assert all(t == 3 for _, t in progress_calls)

    @patch("claude_benchmark.calibration.runner.LLMJudgeScorer")
    def test_metadata_timestamps(self, mock_scorer_cls):
        mock_instance = MagicMock()
        mock_instance.judge_code.return_value = _make_mock_score()
        mock_scorer_cls.return_value = mock_instance

        result = run_calibration(
            samples=[_make_sample()],
            models=["haiku"],
            reps_per_model={"haiku": 1},
            concurrency=1,
        )

        assert result.started_at != ""
        assert result.finished_at != ""
        assert result.models == ["haiku"]
