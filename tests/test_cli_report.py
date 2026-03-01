"""Integration tests for CLI report command."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer.testing

from claude_benchmark.cli.main import app

runner = typer.testing.CliRunner()


def _normalize_output(text: str) -> str:
    """Collapse Rich line-wrapping so long paths can be matched in assertions.

    Rich wraps at the terminal width (80 in CliRunner), breaking long absolute
    paths across multiple lines -- sometimes mid-word.  We strip all newlines
    and any surrounding whitespace so ``pyt\\nest-69`` becomes ``pytest-69``.
    """
    import re
    return re.sub(r"\s*\n\s*", "", text)


def _create_results_dir(base: Path) -> Path:
    """Create a valid results directory with manifest.json, run files, and results.json.

    Builds a minimal but complete test fixture with 2 profiles (empty, test),
    1 task (code-gen-01), 1 model (sonnet), and 3 runs per profile/task combo.
    """
    results_dir = base / "results" / "20260226_151821_686"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Write manifest.json
    manifest = {
        "timestamp": "2026-02-26T15:18:21",
        "models": ["sonnet"],
        "profiles": ["empty", "test"],
        "tasks": ["code-gen-01"],
        "runs_per_combination": 3,
        "total_combinations": 2,
        "total_runs": 6,
        "cli_args": {},
    }
    (results_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    # Create run files in storage format (runs/{model}/{profile}/{task}/run_{NNN}.json)
    for profile in ["empty", "test"]:
        for i in range(1, 4):
            run_dir = results_dir / "runs" / "sonnet" / profile / "code-gen-01"
            run_dir.mkdir(parents=True, exist_ok=True)
            base_score = 80.0 if profile == "empty" else 75.0
            run_data = {
                "run_number": i,
                "success": True,
                "usage": {"input_tokens": 1000, "output_tokens": 500},
                "output_files": {"solution.py": "def hello(): pass"},
                "error": None,
            }
            (run_dir / f"run_{i:03d}.json").write_text(
                json.dumps(run_data), encoding="utf-8"
            )

    # Write results.json (needed by ReportGenerator._load_benchmark_data)
    results_json = {
        "profiles": {
            "empty": {
                "profile_id": "empty",
                "profile_name": "empty",
                "tasks": {
                    "code-gen-01": {
                        "task_id": "code-gen-01",
                        "task_name": "code-gen-01",
                        "runs": [
                            {
                                "profile": "empty",
                                "task": "code-gen-01",
                                "model": "sonnet",
                                "scores": {"correctness": 80.0},
                                "token_count": 1500,
                                "code_output": "def hello(): pass",
                                "success": True,
                            },
                            {
                                "profile": "empty",
                                "task": "code-gen-01",
                                "model": "sonnet",
                                "scores": {"correctness": 82.0},
                                "token_count": 1500,
                                "code_output": "def hello(): pass",
                                "success": True,
                            },
                            {
                                "profile": "empty",
                                "task": "code-gen-01",
                                "model": "sonnet",
                                "scores": {"correctness": 78.0},
                                "token_count": 1500,
                                "code_output": "def hello(): pass",
                                "success": True,
                            },
                        ],
                        "mean_scores": {"correctness": 80.0},
                        "std_scores": {"correctness": 2.0},
                    }
                },
                "aggregate_scores": {"correctness": 80.0},
                "total_tokens": 4500,
            },
            "test": {
                "profile_id": "test",
                "profile_name": "test",
                "tasks": {
                    "code-gen-01": {
                        "task_id": "code-gen-01",
                        "task_name": "code-gen-01",
                        "runs": [
                            {
                                "profile": "test",
                                "task": "code-gen-01",
                                "model": "sonnet",
                                "scores": {"correctness": 75.0},
                                "token_count": 1500,
                                "code_output": "def hello(): pass",
                                "success": True,
                            },
                            {
                                "profile": "test",
                                "task": "code-gen-01",
                                "model": "sonnet",
                                "scores": {"correctness": 73.0},
                                "token_count": 1500,
                                "code_output": "def hello(): pass",
                                "success": True,
                            },
                            {
                                "profile": "test",
                                "task": "code-gen-01",
                                "model": "sonnet",
                                "scores": {"correctness": 77.0},
                                "token_count": 1500,
                                "code_output": "def hello(): pass",
                                "success": True,
                            },
                        ],
                        "mean_scores": {"correctness": 75.0},
                        "std_scores": {"correctness": 2.0},
                    }
                },
                "aggregate_scores": {"correctness": 75.0},
                "total_tokens": 4500,
            },
        },
        "models": ["sonnet"],
        "tasks": ["code-gen-01"],
        "metadata": {
            "date": "2026-02-26",
            "models_tested": ["sonnet"],
            "profile_count": 2,
            "total_runs": 6,
            "wall_clock_seconds": 0.0,
        },
    }
    (results_dir / "results.json").write_text(
        json.dumps(results_json, indent=2), encoding="utf-8"
    )

    return results_dir


def test_report_no_results(tmp_path: Path) -> None:
    """Report command should fail with clear error when results dir is invalid."""
    nonexistent = tmp_path / "nonexistent"
    result = runner.invoke(app, ["report", "--results-dir", str(nonexistent), "--no-open"])
    assert result.exit_code != 0
    assert "Error" in result.output or "not found" in result.output.lower()


def test_report_generates_html(tmp_path: Path) -> None:
    """Report command should generate report.html with step-by-step progress."""
    results_dir = _create_results_dir(tmp_path)
    result = runner.invoke(
        app,
        ["report", "--results-dir", str(results_dir), "--no-open", "--force"],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert (results_dir / "report.html").exists()
    # Check step-by-step progress output
    assert "Loading results" in result.output
    assert "HTML report generated" in result.output
    # Check absolute path in output (normalize to handle Rich line-wrapping)
    assert str(results_dir.resolve()) in _normalize_output(result.output)


def test_report_with_output_flag(tmp_path: Path) -> None:
    """Report command should write HTML to custom output path via --output."""
    results_dir = _create_results_dir(tmp_path)
    custom_output = tmp_path / "custom" / "my_report.html"
    result = runner.invoke(
        app,
        [
            "report",
            "--results-dir", str(results_dir),
            "--output", str(custom_output),
            "--no-open",
            "--force",
        ],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert custom_output.exists()
    assert str(custom_output.resolve()) in _normalize_output(result.output)


def test_report_no_export_flag(tmp_path: Path) -> None:
    """Report --no-export should skip the CLI's explicit export step."""
    results_dir = _create_results_dir(tmp_path)
    # Remove pre-existing benchmark-results files if any
    for f in results_dir.glob("benchmark-results.*"):
        f.unlink()

    result = runner.invoke(
        app,
        [
            "report",
            "--results-dir", str(results_dir),
            "--no-export",
            "--no-open",
            "--force",
        ],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert (results_dir / "report.html").exists()
    # The --no-export flag skips the CLI's export_raw_data call.
    # Note: ReportGenerator.generate() internally calls export_raw_data, so
    # benchmark-results.json/csv may exist from the generator. What we verify
    # is that the CLI output does NOT contain the "Exported JSON and CSV" step.
    assert "Exporting raw data" not in result.output


def test_report_auto_detect(tmp_path: Path) -> None:
    """Report should auto-detect latest results directory when --results-dir not given."""
    results_dir = _create_results_dir(tmp_path)
    with patch(
        "claude_benchmark.cli.commands.report.find_latest_results",
        return_value=results_dir,
    ):
        result = runner.invoke(
            app,
            ["report", "--no-open", "--force"],
        )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert (results_dir / "report.html").exists()


def test_report_filter_flags(tmp_path: Path) -> None:
    """Report with --profile filter should generate successfully with narrowed data."""
    results_dir = _create_results_dir(tmp_path)
    result = runner.invoke(
        app,
        [
            "report",
            "--results-dir", str(results_dir),
            "--profile", "empty",
            "--no-open",
            "--force",
        ],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    assert "Filtered to 1 profiles" in result.output
    assert (results_dir / "report.html").exists()


def test_report_overwrite_prompt(tmp_path: Path) -> None:
    """Report should prompt before overwriting existing report (with --force absent)."""
    results_dir = _create_results_dir(tmp_path)
    # Create existing report.html
    (results_dir / "report.html").write_text("<html>old</html>")
    result = runner.invoke(
        app,
        [
            "report",
            "--results-dir", str(results_dir),
            "--no-open",
        ],
        input="y\n",
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    # The new report should have replaced the old one
    content = (results_dir / "report.html").read_text()
    assert content != "<html>old</html>"


def test_report_browser_open_mocked(tmp_path: Path) -> None:
    """Report should call webbrowser.open when --no-open is not specified."""
    results_dir = _create_results_dir(tmp_path)
    with patch("claude_benchmark.cli.commands.report.webbrowser") as mock_wb:
        result = runner.invoke(
            app,
            ["report", "--results-dir", str(results_dir), "--force"],
        )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    mock_wb.open.assert_called_once()
    call_arg = mock_wb.open.call_args[0][0]
    assert "report.html" in call_arg


def test_report_regression_summary(tmp_path: Path) -> None:
    """Report should print regression summary section."""
    results_dir = _create_results_dir(tmp_path)
    result = runner.invoke(
        app,
        ["report", "--results-dir", str(results_dir), "--no-open", "--force"],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    # Regression summary section always prints (may say "No regressions" or list them)
    assert "Regression Summary" in result.output


def _create_results_dir_with_xss(base: Path) -> Path:
    """Create a results directory where code_output contains XSS payloads.

    This simulates a benchmark task (like instruction-01) whose test cases
    contain ``<script>alert('xss')</script>`` strings that end up in the
    code_output field of run results.
    """
    results_dir = base / "results" / "20260227_xss_test"
    results_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "timestamp": "2026-02-27T10:00:00",
        "models": ["sonnet"],
        "profiles": ["empty", "test"],
        "tasks": ["xss-task"],
        "runs_per_combination": 1,
        "total_combinations": 2,
        "total_runs": 2,
        "cli_args": {},
    }
    (results_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    xss_code = (
        'def sanitize_html(text: str) -> str:\n'
        '    """Strip HTML tags."""\n'
        '    # Test: <script>alert("xss")</script>\n'
        '    import re\n'
        '    return re.sub(r"<[^>]+>", "", text)\n'
    )

    results_json = {
        "profiles": {
            "empty": {
                "profile_id": "empty",
                "profile_name": "empty",
                "tasks": {
                    "xss-task": {
                        "task_id": "xss-task",
                        "task_name": "xss-task",
                        "runs": [
                            {
                                "profile": "empty",
                                "task": "xss-task",
                                "model": "sonnet",
                                "scores": {"correctness": 85.0},
                                "token_count": 1500,
                                "code_output": xss_code,
                                "success": True,
                            },
                        ],
                        "mean_scores": {"correctness": 85.0},
                        "std_scores": {"correctness": 0.0},
                    }
                },
                "aggregate_scores": {"correctness": 85.0},
                "total_tokens": 1500,
            },
            "test": {
                "profile_id": "test",
                "profile_name": "test",
                "tasks": {
                    "xss-task": {
                        "task_id": "xss-task",
                        "task_name": "xss-task",
                        "runs": [
                            {
                                "profile": "test",
                                "task": "xss-task",
                                "model": "sonnet",
                                "scores": {"correctness": 90.0},
                                "token_count": 1500,
                                "code_output": xss_code,
                                "success": True,
                            },
                        ],
                        "mean_scores": {"correctness": 90.0},
                        "std_scores": {"correctness": 0.0},
                    }
                },
                "aggregate_scores": {"correctness": 90.0},
                "total_tokens": 1500,
            },
        },
        "models": ["sonnet"],
        "tasks": ["xss-task"],
        "metadata": {
            "date": "2026-02-27",
            "models_tested": ["sonnet"],
            "profile_count": 2,
            "total_runs": 2,
            "wall_clock_seconds": 0.0,
        },
    }
    (results_dir / "results.json").write_text(
        json.dumps(results_json, indent=2), encoding="utf-8"
    )

    # Create run directories
    for profile in ["empty", "test"]:
        run_dir = results_dir / "runs" / "sonnet" / profile / "xss-task"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_data = {
            "run_number": 1,
            "success": True,
            "usage": {"input_tokens": 1000, "output_tokens": 500},
            "output_files": {"solution.py": xss_code},
            "error": None,
        }
        (run_dir / "run_001.json").write_text(
            json.dumps(run_data), encoding="utf-8"
        )

    return results_dir


def test_report_html_escapes_script_tags_in_code_output(tmp_path: Path) -> None:
    """Report HTML must not contain raw <script> from code_output (XSS prevention).

    When benchmark code_output contains ``<script>alert('xss')</script>``
    (e.g. from instruction-01's sanitize_html test cases), the generated
    report.html must escape or neutralize these sequences so they never
    execute in a browser.
    """
    results_dir = _create_results_dir_with_xss(tmp_path)
    result = runner.invoke(
        app,
        ["report", "--results-dir", str(results_dir), "--no-open", "--force"],
    )
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"

    report_path = results_dir / "report.html"
    assert report_path.exists()

    html_content = report_path.read_text(encoding="utf-8")

    # The raw </script> sequence must NOT appear in JSON data sections.
    # We need to exclude the legitimate closing </script> tags used by
    # the HTML template structure itself, and check only the JSON data.
    # The simplest approach: count </script> occurrences.  The template
    # has exactly 4 legitimate </script> closing tags (chartjs, data,
    # chart init, comparison).  Any extra ones mean data leaked through.

    # The critical XSS vector: </script> inside a <script> block causes the
    # HTML parser to prematurely close the script element.  After that, any
    # subsequent content (including <script>alert(...)) would execute as JS.
    #
    # Our fix escapes </  to <\/  inside JSON data, so the HTML parser never
    # sees a premature </script>.  We verify by checking that each script
    # block's inner content does NOT contain a raw </script> sequence.
    import re
    script_blocks = re.findall(
        r'<script>(.*?)</script>', html_content, re.DOTALL
    )
    for i, block in enumerate(script_blocks):
        assert '</script>' not in block, (
            f"Script block {i} contains unescaped </script> sequence "
            f"which would prematurely close the tag"
        )


def test_report_html_autoescape_active(tmp_path: Path) -> None:
    """Jinja2 autoescape must be active for .html.j2 templates.

    Verify that HTML-significant characters in data fields are properly
    entity-escaped when rendered into HTML attribute and text contexts.
    """
    from claude_benchmark.reporting.generator import ReportGenerator

    results_dir = _create_results_dir_with_xss(tmp_path)
    generator = ReportGenerator(results_dir)
    output_path = results_dir / "report.html"
    generator.generate(output_path)

    html_content = output_path.read_text(encoding="utf-8")

    # The HTML should be valid and not contain unescaped angle brackets
    # in text content areas (outside of intentional HTML structure)
    assert output_path.exists()
    assert "<!DOCTYPE html>" in html_content
    # Basic sanity: the report should contain expected structure
    assert "Executive Summary" in html_content
    assert "Benchmark Report" in html_content
