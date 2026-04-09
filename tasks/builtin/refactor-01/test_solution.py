"""Tests for refactor-01 task."""

import ast
import inspect
import pytest
from pathlib import Path

from solution import process_records


def test_basic_processing():
    """Test basic record processing with various statuses and priorities."""
    records = [
        {"status": "active", "amount": 100, "priority": "high"},
        {"status": "active", "amount": 50, "priority": "low"},
        {"status": "pending", "amount": 75, "priority": "high"},
        {"status": "inactive", "amount": 200, "priority": "high"},
    ]
    result = process_records(records)
    assert result["active_total"] == 150
    assert result["high_priority_total"] == 375
    assert result["pending_total"] == 75
    assert result["active_high_priority_count"] == 1
    assert result["pending_high_priority_count"] == 1


def test_empty_list():
    """Test processing empty record list."""
    result = process_records([])
    assert result["active_total"] == 0
    assert result["high_priority_total"] == 0
    assert result["pending_total"] == 0
    assert result["active_high_priority_count"] == 0
    assert result["pending_high_priority_count"] == 0


def test_missing_fields():
    """Test handling records with missing fields."""
    records = [
        {"status": "active"},
        {"amount": 100},
        {"priority": "high", "amount": 50},
        {"status": "pending", "amount": 25, "priority": "low"},
    ]
    result = process_records(records)
    assert result["active_total"] == 0
    assert result["high_priority_total"] == 50
    assert result["pending_total"] == 25
    assert result["active_high_priority_count"] == 0
    assert result["pending_high_priority_count"] == 0


def test_zero_and_negative_amounts():
    """Test that zero and negative amounts are excluded."""
    records = [
        {"status": "active", "amount": 0, "priority": "high"},
        {"status": "active", "amount": -50, "priority": "high"},
        {"status": "active", "amount": 100, "priority": "high"},
        {"status": "pending", "amount": -25, "priority": "high"},
    ]
    result = process_records(records)
    assert result["active_total"] == 100
    assert result["high_priority_total"] == 100
    assert result["pending_total"] == 0
    assert result["active_high_priority_count"] == 3
    assert result["pending_high_priority_count"] == 1


def test_multiple_pending_high_priority():
    """Test counting multiple pending high priority customers."""
    records = [
        {"status": "pending", "amount": 10, "priority": "high"},
        {"status": "pending", "amount": 20, "priority": "high"},
        {"status": "pending", "amount": 30, "priority": "low"},
        {"status": "active", "amount": 40, "priority": "high"},
    ]
    result = process_records(records)
    assert result["pending_total"] == 60
    assert result["pending_high_priority_count"] == 2
    assert result["active_high_priority_count"] == 1


def test_large_amounts():
    """Test processing with large amounts."""
    records = [
        {"status": "active", "amount": 1_000_000, "priority": "high"},
        {"status": "pending", "amount": 500_000, "priority": "high"},
        {"status": "active", "amount": 250_000, "priority": "low"},
    ]
    result = process_records(records)
    assert result["active_total"] == 1_250_000
    assert result["high_priority_total"] == 1_500_000
    assert result["pending_total"] == 500_000


def test_no_duplicated_loops():
    """Verify solution reduces duplicated loops by extracting repeated logic.

    The starter code has 5 separate 'for record in records' loops.
    A properly refactored solution should have fewer than 4 For loops.
    """
    solution_path = Path(__file__).parent / "solution.py"
    with open(solution_path) as f:
        tree = ast.parse(f.read())

    for_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.For))
    assert for_count < 4, (
        f"Expected fewer than 4 'for' loops (found {for_count}). "
        "The task requires extracting repeated loop logic into helper functions."
    )


def test_has_helper_functions():
    """Verify solution extracts repeated logic into helper functions.

    The task requires extracting duplicated aggregation logic into reusable helpers.
    Solution should define at least 1 function besides process_records.
    """
    solution_path = Path(__file__).parent / "solution.py"
    with open(solution_path) as f:
        tree = ast.parse(f.read())

    function_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name != "process_records"
    ]

    assert len(function_names) >= 1, (
        "Expected at least 1 helper function besides process_records. "
        f"Found: {function_names if function_names else 'none'}. "
        "The task requires extracting repeated logic into helper functions."
    )
