"""Reporting and analysis subsystem for claude-benchmark.

Provides data models for benchmark results, raw data export (JSON/CSV),
statistical regression detection, and HTML report generation.
"""

from claude_benchmark.reporting.models import (
    BenchmarkResults,
    ProfileResult,
    ReportMetadata,
    RegressionResult,
    RunResult,
    TaskResult,
)
from claude_benchmark.reporting.exporter import export_csv, export_json, export_raw_data
from claude_benchmark.reporting.generator import ReportGenerator
from claude_benchmark.reporting.regression import (
    check_regression,
    detect_all_regressions,
    summarize_regressions,
)

__all__ = [
    "BenchmarkResults",
    "ProfileResult",
    "ReportMetadata",
    "RegressionResult",
    "ReportGenerator",
    "RunResult",
    "TaskResult",
    "check_regression",
    "detect_all_regressions",
    "export_csv",
    "export_json",
    "export_raw_data",
    "summarize_regressions",
]
