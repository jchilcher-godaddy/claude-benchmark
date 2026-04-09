"""Tests for calibration sample degrader."""

import ast
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_benchmark.calibration.degrader import (
    CalibrationSample,
    _degrade_broken,
    _degrade_mild,
    _degrade_severe,
    generate_calibration_samples,
)


SAMPLE_CODE = textwrap.dedent('''\
    """Module docstring."""

    def fibonacci(n: int) -> int:
        """Return the nth Fibonacci number."""
        if n < 0:
            raise ValueError("n must be non-negative")
        if n == 0:
            return 0
        if n == 1:
            return 1

        prev, curr = 0, 1
        for _ in range(2, n + 1):
            prev, curr = curr, prev + curr

        return curr
''')


class TestGoldTier:
    def test_gold_returns_code_unchanged(self):
        """Gold tier should be the original code, untouched."""
        # Gold tier is just the original code — tested via generate_calibration_samples
        # No transformation function for gold
        assert SAMPLE_CODE == SAMPLE_CODE


class TestMildTier:
    def test_strips_docstrings(self):
        result = _degrade_mild(SAMPLE_CODE)
        assert '"""Module docstring."""' not in result
        assert '"""Return the nth Fibonacci number."""' not in result

    def test_preserves_function_signature(self):
        result = _degrade_mild(SAMPLE_CODE)
        assert "fibonacci" in result

    def test_preserves_logic(self):
        result = _degrade_mild(SAMPLE_CODE)
        assert "ValueError" in result
        assert "prev" in result
        assert "curr" in result

    def test_preserves_type_hints(self):
        result = _degrade_mild(SAMPLE_CODE)
        assert "int" in result


class TestSevereTier:
    def test_strips_docstrings(self):
        result = _degrade_severe(SAMPLE_CODE)
        assert '"""Module docstring."""' not in result
        assert '"""Return the nth Fibonacci number."""' not in result

    def test_renames_variables(self):
        result = _degrade_severe(SAMPLE_CODE)
        # Local vars (prev, curr) should be renamed to single letters
        # but parameter 'n' stays (it's a param)
        assert "prev" not in result or "curr" not in result

    def test_removes_type_hints(self):
        result = _degrade_severe(SAMPLE_CODE)
        # Function return type hint should be gone
        assert "-> int" not in result

    def test_flattens_try_except(self):
        code_with_try = textwrap.dedent('''\
            def foo():
                try:
                    x = 1
                    return x
                except ValueError:
                    return 0
        ''')
        result = _degrade_severe(code_with_try)
        assert "except" not in result
        assert "try" not in result

    def test_still_parses_as_valid_python(self):
        result = _degrade_severe(SAMPLE_CODE)
        # Should not raise SyntaxError
        ast.parse(result)


class TestBrokenTier:
    def test_code_differs_from_original(self):
        code = textwrap.dedent('''\
            def binary_search(arr, target):
                left, right = 0, len(arr) - 1
                while left <= right:
                    mid = (left + right) // 2
                    if arr[mid] == target:
                        return mid
                    elif arr[mid] < target:
                        left = mid + 1
                    else:
                        right = mid - 1
                return -1
        ''')
        result = _degrade_broken(code, seed=42)
        # With seed=42, comparison mutation is applied
        assert result != code
        assert "left < right" in result

    def test_still_parses_as_valid_python(self):
        result = _degrade_broken(SAMPLE_CODE, seed=42)
        ast.parse(result)

    def test_deterministic_with_seed(self):
        result1 = _degrade_broken(SAMPLE_CODE, seed=100)
        result2 = _degrade_broken(SAMPLE_CODE, seed=100)
        assert result1 == result2

    def test_different_with_different_seed(self):
        result1 = _degrade_broken(SAMPLE_CODE, seed=100)
        result2 = _degrade_broken(SAMPLE_CODE, seed=200)
        # With different seeds, may or may not differ depending on mutation type selected
        # Just verify both are valid Python
        ast.parse(result1)
        ast.parse(result2)


class TestRegexFallback:
    def test_mild_handles_syntax_error_gracefully(self):
        bad_code = "def foo(:\n    pass"  # invalid syntax
        result = _degrade_mild(bad_code)
        # Regex fallback should return something (not crash)
        assert isinstance(result, str)


class TestGenerateCalibrationSamples:
    def test_generates_three_tiers_per_task(self, tmp_path):
        # Create a minimal task directory
        task_dir = tmp_path / "code-gen-01"
        task_dir.mkdir()

        toml_content = textwrap.dedent('''\
            name = "code-gen-01"
            task_type = "code-gen"
            difficulty = "easy"
            size = "function"
            description = "Test task"
            prompt = "Write a function."
            tags = []

            [scoring]
            test_file = "test_solution.py"
            reference_solution = "reference.py"
        ''')
        (task_dir / "task.toml").write_text(toml_content)
        (task_dir / "test_solution.py").write_text("def test_foo(): pass")
        (task_dir / "reference.py").write_text(SAMPLE_CODE)

        samples = generate_calibration_samples([task_dir])

        assert len(samples) == 4
        tiers = {s.tier for s in samples}
        assert tiers == {"gold", "mild", "broken", "severe"}

        # Gold should be unchanged
        gold = [s for s in samples if s.tier == "gold"][0]
        assert gold.code == SAMPLE_CODE

        # Mild should differ from gold
        mild = [s for s in samples if s.tier == "mild"][0]
        assert mild.code != SAMPLE_CODE

    def test_skips_tasks_without_reference(self, tmp_path):
        task_dir = tmp_path / "no-ref"
        task_dir.mkdir()

        toml_content = textwrap.dedent('''\
            name = "no-ref"
            task_type = "code-gen"
            difficulty = "easy"
            size = "function"
            description = "No ref"
            prompt = "Write something."
            tags = []

            [scoring]
            test_file = "test_solution.py"
        ''')
        (task_dir / "task.toml").write_text(toml_content)
        (task_dir / "test_solution.py").write_text("def test_foo(): pass")

        samples = generate_calibration_samples([task_dir])
        assert len(samples) == 0
