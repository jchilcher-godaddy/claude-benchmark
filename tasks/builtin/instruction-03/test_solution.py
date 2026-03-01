"""Tests for instruction-03 task."""

import inspect
import re

import pytest

from solution import format_report


def test_basic_formatting():
    """Test basic report formatting."""
    data = [
        {"name": "Temperature", "value": "25", "unit": "°C"},
        {"name": "Humidity", "value": "60", "unit": "%"},
    ]
    template = "{name}: {value} {unit}"
    result = format_report(data, template)
    assert "Temperature: 25 °C" in result
    assert "Humidity: 60 %" in result


def test_missing_key_substitutes_na():
    """Test missing key is substituted with N/A."""
    data = [
        {"name": "Temperature", "value": "25"},
        {"name": "Pressure", "unit": "Pa"},
    ]
    template = "{name}: {value} {unit}"
    result = format_report(data, template)
    assert "Temperature: 25 N/A" in result
    assert "Pressure: N/A Pa" in result


def test_empty_data():
    """Test with empty data list."""
    data = []
    template = "{name}: {value} {unit}"
    result = format_report(data, template)
    assert result == ""


def test_single_item():
    """Test with single item."""
    data = [{"name": "Speed", "value": "100", "unit": "km/h"}]
    template = "{name}: {value} {unit}"
    result = format_report(data, template)
    assert "Speed: 100 km/h" in result


def test_custom_template():
    """Test with custom template format."""
    data = [{"name": "Distance", "value": "500", "unit": "m"}]
    template = "Metric: {name} = {value}{unit}"
    result = format_report(data, template)
    assert "Metric: Distance = 500m" in result


def test_all_keys_missing():
    """Test with all keys missing."""
    data = [{"other": "value"}]
    template = "{name}: {value} {unit}"
    result = format_report(data, template)
    assert "N/A: N/A N/A" in result


def test_invalid_data_raises_valueerror():
    """Test invalid data type raises ValueError."""
    with pytest.raises(ValueError):
        format_report("not a list", "{name}")


def test_invalid_template_raises_valueerror():
    """Test invalid template type raises ValueError."""
    data = [{"name": "Test"}]
    with pytest.raises(ValueError):
        format_report(data, 123)


def test_non_dict_items_raise_valueerror():
    """Test non-dict items in data raise ValueError."""
    data = [{"name": "Test"}, "not a dict"]
    template = "{name}"
    with pytest.raises(ValueError):
        format_report(data, template)


def test_uses_snake_case():
    """Test function name uses snake_case (prompt rule)."""
    assert "format_report" in dir(__import__("solution"))
    assert "_" in "format_report", "Function name should use snake_case"


def test_uses_str_format_not_fstrings():
    """Test code uses str.format() not f-strings (prompt rule)."""
    import solution

    source = inspect.getsource(solution.format_report)
    format_pattern = r'\.format\s*\('
    assert re.search(format_pattern, source), "Code should use str.format() per prompt rules"


def test_raises_valueerror_not_returns_none():
    """Test function raises ValueError on errors, not returns None (prompt rule)."""
    invalid_inputs = [
        ("not a list", "{name}"),
        ([{"name": "Test"}], 123),
        ([{"name": "Test"}, "not a dict"], "{name}"),
    ]

    for data, template in invalid_inputs:
        with pytest.raises(ValueError):
            format_report(data, template)


def test_no_camelcase_function_name():
    """Test function does NOT use camelCase (which would violate prompt rule)."""
    import solution

    functions = [name for name in dir(solution) if callable(getattr(solution, name)) and not name.startswith("_")]
    for func_name in functions:
        if func_name != "__init__":
            has_lowercase_after_uppercase = any(
                func_name[i].isupper() and i > 0 and func_name[i - 1].islower()
                for i in range(len(func_name))
            )
            assert not has_lowercase_after_uppercase or "_" in func_name, f"Function {func_name} appears to use camelCase instead of snake_case"


def test_multiline_output():
    """Test multiple data items produce multi-line output."""
    data = [
        {"name": "A", "value": "1", "unit": "x"},
        {"name": "B", "value": "2", "unit": "y"},
        {"name": "C", "value": "3", "unit": "z"},
    ]
    template = "{name}: {value} {unit}"
    result = format_report(data, template)
    lines = result.strip().split("\n")
    assert len(lines) == 3
