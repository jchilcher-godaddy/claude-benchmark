"""Tests for the CLI run command (basic flag and error checks).

These tests verify the basic CLI contract: help output, error handling
for invalid inputs. Detailed wiring tests are in test_run_command.py.
"""

import pytest
from typer.testing import CliRunner
from claude_benchmark.cli.main import app

runner = CliRunner()


def test_run_help():
    """run --help shows all expected options."""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--profile" in result.output
    assert "--model" in result.output
    assert "--reps" in result.output
    assert "--concurrency" in result.output
    assert "--max-cost" in result.output
    assert "--task" in result.output
    assert "--yes" in result.output
    assert "--dry-run" in result.output
    assert "--results-dir" in result.output
