"""Tests for system resource detection and auto-concurrency computation."""

from __future__ import annotations

import pytest

from claude_benchmark.scoring.system_resources import (
    SystemSpecs,
    compute_optimal_static_concurrency,
    detect_system_specs,
    get_auto_static_concurrency,
    _MAX_WORKERS,
    _MIN_WORKERS,
)


class TestDetectSystemSpecs:
    def test_returns_positive_values(self) -> None:
        specs = detect_system_specs()
        assert specs.cpu_count >= 1
        assert specs.available_memory_gb > 0


class TestComputeOptimalStaticConcurrency:
    def test_high_cpu_machine(self) -> None:
        specs = SystemSpecs(cpu_count=16, available_memory_gb=32.0)
        result = compute_optimal_static_concurrency(specs)
        assert result == 32  # min(48, 320, 32) → capped

    def test_low_memory_constrains(self) -> None:
        specs = SystemSpecs(cpu_count=16, available_memory_gb=2.0)
        result = compute_optimal_static_concurrency(specs)
        assert result == 20  # int(2.0 / 0.1)

    def test_typical_laptop(self) -> None:
        specs = SystemSpecs(cpu_count=12, available_memory_gb=12.0)
        result = compute_optimal_static_concurrency(specs)
        assert result == 32  # min(36, 120, 32) → capped

    def test_floor_at_min_workers(self) -> None:
        specs = SystemSpecs(cpu_count=1, available_memory_gb=0.5)
        assert compute_optimal_static_concurrency(specs) >= _MIN_WORKERS

    def test_cap_at_max_workers(self) -> None:
        specs = SystemSpecs(cpu_count=128, available_memory_gb=512.0)
        assert compute_optimal_static_concurrency(specs) <= _MAX_WORKERS

    def test_zero_cpu_does_not_crash(self) -> None:
        specs = SystemSpecs(cpu_count=0, available_memory_gb=8.0)
        result = compute_optimal_static_concurrency(specs)
        assert result >= _MIN_WORKERS


class TestGetAutoStaticConcurrency:
    def test_returns_int(self) -> None:
        result = get_auto_static_concurrency()
        assert isinstance(result, int)
        assert result >= _MIN_WORKERS

    def test_logs_detection(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("INFO", logger="claude_benchmark.scoring.system_resources"):
            get_auto_static_concurrency()
        assert "Auto-detected" in caplog.text
        assert "static workers" in caplog.text
