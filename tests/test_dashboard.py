"""Tests for Dashboard and LogLineOutput progress display implementations.

Tests verify:
- Dashboard state management (completed, failed, workers dict)
- Dashboard rendering produces correct Rich renderables
- Scoring progress bar lifecycle (started, progress, completed)
- run_scoring_with_display Live context management
- LogLineOutput prints correctly formatted timestamped lines
- Both implementations satisfy the ProgressCallback interface
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Group

from claude_benchmark.execution.dashboard import Dashboard
from claude_benchmark.execution.logger import LogLineOutput


# ---------------------------------------------------------------------------
# Mock data objects matching the ProgressCallback protocol expectations
# ---------------------------------------------------------------------------


@dataclass
class MockBenchmarkRun:
    """Minimal BenchmarkRun mock with required attributes."""

    task_name: str = "code-gen-01"
    profile_name: str = "empty"
    model: str = "sonnet"
    run_number: int = 1


@dataclass
class MockRunResult:
    """Minimal RunResult mock with required attributes."""

    total_tokens: int = 1500
    cost: float = 0.0045
    status: str = "success"


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------


class TestDashboardInit:
    """Test Dashboard initialization."""

    def test_initializes_with_correct_totals(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        assert dashboard.total_runs == 10
        assert dashboard.concurrency == 3

    def test_initializes_counters_to_zero(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        assert dashboard.completed == 0
        assert dashboard.failed == 0

    def test_initializes_empty_workers(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        assert dashboard.workers == {}

    def test_creates_progress_with_overall_task(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        assert dashboard.progress is not None
        assert dashboard.overall_task is not None


class TestDashboardWorkerStarted:
    """Test Dashboard.worker_started updates worker status."""

    def test_updates_worker_status_text(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run = MockBenchmarkRun(
            task_name="code-gen-01", profile_name="empty", model="sonnet"
        )
        dashboard.worker_started(0, run)
        assert dashboard.workers[0] == "code-gen-01 | empty | sonnet"

    def test_updates_different_workers(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run1 = MockBenchmarkRun(
            task_name="code-gen-01", profile_name="empty", model="sonnet"
        )
        run2 = MockBenchmarkRun(
            task_name="refactor-02", profile_name="large", model="opus"
        )
        dashboard.worker_started(0, run1)
        dashboard.worker_started(1, run2)
        assert dashboard.workers[0] == "code-gen-01 | empty | sonnet"
        assert dashboard.workers[1] == "refactor-02 | large | opus"

    def test_overwrites_previous_worker_status(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run1 = MockBenchmarkRun(task_name="task-a", profile_name="p1", model="haiku")
        run2 = MockBenchmarkRun(task_name="task-b", profile_name="p2", model="sonnet")
        dashboard.worker_started(0, run1)
        dashboard.worker_started(0, run2)
        assert dashboard.workers[0] == "task-b | p2 | sonnet"


class TestDashboardRunCompleted:
    """Test Dashboard.run_completed increments completed and shows checkmark."""

    def test_increments_completed_count(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run = MockBenchmarkRun()
        result = MockRunResult()
        dashboard.run_completed(0, run, result)
        assert dashboard.completed == 1

    def test_shows_checkmark_in_worker_status(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run = MockBenchmarkRun(task_name="code-gen-01")
        result = MockRunResult()
        dashboard.run_completed(0, run, result)
        assert "\u2713" in dashboard.workers[0]
        assert "code-gen-01" in dashboard.workers[0]

    def test_does_not_increment_failed(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run = MockBenchmarkRun()
        result = MockRunResult()
        dashboard.run_completed(0, run, result)
        assert dashboard.failed == 0

    def test_multiple_completions_increment(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        for i in range(3):
            run = MockBenchmarkRun(task_name=f"task-{i}")
            result = MockRunResult()
            dashboard.run_completed(i % 3, run, result)
        assert dashboard.completed == 3


class TestDashboardRunFailed:
    """Test Dashboard.run_failed increments completed+failed and shows X."""

    def test_increments_completed_and_failed(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run = MockBenchmarkRun()
        error = RuntimeError("API error")
        dashboard.run_failed(0, run, error)
        assert dashboard.completed == 1
        assert dashboard.failed == 1

    def test_shows_x_in_worker_status(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run = MockBenchmarkRun(task_name="code-gen-01")
        error = RuntimeError("timeout")
        dashboard.run_failed(0, run, error)
        assert "\u2717" in dashboard.workers[0]
        assert "code-gen-01" in dashboard.workers[0]

    def test_mixed_success_and_failure(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run = MockBenchmarkRun()
        result = MockRunResult()
        error = RuntimeError("fail")

        dashboard.run_completed(0, run, result)
        dashboard.run_failed(1, run, error)
        dashboard.run_completed(2, run, result)

        assert dashboard.completed == 3
        assert dashboard.failed == 1


class TestDashboardRender:
    """Test Dashboard._render returns a Group with progress and table."""

    def test_returns_group(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        renderable = dashboard._render()
        assert isinstance(renderable, Group)

    def test_render_after_worker_started(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        run = MockBenchmarkRun(
            task_name="code-gen-01", profile_name="empty", model="sonnet"
        )
        dashboard.worker_started(0, run)
        # Should not raise
        renderable = dashboard._render()
        assert isinstance(renderable, Group)

    def test_render_with_all_workers_active(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        for i in range(3):
            run = MockBenchmarkRun(
                task_name=f"task-{i}", profile_name="prof", model="haiku"
            )
            dashboard.worker_started(i, run)
        renderable = dashboard._render()
        assert isinstance(renderable, Group)


# ---------------------------------------------------------------------------
# Scoring display tests
# ---------------------------------------------------------------------------


class TestDashboardScoringStarted:
    """Test scoring_started creates progress task and resets between phases."""

    def test_creates_scoring_task(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        assert dashboard._scoring_task_id is not None
        assert dashboard.scoring_phase == "Static analysis"
        assert dashboard.scoring_total == 5
        assert dashboard.scoring_completed_count == 0

    def test_resets_between_phases(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        first_task_id = dashboard._scoring_task_id
        dashboard.scoring_started("llm", 5)
        second_task_id = dashboard._scoring_task_id
        # New task created (old one removed)
        assert second_task_id is not None
        assert second_task_id != first_task_id
        assert dashboard.scoring_phase == "LLM judging"

    def test_clears_current_run(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_current_run = "leftover"
        dashboard.scoring_started("composite", 3)
        assert dashboard.scoring_current_run == ""


class TestDashboardScoringProgress:
    """Test scoring_progress updates bar state."""

    def test_updates_completed_count_and_run_key(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        dashboard.scoring_progress("static", 3, 5, "task-a|prof|sonnet:1")
        assert dashboard.scoring_completed_count == 3
        assert dashboard.scoring_current_run == "task-a|prof|sonnet:1"

    def test_advances_progress_bar(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        dashboard.scoring_progress("static", 2, 5, "run-key")
        task = dashboard._scoring_progress.tasks[0]
        assert task.completed == 2


class TestDashboardScoringCompleted:
    """Test scoring_completed clears phase state."""

    def test_clears_phase_and_run(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        dashboard.scoring_progress("static", 3, 5, "some-run")
        dashboard.scoring_completed("static")
        assert dashboard.scoring_phase is None
        assert dashboard.scoring_current_run == ""

    def test_marks_task_complete(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        dashboard.scoring_completed("static")
        task = dashboard._scoring_progress.tasks[0]
        assert task.completed == 5


class TestDashboardRenderScoring:
    """Test _render_scoring returns a Group."""

    def test_returns_group(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        renderable = dashboard._render_scoring()
        assert isinstance(renderable, Group)

    def test_includes_run_label_when_set(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        dashboard.scoring_current_run = "task-a|prof|sonnet:1"
        renderable = dashboard._render_scoring()
        assert isinstance(renderable, Group)


class TestDashboardRunScoringWithDisplay:
    """Test run_scoring_with_display Live context lifecycle."""

    def test_returns_score_fn_result(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        # Force is_terminal so Live actually opens
        dashboard.console = MagicMock()
        dashboard.console.is_terminal = True

        sentinel = (["results"], {"agg": "data"})

        def fake_score(cb):
            return sentinel

        result = dashboard.run_scoring_with_display(fake_score)
        assert result is sentinel

    def test_passes_dashboard_as_callback(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.console = MagicMock()
        dashboard.console.is_terminal = True

        received = []

        def fake_score(cb):
            received.append(cb)
            return None

        dashboard.run_scoring_with_display(fake_score)
        assert received[0] is dashboard

    def test_cleans_up_live_and_flag(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.console = MagicMock()
        dashboard.console.is_terminal = True

        def fake_score(cb):
            # During execution, _live should be set
            assert dashboard._live is not None
            assert dashboard._scoring_display_active is True
            return None

        dashboard.run_scoring_with_display(fake_score)
        assert dashboard._live is None
        assert dashboard._scoring_display_active is False

    def test_cleans_up_on_exception(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.console = MagicMock()
        dashboard.console.is_terminal = True

        def failing_score(cb):
            raise ValueError("scoring error")

        with pytest.raises(ValueError, match="scoring error"):
            dashboard.run_scoring_with_display(failing_score)
        assert dashboard._live is None
        assert dashboard._scoring_display_active is False


class TestDashboardRefreshLiveDispatch:
    """Test _refresh_live uses correct renderer based on _scoring_display_active."""

    def test_uses_execution_renderer_by_default(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        mock_live = MagicMock()
        dashboard._live = mock_live
        dashboard._scoring_display_active = False

        dashboard._refresh_live()

        mock_live.update.assert_called_once()
        # Should have called _render() which includes worker table
        rendered = mock_live.update.call_args[0][0]
        assert isinstance(rendered, Group)

    def test_uses_scoring_renderer_when_active(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard.scoring_started("static", 5)
        mock_live = MagicMock()
        dashboard._live = mock_live
        dashboard._scoring_display_active = True

        dashboard._refresh_live()

        mock_live.update.assert_called_once()
        rendered = mock_live.update.call_args[0][0]
        assert isinstance(rendered, Group)

    def test_noop_when_live_is_none(self) -> None:
        dashboard = Dashboard(total_runs=5, concurrency=2)
        dashboard._live = None
        # Should not raise
        dashboard._refresh_live()


# ---------------------------------------------------------------------------
# LogLineOutput tests
# ---------------------------------------------------------------------------


class TestLogLineOutputWorkerStarted:
    """Test LogLineOutput.worker_started prints START line."""

    def test_prints_start_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = LogLineOutput()
        run = MockBenchmarkRun(
            task_name="code-gen-01",
            profile_name="empty",
            model="sonnet",
            run_number=1,
        )
        logger.worker_started(0, run)
        captured = capsys.readouterr()
        assert "START" in captured.out
        assert "sonnet" in captured.out
        assert "empty" in captured.out
        assert "code-gen-01" in captured.out
        assert "run 1" in captured.out

    def test_includes_timestamp(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = LogLineOutput()
        run = MockBenchmarkRun()
        logger.worker_started(0, run)
        captured = capsys.readouterr()
        # Timestamp format: [HH:MM:SS]
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\]", captured.out)


class TestLogLineOutputRunCompleted:
    """Test LogLineOutput.run_completed prints DONE line."""

    def test_prints_done_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = LogLineOutput()
        run = MockBenchmarkRun(
            task_name="code-gen-01",
            profile_name="empty",
            model="sonnet",
            run_number=2,
        )
        result = MockRunResult(total_tokens=1500, cost=0.0045)
        logger.run_completed(0, run, result)
        captured = capsys.readouterr()
        assert "DONE" in captured.out
        assert "sonnet" in captured.out
        assert "empty" in captured.out
        assert "code-gen-01" in captured.out
        assert "run 2" in captured.out
        assert "1500 tok" in captured.out
        assert "$0.0045" in captured.out

    def test_includes_timestamp(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = LogLineOutput()
        run = MockBenchmarkRun()
        result = MockRunResult()
        logger.run_completed(0, run, result)
        captured = capsys.readouterr()
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\]", captured.out)


class TestLogLineOutputRunFailed:
    """Test LogLineOutput.run_failed prints FAIL line."""

    def test_prints_fail_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = LogLineOutput()
        run = MockBenchmarkRun(
            task_name="code-gen-01",
            profile_name="empty",
            model="sonnet",
            run_number=3,
        )
        error = RuntimeError("API rate limit exceeded")
        logger.run_failed(0, run, error)
        captured = capsys.readouterr()
        assert "FAIL" in captured.out
        assert "sonnet" in captured.out
        assert "empty" in captured.out
        assert "code-gen-01" in captured.out
        assert "run 3" in captured.out
        assert "API rate limit exceeded" in captured.out

    def test_includes_timestamp(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = LogLineOutput()
        run = MockBenchmarkRun()
        error = RuntimeError("fail")
        logger.run_failed(0, run, error)
        captured = capsys.readouterr()
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\]", captured.out)


class TestLogLineOutputSummary:
    """Test LogLineOutput.summary prints completion summary."""

    def test_prints_summary_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = LogLineOutput()
        logger.summary(total=10, succeeded=8, failed=2, cost=1.23, elapsed=45.7)
        captured = capsys.readouterr()
        assert "8/10" in captured.out
        assert "Failed: 2" in captured.out
        assert "$1.23" in captured.out
        assert "46s" in captured.out

    def test_zero_cost_formatting(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = LogLineOutput()
        logger.summary(total=5, succeeded=5, failed=0, cost=0.0, elapsed=12.0)
        captured = capsys.readouterr()
        assert "5/5" in captured.out
        assert "Failed: 0" in captured.out
        assert "$0.00" in captured.out


class TestDashboardSummary:
    """Test Dashboard.summary prints final summary."""

    def test_summary_does_not_raise(self) -> None:
        dashboard = Dashboard(total_runs=10, concurrency=3)
        # Summary prints to console -- just verify it doesn't raise
        dashboard.summary(total=10, succeeded=8, failed=2, cost=1.23, elapsed=45.0)
