"""Tests for scoring pipeline orchestrator.

Verifies that score_run() and score_all_runs() correctly orchestrate
static scoring, LLM-as-judge scoring, composite scoring, token efficiency,
and statistical aggregation. Uses mocked scorers to avoid subprocess/API calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_benchmark.execution.parallel import BenchmarkRun, RunResult
from claude_benchmark.scoring.errors import LLMJudgeError, ScoringError, StaticAnalysisError
from claude_benchmark.scoring.models import (
    CompositeScore,
    LLMCriterionScore,
    LLMScore,
    StaticScore,
    TokenEfficiency,
)
from claude_benchmark.scoring.pipeline import ScoringProgressCallback, score_all_runs, score_run


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_static(weighted_total: float = 80.0) -> StaticScore:
    """Create a StaticScore with the given weighted_total."""
    return StaticScore(
        test_pass_rate=80.0,
        tests_passed=8,
        tests_total=10,
        lint_score=70.0,
        lint_errors=3,
        complexity_score=65.0,
        avg_complexity=8.0,
        weighted_total=weighted_total,
        lines_of_code=100,
    )


def _make_llm(normalized: float = 60.0, average: float = 3.4) -> LLMScore:
    """Create an LLMScore with the given normalized score."""
    return LLMScore(
        criteria=[
            LLMCriterionScore(name="code_readability", score=3, reasoning="Decent"),
            LLMCriterionScore(name="architecture_quality", score=4, reasoning="Good"),
            LLMCriterionScore(name="instruction_adherence", score=3, reasoning="OK"),
            LLMCriterionScore(name="correctness_reasoning", score=4, reasoning="Solid"),
        ],
        average=average,
        normalized=normalized,
        model_used="test-model",
    )


def _make_task_dir(tmp_path: Path, task_name: str = "test-task") -> Path:
    """Create a minimal task directory with task.toml and test file."""
    task_dir = tmp_path / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    # Create task.toml
    toml_content = f"""\
name = "{task_name}"
task_type = "code-gen"
difficulty = "medium"
description = "A test task for unit testing"
prompt = "Write a function that adds two numbers"
size = "function"

[scoring]
test_file = "test_solution.py"
"""
    (task_dir / "task.toml").write_text(toml_content)

    # Create test file
    (task_dir / "test_solution.py").write_text(
        "def test_add():\n    assert 1 + 1 == 2\n"
    )

    return task_dir


def _make_task_dir_with_ref(tmp_path: Path, task_name: str = "ref-task") -> Path:
    """Create a task directory with a reference solution."""
    task_dir = _make_task_dir(tmp_path, task_name)

    # Update task.toml to include reference_solution
    toml_content = f"""\
name = "{task_name}"
task_type = "code-gen"
difficulty = "medium"
description = "A test task with reference solution"
prompt = "Write a function that adds two numbers"
size = "function"

[scoring]
test_file = "test_solution.py"
reference_solution = "reference.py"
"""
    (task_dir / "task.toml").write_text(toml_content)
    (task_dir / "reference.py").write_text("def add(a, b):\n    return a + b\n")

    return task_dir


def _make_output_dir(tmp_path: Path, name: str = "output") -> Path:
    """Create an output directory with a minimal Python file."""
    output_dir = tmp_path / name
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "solution.py").write_text("def add(a, b):\n    return a + b\n")
    return output_dir


def _make_profile(tmp_path: Path, name: str = "test-profile") -> Path:
    """Create a minimal CLAUDE.md profile file."""
    profile_path = tmp_path / f"{name}.md"
    profile_path.write_text("# Test Profile\n\nSome instructions for Claude.\n")
    return profile_path


def _make_benchmark_run(
    tmp_path: Path,
    task_name: str = "test-task",
    profile_name: str = "test-profile",
    model: str = "test-model",
    run_number: int = 1,
) -> BenchmarkRun:
    """Create a BenchmarkRun with a task directory and profile path."""
    task_dir = _make_task_dir(tmp_path, task_name)
    profile_path = _make_profile(tmp_path, profile_name)
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    return BenchmarkRun(
        task_name=task_name,
        profile_name=profile_name,
        model=model,
        run_number=run_number,
        task_dir=task_dir,
        profile_path=profile_path,
        results_dir=results_dir,
    )


def _make_run_result(
    tmp_path: Path,
    task_name: str = "test-task",
    profile_name: str = "test-profile",
    model: str = "test-model",
    run_number: int = 1,
    status: str = "success",
    total_tokens: int = 5000,
) -> RunResult:
    """Create a RunResult with a valid output_dir."""
    run = _make_benchmark_run(tmp_path, task_name, profile_name, model, run_number)
    output_dir = _make_output_dir(tmp_path, f"output-{task_name}-{run_number}")

    return RunResult(
        run=run,
        status=status,
        output_dir=output_dir if status == "success" else None,
        total_tokens=total_tokens,
        input_tokens=total_tokens // 2,
        output_tokens=total_tokens // 2,
        cost=0.01,
        duration_seconds=5.0,
    )


# ---------------------------------------------------------------------------
# Tests: score_run() -- static only
# ---------------------------------------------------------------------------


class TestScoreRunStaticOnly:
    """Tests for score_run() with skip_llm=True (static-only mode)."""

    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_score_run_static_only(self, mock_scorer_cls, tmp_path: Path) -> None:
        """Static-only scoring populates static, composite, and token_efficiency."""
        mock_scorer = mock_scorer_cls.return_value
        static = _make_static(80.0)
        mock_scorer.score.return_value = static

        run = _make_benchmark_run(tmp_path)
        output_dir = _make_output_dir(tmp_path)
        result = RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            total_tokens=5000,
        )

        scores = score_run(result, run.task_dir, skip_llm=True)

        assert scores["static"] is not None
        assert scores["static"]["weighted_total"] == 80.0
        assert scores["llm"] is None
        assert scores["composite"] is not None
        assert scores["composite"]["static_only"] is True
        assert scores["token_efficiency"] is not None
        assert scores["degraded"] is False
        assert scores["failed_scorers"] == []


# ---------------------------------------------------------------------------
# Tests: score_run() -- full scoring
# ---------------------------------------------------------------------------


class TestScoreRunFull:
    """Tests for score_run() with both static and LLM scoring."""

    @patch("claude_benchmark.scoring.pipeline.LLMJudgeScorer")
    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_score_run_full(
        self, mock_static_cls, mock_llm_cls, tmp_path: Path
    ) -> None:
        """Full scoring populates static, llm, composite, token_efficiency."""
        mock_static = mock_static_cls.return_value
        static = _make_static(80.0)
        mock_static.score.return_value = static

        mock_llm = mock_llm_cls.return_value
        llm = _make_llm(60.0)
        mock_llm.score.return_value = llm

        run = _make_benchmark_run(tmp_path)
        output_dir = _make_output_dir(tmp_path)
        result = RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            total_tokens=5000,
        )

        scores = score_run(result, run.task_dir, skip_llm=False)

        assert scores["static"] is not None
        assert scores["llm"] is not None
        assert scores["composite"] is not None
        assert scores["composite"]["static_only"] is False
        # 80*0.5 + 60*0.5 = 70.0
        assert scores["composite"]["composite"] == 70.0
        assert scores["token_efficiency"] is not None
        assert scores["degraded"] is False


# ---------------------------------------------------------------------------
# Tests: score_run() -- LLM failure degradation
# ---------------------------------------------------------------------------


class TestScoreRunLLMDegradation:
    """Tests for graceful degradation when LLM scoring fails."""

    @patch("claude_benchmark.scoring.pipeline.time")
    @patch("claude_benchmark.scoring.pipeline.LLMJudgeScorer")
    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_llm_failure_degradation(
        self, mock_static_cls, mock_llm_cls, mock_time, tmp_path: Path
    ) -> None:
        """LLM failure after 3 retries produces static-only composite with degraded flag."""
        mock_static = mock_static_cls.return_value
        mock_static.score.return_value = _make_static(80.0)

        mock_llm = mock_llm_cls.return_value
        mock_llm.score.side_effect = LLMJudgeError("API error")

        # Don't actually sleep during tests
        mock_time.sleep = MagicMock()

        run = _make_benchmark_run(tmp_path)
        output_dir = _make_output_dir(tmp_path)
        result = RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            total_tokens=5000,
        )

        scores = score_run(result, run.task_dir, skip_llm=False)

        assert scores["degraded"] is True
        assert "llm_judge" in scores["failed_scorers"]
        assert scores["llm"] is None
        assert scores["composite"] is not None
        assert scores["composite"]["static_only"] is True
        # Called 3 times (retry attempts)
        assert mock_llm.score.call_count == 3


# ---------------------------------------------------------------------------
# Tests: score_run() -- strict mode
# ---------------------------------------------------------------------------


class TestScoreRunStrictMode:
    """Tests for strict mode where failures raise exceptions."""

    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_strict_static_failure(self, mock_static_cls, tmp_path: Path) -> None:
        """Strict mode re-raises static scoring failures as ScoringError."""
        mock_static = mock_static_cls.return_value
        mock_static.score.side_effect = StaticAnalysisError("Ruff crashed", tool="ruff")

        run = _make_benchmark_run(tmp_path)
        output_dir = _make_output_dir(tmp_path)
        result = RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            total_tokens=5000,
        )

        with pytest.raises(ScoringError, match="Static scoring failed"):
            score_run(result, run.task_dir, strict=True)

    @patch("claude_benchmark.scoring.pipeline.time")
    @patch("claude_benchmark.scoring.pipeline.LLMJudgeScorer")
    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_strict_llm_failure(
        self, mock_static_cls, mock_llm_cls, mock_time, tmp_path: Path
    ) -> None:
        """Strict mode re-raises LLM scoring failures as ScoringError."""
        mock_static = mock_static_cls.return_value
        mock_static.score.return_value = _make_static(80.0)

        mock_llm = mock_llm_cls.return_value
        mock_llm.score.side_effect = LLMJudgeError("API error")
        mock_time.sleep = MagicMock()

        run = _make_benchmark_run(tmp_path)
        output_dir = _make_output_dir(tmp_path)
        result = RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            total_tokens=5000,
        )

        with pytest.raises(ScoringError, match="LLM scoring failed"):
            score_run(result, run.task_dir, skip_llm=False, strict=True)


# ---------------------------------------------------------------------------
# Tests: score_run() -- graceful static failure
# ---------------------------------------------------------------------------


class TestScoreRunGracefulStaticFailure:
    """Tests for graceful degradation when static scoring fails."""

    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_graceful_static_failure(self, mock_static_cls, tmp_path: Path) -> None:
        """Static failure in non-strict mode produces degraded scores."""
        mock_static = mock_static_cls.return_value
        mock_static.score.side_effect = Exception("pytest crashed")

        run = _make_benchmark_run(tmp_path)
        output_dir = _make_output_dir(tmp_path)
        result = RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            total_tokens=5000,
        )

        scores = score_run(result, run.task_dir, skip_llm=True, strict=False)

        assert scores["degraded"] is True
        assert "static" in scores["failed_scorers"]
        assert scores["static"] is None
        assert scores["composite"] is None
        assert scores["token_efficiency"] is None


# ---------------------------------------------------------------------------
# Tests: score_all_runs() -- batch phases
# ---------------------------------------------------------------------------


class TestScoreAllRunsBatchPhases:
    """Tests for score_all_runs() batch processing."""

    @patch("claude_benchmark.scoring.pipeline.LLMJudgeScorer")
    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_batch_phases(self, mock_static_cls, mock_llm_cls, tmp_path: Path) -> None:
        """score_all_runs() processes 3 results and returns aggregation."""
        mock_static = mock_static_cls.return_value
        mock_static.score.return_value = _make_static(80.0)

        mock_llm = mock_llm_cls.return_value
        mock_llm.score.return_value = _make_llm(60.0)

        results = []
        for i in range(3):
            # Use unique subdirectory per run to avoid path conflicts
            sub = tmp_path / f"run{i}"
            sub.mkdir()
            results.append(
                _make_run_result(sub, task_name="test-task", run_number=i + 1)
            )

        scored_results, aggregation = score_all_runs(
            results, skip_llm=False, strict=False
        )

        # All 3 should be scored
        scored_count = sum(1 for r in scored_results if r.scores is not None)
        assert scored_count == 3

        # Aggregation should have one variant key
        assert len(aggregation) == 1
        key = list(aggregation.keys())[0]
        assert "test-task" in key
        assert "scores" in aggregation[key]


# ---------------------------------------------------------------------------
# Tests: score_all_runs() -- skips failed runs
# ---------------------------------------------------------------------------


class TestScoreAllRunsSkipsFailedRuns:
    """Tests that score_all_runs() only scores successful runs."""

    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_skips_failed_runs(self, mock_static_cls, tmp_path: Path) -> None:
        """Only successful runs are scored; failed runs are left untouched."""
        mock_static = mock_static_cls.return_value
        mock_static.score.return_value = _make_static(80.0)

        sub1 = tmp_path / "run1"
        sub1.mkdir()
        success_result = _make_run_result(sub1, task_name="test-task", run_number=1)

        sub2 = tmp_path / "run2"
        sub2.mkdir()
        fail_run = _make_benchmark_run(sub2, task_name="test-task")
        fail_result = RunResult(
            run=fail_run,
            status="failure",
            error="Something broke",
        )

        scored_results, aggregation = score_all_runs(
            [success_result, fail_result], skip_llm=True, strict=False
        )

        # Only 1 scored
        scored = [r for r in scored_results if r.scores is not None]
        assert len(scored) == 1
        assert scored[0].run.run_number == 1

        # Failed result untouched
        assert fail_result.scores is None


# ---------------------------------------------------------------------------
# Tests: score_all_runs() -- aggregation
# ---------------------------------------------------------------------------


class TestScoreAllRunsAggregation:
    """Tests for per-variant aggregation in score_all_runs()."""

    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_aggregation(self, mock_static_cls, tmp_path: Path) -> None:
        """3 results for same variant produce aggregation with n=3."""
        mock_static = mock_static_cls.return_value
        mock_static.score.return_value = _make_static(80.0)

        results = []
        for i in range(3):
            sub = tmp_path / f"run{i}"
            sub.mkdir()
            results.append(
                _make_run_result(
                    sub,
                    task_name="test-task",
                    profile_name="test-profile",
                    model="test-model",
                    run_number=i + 1,
                )
            )

        scored_results, aggregation = score_all_runs(
            results, skip_llm=True, strict=False
        )

        assert len(aggregation) == 1
        key = "test-task|test-profile|test-model"
        assert key in aggregation

        scores_agg = aggregation[key]["scores"]
        assert "composite" in scores_agg
        assert scores_agg["composite"]["n"] == 3
        assert scores_agg["composite"]["mean"] == 80.0  # All static-only at 80
        assert scores_agg["composite"]["stdev"] == 0.0  # All same value


# ---------------------------------------------------------------------------
# Tests: token efficiency
# ---------------------------------------------------------------------------


class TestTokenEfficiency:
    """Tests for token efficiency computation in the pipeline."""

    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_token_efficiency_computed(self, mock_static_cls, tmp_path: Path) -> None:
        """Token efficiency uses profile path content and result.total_tokens."""
        mock_static = mock_static_cls.return_value
        mock_static.score.return_value = _make_static(80.0)

        run = _make_benchmark_run(tmp_path)
        output_dir = _make_output_dir(tmp_path)
        result = RunResult(
            run=run,
            status="success",
            output_dir=output_dir,
            total_tokens=5000,
        )

        scores = score_run(result, run.task_dir, skip_llm=True)

        te = scores["token_efficiency"]
        assert te is not None
        assert te["composite_score"] == 80.0
        # Profile text is "# Test Profile\n\nSome instructions for Claude.\n"
        # ~45 chars / 4 = ~11 tokens
        assert te["claudemd_tokens"] > 0
        assert te["task_io_tokens"] == 5000
        assert te["points_per_1k_tokens"] > 0


# ---------------------------------------------------------------------------
# Tests: score_all_runs() -- progress callback
# ---------------------------------------------------------------------------


class TestScoreAllRunsProgressCallback:
    """Tests for ScoringProgressCallback in score_all_runs()."""

    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_progress_callback(self, mock_static_cls, tmp_path: Path) -> None:
        """Progress callback receives started/progress/completed for each phase."""
        mock_static = mock_static_cls.return_value
        mock_static.score.return_value = _make_static(80.0)

        sub = tmp_path / "run1"
        sub.mkdir()
        result = _make_run_result(sub, task_name="test-task")

        # Create a mock progress callback
        mock_progress = MagicMock(spec=["scoring_started", "scoring_progress", "scoring_completed"])

        score_all_runs(
            [result], skip_llm=True, strict=False, progress=mock_progress
        )

        # Verify static phase callbacks
        mock_progress.scoring_started.assert_any_call("static", 1)
        mock_progress.scoring_progress.assert_any_call("static", 1, 1, result.run.result_key)
        mock_progress.scoring_completed.assert_any_call("static")

        # Verify composite phase callbacks
        mock_progress.scoring_started.assert_any_call("composite", 1)
        mock_progress.scoring_progress.assert_any_call("composite", 1, 1, result.run.result_key)
        mock_progress.scoring_completed.assert_any_call("composite")

    @patch("claude_benchmark.scoring.pipeline.LLMJudgeScorer")
    @patch("claude_benchmark.scoring.pipeline.StaticScorer")
    def test_progress_callback_with_llm(
        self, mock_static_cls, mock_llm_cls, tmp_path: Path
    ) -> None:
        """Progress callback also receives LLM phase when skip_llm=False."""
        mock_static = mock_static_cls.return_value
        mock_static.score.return_value = _make_static(80.0)

        mock_llm = mock_llm_cls.return_value
        mock_llm.score.return_value = _make_llm(60.0)

        sub = tmp_path / "run1"
        sub.mkdir()
        result = _make_run_result(sub, task_name="test-task")

        mock_progress = MagicMock(spec=["scoring_started", "scoring_progress", "scoring_completed"])

        score_all_runs(
            [result], skip_llm=False, strict=False, progress=mock_progress
        )

        # Verify all three phases
        started_calls = [c.args[0] for c in mock_progress.scoring_started.call_args_list]
        assert "static" in started_calls
        assert "llm" in started_calls
        assert "composite" in started_calls


# ---------------------------------------------------------------------------
# Tests: ScoringProgressCallback protocol
# ---------------------------------------------------------------------------


class TestScoringProgressCallbackProtocol:
    """Tests that the ScoringProgressCallback protocol is properly defined."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """ScoringProgressCallback is runtime_checkable."""

        class ValidCallback:
            def scoring_started(self, phase: str, total: int) -> None:
                pass

            def scoring_progress(
                self, phase: str, completed: int, total: int, run_key: str
            ) -> None:
                pass

            def scoring_completed(self, phase: str) -> None:
                pass

        cb = ValidCallback()
        assert isinstance(cb, ScoringProgressCallback)
