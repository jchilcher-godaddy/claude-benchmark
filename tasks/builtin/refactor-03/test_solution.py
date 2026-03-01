"""Tests for refactor-03 task."""

import pytest

from solution import process_data


def test_basic_processing():
    """Test basic data processing."""
    raw_input = """Alice,Engineering,100
Bob,Sales,200
Charlie,Marketing,150"""
    result = process_data(raw_input)
    lines = result.split("\n")
    assert len(lines) == 3
    assert "ALICE" in lines[0]
    assert "ENGINEERING" in lines[0]
    assert "100.00" in lines[0]
    assert "150.00" in lines[0]
    assert "BOB" in lines[1]
    assert "SALES" in lines[1]
    assert "200.00" in lines[1]
    assert "300.00" in lines[1]
    assert "CHARLIE" in lines[2]
    assert "MARKETING" in lines[2]
    assert "150.00" in lines[2]
    assert "225.00" in lines[2]


def test_empty_input():
    """Test processing empty input."""
    result = process_data("")
    assert result == "ERROR: No data"


def test_whitespace_only():
    """Test processing whitespace-only input."""
    result = process_data("   \n  \n  ")
    assert result == "ERROR: No data"


def test_wrong_column_count():
    """Test error handling for wrong column count."""
    raw_input = """Alice,Engineering,100
Bob,Sales
Charlie,Marketing,150"""
    result = process_data(raw_input)
    assert result.startswith("ERROR:")
    assert "expected 3 columns, got 2" in result


def test_non_numeric_value():
    """Test error handling for non-numeric value column."""
    raw_input = """Alice,Engineering,100
Bob,Sales,invalid
Charlie,Marketing,150"""
    result = process_data(raw_input)
    assert result.startswith("ERROR:")
    assert "not a valid number" in result


def test_single_row():
    """Test processing single row."""
    raw_input = "John,Finance,500"
    result = process_data(raw_input)
    assert "JOHN" in result
    assert "FINANCE" in result
    assert "500.00" in result
    assert "750.00" in result


def test_decimal_values():
    """Test processing decimal values."""
    raw_input = "Jane,HR,123.45"
    result = process_data(raw_input)
    assert "JANE" in result
    assert "HR" in result
    assert "123.45" in result
    assert "185.17" in result or "185.18" in result


def test_zero_value():
    """Test processing zero value."""
    raw_input = "Zero,Test,0"
    result = process_data(raw_input)
    assert "ZERO" in result
    assert "TEST" in result
    assert "0.00" in result


def test_negative_value():
    """Test processing negative value."""
    raw_input = "Negative,Test,-50"
    result = process_data(raw_input)
    assert "NEGATIVE" in result
    assert "TEST" in result
    assert "-50.00" in result
    assert "-75.00" in result


def test_mixed_case_normalization():
    """Test that text columns are normalized to uppercase."""
    raw_input = "MiXeD,CaSe,100"
    result = process_data(raw_input)
    assert "MIXED" in result
    assert "CASE" in result
    assert "mixed" not in result.lower() or "MIXED" in result


def test_multiple_validation_errors():
    """Test handling multiple validation errors."""
    raw_input = """Alice,Engineering,100
Bob,Sales
Charlie,Marketing
Dave,IT,300"""
    result = process_data(raw_input)
    assert result.startswith("ERROR:")


def test_whitespace_handling():
    """Test that whitespace is trimmed from cells."""
    raw_input = " Alice , Engineering , 100 "
    result = process_data(raw_input)
    assert "ALICE" in result
    assert "ENGINEERING" in result
    assert "100.00" in result


def test_blank_lines_ignored():
    """Test that blank lines are ignored."""
    raw_input = """Alice,Engineering,100

Bob,Sales,200

Charlie,Marketing,150"""
    result = process_data(raw_input)
    lines = result.split("\n")
    assert len(lines) == 3
