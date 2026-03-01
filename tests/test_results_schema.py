from datetime import datetime
import json

from claude_benchmark.results.schema import (
    AggregateResult,
    BenchmarkManifest,
    RunResult,
    StatsSummary,
    TokenUsage,
)


def test_run_result_with_all_fields_validates():
    usage = TokenUsage(
        input_tokens=100,
        output_tokens=200,
        cache_creation_input_tokens=10,
        cache_read_input_tokens=20,
    )
    result = RunResult(
        run_number=1,
        success=True,
        wall_clock_seconds=1.5,
        duration_ms=1500,
        duration_api_ms=1400,
        total_cost_usd=0.05,
        num_turns=3,
        session_id="test-session",
        usage=usage,
        output_files={"main.py": "def test(): pass"},
        error=None,
        timestamp=datetime.now(),
    )
    assert result.run_number == 1
    assert result.success is True
    assert result.wall_clock_seconds == 1.5
    assert result.usage.input_tokens == 100


def test_run_result_with_failure_and_error_validates():
    result = RunResult(
        run_number=2,
        success=False,
        wall_clock_seconds=0.5,
        error="Timeout occurred",
    )
    assert result.run_number == 2
    assert result.success is False
    assert result.error == "Timeout occurred"
    assert result.usage is None


def test_run_result_with_minimal_fields_validates():
    result = RunResult(
        run_number=1,
        success=True,
        wall_clock_seconds=2.0,
    )
    assert result.run_number == 1
    assert result.success is True
    assert result.wall_clock_seconds == 2.0
    assert result.duration_ms == 0
    assert result.num_turns == 0
    assert result.output_files == {}


def test_token_usage_with_defaults_validates():
    usage = TokenUsage(input_tokens=50, output_tokens=100)
    assert usage.input_tokens == 50
    assert usage.output_tokens == 100
    assert usage.cache_creation_input_tokens == 0
    assert usage.cache_read_input_tokens == 0


def test_aggregate_result_serializes_to_json_and_back():
    aggregate = AggregateResult(
        task_name="test-task",
        profile_name="default",
        model="claude-opus-4",
        total_runs=5,
        successful_runs=4,
        failed_runs=1,
        success_rate=0.8,
        wall_clock=StatsSummary(mean=1.5, variance=0.1, stdev=0.316),
        failed_details=["Error 1"],
    )

    json_str = aggregate.model_dump_json()
    parsed = json.loads(json_str)

    assert parsed["task_name"] == "test-task"
    assert parsed["success_rate"] == 0.8
    assert parsed["wall_clock"]["mean"] == 1.5

    roundtrip = AggregateResult.model_validate(parsed)
    assert roundtrip.task_name == "test-task"
    assert roundtrip.success_rate == 0.8


def test_benchmark_manifest_validates():
    manifest = BenchmarkManifest(
        timestamp=datetime.now(),
        models=["claude-opus-4"],
        profiles=["default", "strict"],
        tasks=["task1", "task2"],
        runs_per_combination=5,
        total_combinations=4,
        total_runs=20,
        cli_args={"--verbose": "true"},
    )
    assert len(manifest.models) == 1
    assert len(manifest.profiles) == 2
    assert manifest.total_runs == 20


def test_stats_summary_stores_values_correctly():
    stats = StatsSummary(mean=10.5, variance=2.25, stdev=1.5)
    assert stats.mean == 10.5
    assert stats.variance == 2.25
    assert stats.stdev == 1.5
