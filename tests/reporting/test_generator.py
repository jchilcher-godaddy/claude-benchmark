"""Integration tests for ReportGenerator.

Tests the full HTML report generation pipeline: loading data, building charts,
detecting regressions, generating diffs, and rendering Jinja2 templates into
a single self-contained HTML file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from claude_benchmark.reporting.generator import ReportGenerator
from claude_benchmark.reporting.models import (
    BenchmarkResults,
    ProfileResult,
    ReportMetadata,
    RunResult,
    TaskResult,
)


def _make_sample_results(
    *,
    with_regressions: bool = False,
    single_profile: bool = False,
) -> BenchmarkResults:
    """Build sample BenchmarkResults for testing.

    Args:
        with_regressions: If True, make one profile consistently worse
            than the empty baseline to trigger regression detection.
        single_profile: If True, only include one profile.
    """
    dimensions = ["correctness", "style", "efficiency"]

    # Empty baseline profile
    empty_runs_task1 = [
        RunResult(
            profile="empty",
            task="fizzbuzz",
            model="sonnet",
            scores={"correctness": 85.0, "style": 70.0, "efficiency": 80.0},
            token_count=500,
            code_output="def fizzbuzz(n):\n    for i in range(1, n+1):\n        print(i)",
        ),
        RunResult(
            profile="empty",
            task="fizzbuzz",
            model="sonnet",
            scores={"correctness": 88.0, "style": 72.0, "efficiency": 82.0},
            token_count=520,
            code_output="def fizzbuzz(n):\n    for i in range(1, n+1):\n        print(i)",
        ),
        RunResult(
            profile="empty",
            task="fizzbuzz",
            model="sonnet",
            scores={"correctness": 83.0, "style": 68.0, "efficiency": 78.0},
            token_count=490,
            code_output="def fizzbuzz(n):\n    for i in range(1, n+1):\n        print(i)",
        ),
    ]

    empty_runs_task2 = [
        RunResult(
            profile="empty",
            task="sort_list",
            model="sonnet",
            scores={"correctness": 90.0, "style": 75.0, "efficiency": 85.0},
            token_count=400,
            code_output="def sort_list(lst):\n    return sorted(lst)",
        ),
        RunResult(
            profile="empty",
            task="sort_list",
            model="sonnet",
            scores={"correctness": 92.0, "style": 77.0, "efficiency": 87.0},
            token_count=410,
            code_output="def sort_list(lst):\n    return sorted(lst)",
        ),
        RunResult(
            profile="empty",
            task="sort_list",
            model="sonnet",
            scores={"correctness": 88.0, "style": 73.0, "efficiency": 83.0},
            token_count=390,
            code_output="def sort_list(lst):\n    return sorted(lst)",
        ),
    ]

    empty_profile = ProfileResult(
        profile_id="empty",
        profile_name="No CLAUDE.md",
        tasks={
            "fizzbuzz": TaskResult(
                task_id="fizzbuzz",
                task_name="FizzBuzz",
                runs=empty_runs_task1,
                mean_scores={"correctness": 85.3, "style": 70.0, "efficiency": 80.0},
                std_scores={"correctness": 2.5, "style": 2.0, "efficiency": 2.0},
            ),
            "sort_list": TaskResult(
                task_id="sort_list",
                task_name="Sort List",
                runs=empty_runs_task2,
                mean_scores={"correctness": 90.0, "style": 75.0, "efficiency": 85.0},
                std_scores={"correctness": 2.0, "style": 2.0, "efficiency": 2.0},
            ),
        },
        aggregate_scores={"correctness": 87.7, "style": 72.5, "efficiency": 82.5},
        total_tokens=2710,
    )

    if single_profile:
        return BenchmarkResults(
            profiles={"empty": empty_profile},
            models=["sonnet"],
            tasks=["fizzbuzz", "sort_list"],
            metadata=ReportMetadata(
                date="2026-01-15",
                models_tested=["sonnet"],
                profile_count=1,
                total_runs=6,
                wall_clock_seconds=42.5,
            ),
        )

    # Typical profile
    if with_regressions:
        # Make typical profile significantly worse on correctness
        typical_correctness_fizz = [40.0, 42.0, 38.0]
        typical_correctness_sort = [45.0, 43.0, 41.0]
    else:
        typical_correctness_fizz = [87.0, 90.0, 85.0]
        typical_correctness_sort = [91.0, 93.0, 89.0]

    typical_runs_task1 = [
        RunResult(
            profile="typical",
            task="fizzbuzz",
            model="sonnet",
            scores={
                "correctness": typical_correctness_fizz[i],
                "style": 75.0 + i,
                "efficiency": 82.0 + i,
            },
            token_count=600 + i * 10,
            code_output=(
                "def fizzbuzz(n):\n"
                "    for i in range(1, n+1):\n"
                "        if i % 15 == 0:\n"
                "            print('FizzBuzz')\n"
                "        elif i % 3 == 0:\n"
                "            print('Fizz')\n"
                "        elif i % 5 == 0:\n"
                "            print('Buzz')\n"
                "        else:\n"
                "            print(i)\n"
            ),
        )
        for i in range(3)
    ]

    typical_runs_task2 = [
        RunResult(
            profile="typical",
            task="sort_list",
            model="sonnet",
            scores={
                "correctness": typical_correctness_sort[i],
                "style": 78.0 + i,
                "efficiency": 86.0 + i,
            },
            token_count=450 + i * 10,
            code_output=(
                "def sort_list(lst: list) -> list:\n"
                "    return sorted(lst)\n"
            ),
        )
        for i in range(3)
    ]

    typical_profile = ProfileResult(
        profile_id="typical",
        profile_name="Typical CLAUDE.md",
        tasks={
            "fizzbuzz": TaskResult(
                task_id="fizzbuzz",
                task_name="FizzBuzz",
                runs=typical_runs_task1,
                mean_scores={
                    "correctness": sum(typical_correctness_fizz) / 3,
                    "style": 76.0,
                    "efficiency": 83.0,
                },
                std_scores={"correctness": 2.5, "style": 1.0, "efficiency": 1.0},
            ),
            "sort_list": TaskResult(
                task_id="sort_list",
                task_name="Sort List",
                runs=typical_runs_task2,
                mean_scores={
                    "correctness": sum(typical_correctness_sort) / 3,
                    "style": 79.0,
                    "efficiency": 87.0,
                },
                std_scores={"correctness": 2.0, "style": 1.0, "efficiency": 1.0},
            ),
        },
        aggregate_scores={
            "correctness": (sum(typical_correctness_fizz) + sum(typical_correctness_sort)) / 6,
            "style": 77.5,
            "efficiency": 85.0,
        },
        total_tokens=3180,
    )

    return BenchmarkResults(
        profiles={"empty": empty_profile, "typical": typical_profile},
        models=["sonnet"],
        tasks=["fizzbuzz", "sort_list"],
        metadata=ReportMetadata(
            date="2026-01-15",
            models_tested=["sonnet"],
            profile_count=2,
            total_runs=12,
            wall_clock_seconds=85.3,
        ),
    )


def _write_results_json(results: BenchmarkResults, results_dir: Path) -> None:
    """Write BenchmarkResults to results.json in the given directory."""
    results_dir.mkdir(parents=True, exist_ok=True)
    data = results.to_export_dict()
    (results_dir / "results.json").write_text(
        json.dumps(data, indent=2, default=str), encoding="utf-8"
    )


class TestReportGeneratorGenerate:
    """Tests for ReportGenerator.generate() producing a complete HTML report."""

    def test_generates_html_file(self, tmp_path: Path) -> None:
        """generate() produces an HTML file at the specified output path."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "output" / "report.html")

        assert output.exists()
        assert output.suffix == ".html"
        assert output.stat().st_size > 1000  # Non-trivial content

    def test_html_contains_sidebar_navigation(self, tmp_path: Path) -> None:
        """Generated HTML includes sticky sidebar with section links."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert '<nav class="sidebar">' in html
        assert 'href="#summary"' in html
        assert 'href="#dashboard"' in html
        assert 'href="#comparison"' in html
        assert 'href="#raw-data"' in html

    def test_html_contains_all_sections(self, tmp_path: Path) -> None:
        """Generated HTML includes all 5 report sections."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert 'id="summary"' in html
        assert 'id="dashboard"' in html
        assert 'id="detailed"' in html
        assert 'id="comparison"' in html
        assert 'id="raw-data"' in html

    def test_html_contains_inlined_chartjs(self, tmp_path: Path) -> None:
        """Chart.js is inlined in the HTML (no external script references)."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        # Chart.js source should be inlined
        assert "Chart(" in html or "Chart" in html
        assert "CHART_CONFIGS" in html

    def test_html_contains_benchmark_data_json(self, tmp_path: Path) -> None:
        """Benchmark data is embedded as JSON in script tags."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert "BENCHMARK_DATA" in html
        assert "CHART_CONFIGS" in html

    def test_html_is_self_contained(self, tmp_path: Path) -> None:
        """Generated HTML has no external href/src references (works offline)."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        # Should not have any external resource references
        # (no href to .css files, no src to .js files from CDN)
        external_refs = re.findall(r'(?:src|href)="https?://[^"]*"', html)
        assert len(external_refs) == 0, f"Found external references: {external_refs}"

    def test_json_and_csv_created_alongside(self, tmp_path: Path) -> None:
        """JSON and CSV export files are created alongside the HTML report."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output_dir = tmp_path / "output"
        gen.generate(output_dir / "report.html")

        assert (output_dir / "benchmark-results.json").exists()
        assert (output_dir / "benchmark-results.csv").exists()

    def test_download_buttons_present(self, tmp_path: Path) -> None:
        """Raw data section has download button functions."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert "downloadJSON" in html
        assert "downloadCSV" in html
        assert "downloadFile" in html

    def test_metadata_banner(self, tmp_path: Path) -> None:
        """Metadata banner displays benchmark context information."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert "2026-01-15" in html  # date
        assert "sonnet" in html  # model
        assert "metadata-banner" in html


class TestReportGeneratorRegressions:
    """Tests for regression callout rendering."""

    def test_regression_callout_present(self, tmp_path: Path) -> None:
        """When regressions exist, HTML contains regression callout."""
        results = _make_sample_results(with_regressions=True)
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert "regression-callout" in html
        assert "Regressions Detected" in html

    def test_no_regression_shows_success(self, tmp_path: Path) -> None:
        """When no regressions, HTML shows success message."""
        results = _make_sample_results(with_regressions=False)
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert "success-callout" in html
        assert "No Regressions Detected" in html

    def test_regression_badges_in_detailed(self, tmp_path: Path) -> None:
        """Regression badges appear in detailed scores section for affected items."""
        results = _make_sample_results(with_regressions=True)
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert "badge-regression" in html


class TestReportGeneratorSingleProfile:
    """Tests for edge case: single profile."""

    def test_single_profile_generates(self, tmp_path: Path) -> None:
        """Report generates successfully with only one profile."""
        results = _make_sample_results(single_profile=True)
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")

        assert output.exists()
        html = output.read_text(encoding="utf-8")
        assert 'id="summary"' in html
        assert 'id="dashboard"' in html

    def test_single_profile_hides_comparison(self, tmp_path: Path) -> None:
        """Comparison section shows info note for single profile."""
        results = _make_sample_results(single_profile=True)
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(tmp_path / "report.html")
        html = output.read_text(encoding="utf-8")

        assert "info-note" in html
        assert "at least two profiles" in html


class TestReportGeneratorCLISummary:
    """Tests for CLI regression summary printing."""

    def test_cli_summary_output(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """print_cli_summary outputs regression summary to stdout."""
        results = _make_sample_results(with_regressions=True)
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        data = gen._load_benchmark_data()

        from claude_benchmark.reporting.regression import detect_all_regressions
        regressions = detect_all_regressions(data, baseline_profile="empty")

        gen.print_cli_summary(regressions)

        captured = capsys.readouterr()
        assert "Regression Summary" in captured.out

    def test_cli_summary_no_regressions(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """print_cli_summary shows 'No regressions' when none detected."""
        gen = ReportGenerator(tmp_path)
        gen.print_cli_summary([])

        captured = capsys.readouterr()
        assert "No regressions detected" in captured.out


class TestReportGeneratorLoadData:
    """Tests for data loading and error handling."""

    def test_missing_results_file_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError when results.json doesn't exist."""
        gen = ReportGenerator(tmp_path)
        with pytest.raises(FileNotFoundError, match="results.json"):
            gen._load_benchmark_data()

    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        """ValueError when results.json contains invalid data."""
        (tmp_path / "results.json").write_text("{invalid json", encoding="utf-8")
        gen = ReportGenerator(tmp_path)
        with pytest.raises(ValueError, match="Failed to parse"):
            gen._load_benchmark_data()

    def test_valid_results_load(self, tmp_path: Path) -> None:
        """Successfully loads and parses valid results.json."""
        results = _make_sample_results()
        _write_results_json(results, tmp_path)

        gen = ReportGenerator(tmp_path)
        loaded = gen._load_benchmark_data()

        assert len(loaded.profiles) == 2
        assert "empty" in loaded.profiles
        assert "typical" in loaded.profiles


def _make_multi_category_results() -> BenchmarkResults:
    """Build results with multiple task categories and multiple models.

    Creates bug-fix-01, bug-fix-02, refactor-01 tasks across haiku and sonnet
    models with two profiles (empty, typical). Designed so that 'empty' wins
    bug-fix category and 'typical' wins refactor category overall.
    """
    profiles: dict[str, ProfileResult] = {}

    # Profile: empty — strong on bug-fix, weaker on refactor
    empty_tasks = {
        "bug-fix-01": TaskResult(
            task_id="bug-fix-01",
            task_name="Bug Fix 01",
            runs=[
                RunResult(profile="empty", task="bug-fix-01", model="haiku",
                          scores={"correctness": 92.0, "style": 80.0}, token_count=400,
                          code_output="fix1"),
                RunResult(profile="empty", task="bug-fix-01", model="sonnet",
                          scores={"correctness": 94.0, "style": 82.0}, token_count=500,
                          code_output="fix1"),
            ],
            mean_scores={"correctness": 93.0, "style": 81.0},
            std_scores={"correctness": 1.0, "style": 1.0},
        ),
        "bug-fix-02": TaskResult(
            task_id="bug-fix-02",
            task_name="Bug Fix 02",
            runs=[
                RunResult(profile="empty", task="bug-fix-02", model="haiku",
                          scores={"correctness": 90.0, "style": 78.0}, token_count=420,
                          code_output="fix2"),
                RunResult(profile="empty", task="bug-fix-02", model="sonnet",
                          scores={"correctness": 91.0, "style": 79.0}, token_count=510,
                          code_output="fix2"),
            ],
            mean_scores={"correctness": 90.5, "style": 78.5},
            std_scores={"correctness": 0.5, "style": 0.5},
        ),
        "refactor-01": TaskResult(
            task_id="refactor-01",
            task_name="Refactor 01",
            runs=[
                RunResult(profile="empty", task="refactor-01", model="haiku",
                          scores={"correctness": 70.0, "style": 65.0}, token_count=600,
                          code_output="ref1"),
                RunResult(profile="empty", task="refactor-01", model="sonnet",
                          scores={"correctness": 72.0, "style": 67.0}, token_count=700,
                          code_output="ref1"),
            ],
            mean_scores={"correctness": 71.0, "style": 66.0},
            std_scores={"correctness": 1.0, "style": 1.0},
        ),
    }
    profiles["empty"] = ProfileResult(
        profile_id="empty",
        profile_name="No CLAUDE.md",
        tasks=empty_tasks,
        aggregate_scores={"correctness": 84.8, "style": 75.2},
        total_tokens=3130,
    )

    # Profile: typical — weaker on bug-fix, strong on refactor
    typical_tasks = {
        "bug-fix-01": TaskResult(
            task_id="bug-fix-01",
            task_name="Bug Fix 01",
            runs=[
                RunResult(profile="typical", task="bug-fix-01", model="haiku",
                          scores={"correctness": 85.0, "style": 82.0}, token_count=450,
                          code_output="fix1t"),
                RunResult(profile="typical", task="bug-fix-01", model="sonnet",
                          scores={"correctness": 88.0, "style": 84.0}, token_count=550,
                          code_output="fix1t"),
            ],
            mean_scores={"correctness": 86.5, "style": 83.0},
            std_scores={"correctness": 1.5, "style": 1.0},
        ),
        "bug-fix-02": TaskResult(
            task_id="bug-fix-02",
            task_name="Bug Fix 02",
            runs=[
                RunResult(profile="typical", task="bug-fix-02", model="haiku",
                          scores={"correctness": 83.0, "style": 80.0}, token_count=460,
                          code_output="fix2t"),
                RunResult(profile="typical", task="bug-fix-02", model="sonnet",
                          scores={"correctness": 86.0, "style": 81.0}, token_count=560,
                          code_output="fix2t"),
            ],
            mean_scores={"correctness": 84.5, "style": 80.5},
            std_scores={"correctness": 1.5, "style": 0.5},
        ),
        "refactor-01": TaskResult(
            task_id="refactor-01",
            task_name="Refactor 01",
            runs=[
                RunResult(profile="typical", task="refactor-01", model="haiku",
                          scores={"correctness": 88.0, "style": 85.0}, token_count=650,
                          code_output="ref1t"),
                RunResult(profile="typical", task="refactor-01", model="sonnet",
                          scores={"correctness": 90.0, "style": 88.0}, token_count=750,
                          code_output="ref1t"),
            ],
            mean_scores={"correctness": 89.0, "style": 86.5},
            std_scores={"correctness": 1.0, "style": 1.5},
        ),
    }
    profiles["typical"] = ProfileResult(
        profile_id="typical",
        profile_name="Typical CLAUDE.md",
        tasks=typical_tasks,
        aggregate_scores={"correctness": 86.7, "style": 83.2},
        total_tokens=3420,
    )

    return BenchmarkResults(
        profiles=profiles,
        models=["haiku", "sonnet"],
        tasks=["bug-fix-01", "bug-fix-02", "refactor-01"],
        metadata=ReportMetadata(
            date="2026-02-28",
            models_tested=["haiku", "sonnet"],
            profile_count=2,
            total_runs=12,
            wall_clock_seconds=120.0,
        ),
    )


class TestVariantAnalysis:
    """Tests for variant analysis insights in the executive summary."""

    def test_task_category_derivation(self) -> None:
        """_task_category strips numeric suffix correctly."""
        cat = ReportGenerator._task_category
        assert cat("bug-fix-01") == "bug-fix"
        assert cat("refactor-03") == "refactor"
        assert cat("instruction-following-12") == "instruction-following"
        # No numeric suffix — returns full name
        assert cat("fizzbuzz") == "fizzbuzz"
        assert cat("sort_list") == "sort_list"
        # Suffix is not purely digits
        assert cat("task-abc") == "task-abc"

    def test_category_analysis_structure(self, tmp_path: Path) -> None:
        """Multi-category results return correct winners and scores."""
        results = _make_multi_category_results()
        gen = ReportGenerator(tmp_path)

        # Determine best_profile_overall via the generator's own method
        _, _, _, _, _, _, qbm = gen._extract_chart_data(results)
        best_overall, _ = gen._find_best_profile_overall(qbm)

        analysis = gen._compute_category_variant_analysis(results, best_overall)

        assert len(analysis) == 2  # bug-fix and refactor
        categories = {a["category"] for a in analysis}
        assert categories == {"bug-fix", "refactor"}

        bug_fix = next(a for a in analysis if a["category"] == "bug-fix")
        refactor = next(a for a in analysis if a["category"] == "refactor")

        # empty has higher scores on bug-fix tasks
        assert bug_fix["winner"] == "empty"
        assert bug_fix["task_count"] == 2
        assert bug_fix["winner_score"] > bug_fix["runner_up_score"]
        assert bug_fix["margin"] > 0
        assert bug_fix["spread"] > 0

        # typical has higher scores on refactor tasks
        assert refactor["winner"] == "typical"
        assert refactor["task_count"] == 1

    def test_category_analysis_flags_exceptions(self, tmp_path: Path) -> None:
        """Exception flag is set when category winner != overall winner."""
        results = _make_multi_category_results()
        gen = ReportGenerator(tmp_path)

        _, _, _, _, _, _, qbm = gen._extract_chart_data(results)
        best_overall, _ = gen._find_best_profile_overall(qbm)

        analysis = gen._compute_category_variant_analysis(results, best_overall)

        # At least one category should have is_exception=True since
        # different profiles win different categories
        exceptions = [a for a in analysis if a["is_exception"]]
        non_exceptions = [a for a in analysis if not a["is_exception"]]
        assert len(exceptions) >= 1
        assert len(non_exceptions) >= 1

    def test_model_preferences_structure(self, tmp_path: Path) -> None:
        """Multi-model results return per-model preferences."""
        results = _make_multi_category_results()
        gen = ReportGenerator(tmp_path)

        _, _, _, _, _, _, qbm = gen._extract_chart_data(results)
        best_overall, _ = gen._find_best_profile_overall(qbm)

        prefs = gen._compute_model_variant_preferences(qbm, best_overall)

        assert len(prefs) == 2  # haiku and sonnet
        models = {p["model"] for p in prefs}
        assert models == {"haiku", "sonnet"}

        for pref in prefs:
            assert "preferred_profile" in pref
            assert "score" in pref
            assert "spread" in pref
            assert "margin" in pref
            assert "is_exception" in pref
            assert pref["score"] > 0

    def test_html_contains_category_analysis(self, tmp_path: Path) -> None:
        """Rendered HTML includes the variant analysis table."""
        results = _make_multi_category_results()
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(
            tmp_path / "report.html",
            results=results,
        )
        html = output.read_text(encoding="utf-8")

        assert "Variant Analysis by Task Category" in html
        assert "bug-fix" in html
        assert "refactor" in html
        assert "Model-Specific Preferences" in html

    def test_html_hides_sections_when_irrelevant(self, tmp_path: Path) -> None:
        """Single-category or single-model benchmarks omit variant sections."""
        # _make_sample_results has tasks fizzbuzz and sort_list (no numeric
        # suffix → each is its own category, but only 1 model)
        results = _make_sample_results(single_profile=True)
        _write_results_json(results, tmp_path / "results")

        gen = ReportGenerator(tmp_path / "results")
        output = gen.generate(
            tmp_path / "report.html",
            results=results,
        )
        html = output.read_text(encoding="utf-8")

        # Single model → model preferences section hidden
        assert "Model-Specific Preferences" not in html
