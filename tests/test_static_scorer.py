"""Tests for the static analysis scorer (Ruff, pytest, radon)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_benchmark.scoring.models import ScoringWeights
from claude_benchmark.scoring.static import (
    StaticScorer,
    count_loc,
    normalize_complexity_score,
    normalize_lint_score,
    normalize_test_pass_rate,
)


# ---------------------------------------------------------------------------
# Normalization function tests
# ---------------------------------------------------------------------------


class TestNormalizeTestPassRate:
    def test_half_passing(self):
        assert normalize_test_pass_rate(5, 10) == 50.0

    def test_no_tests(self):
        assert normalize_test_pass_rate(0, 0) == 0.0

    def test_all_passing(self):
        assert normalize_test_pass_rate(10, 10) == 100.0

    def test_none_passing(self):
        assert normalize_test_pass_rate(0, 10) == 0.0

    def test_single_test_passing(self):
        assert normalize_test_pass_rate(1, 1) == 100.0


class TestNormalizeLintScore:
    def test_no_errors(self):
        assert normalize_lint_score(0, 100) == 100.0

    def test_ten_errors_per_100_loc(self):
        # 10/100 * 1000 = 100, so 100 - 100 = 0
        assert normalize_lint_score(10, 100) == 0.0

    def test_five_errors_per_100_loc(self):
        # 5/100 * 1000 = 50, so 100 - 50 = 50
        assert normalize_lint_score(5, 100) == 50.0

    def test_no_code(self):
        assert normalize_lint_score(0, 0) == 100.0

    def test_many_errors_clamps_to_zero(self):
        # 20 errors in 100 lines: 20/100 * 1000 = 200, max(0, 100-200) = 0
        assert normalize_lint_score(20, 100) == 0.0

    def test_one_error_in_1000_lines(self):
        # 1/1000 * 1000 = 1, so 100 - 1 = 99
        assert normalize_lint_score(1, 1000) == 99.0


class TestNormalizeComplexityScore:
    def test_complexity_1(self):
        # 100 - (1-1)*5 = 100
        assert normalize_complexity_score(1) == 100.0

    def test_complexity_5(self):
        # 100 - (5-1)*5 = 80
        assert normalize_complexity_score(5) == 80.0

    def test_complexity_10(self):
        # 80 - (10-5)*4 = 60
        assert normalize_complexity_score(10) == 60.0

    def test_complexity_20(self):
        # 60 - (20-10)*2 = 40
        assert normalize_complexity_score(20) == 40.0

    def test_complexity_30(self):
        # 40 - (30-20)*2 = 20
        assert normalize_complexity_score(30) == 20.0

    def test_complexity_40(self):
        # 20 - (40-30)*1.5 = 5
        assert normalize_complexity_score(40) == 5.0

    def test_complexity_50(self):
        # max(0, 5 - (50-40)*0.5) = max(0, 0) = 0
        assert normalize_complexity_score(50) == 0.0

    def test_no_functions(self):
        assert normalize_complexity_score(0) == 100.0

    def test_very_high_complexity(self):
        assert normalize_complexity_score(100) >= 0.0

    def test_boundary_between_a_and_b(self):
        # At 5.5: B range => 80 - (5.5-5)*4 = 78
        assert normalize_complexity_score(5.5) == 78.0


class TestCountLoc:
    def test_counts_code_lines(self, tmp_path: Path):
        f = tmp_path / "module.py"
        f.write_text("import os\n\ndef main():\n    pass\n")
        # Lines: "import os", "def main():", "pass" = 3 (blank line excluded)
        assert count_loc([f]) == 3

    def test_excludes_comments(self, tmp_path: Path):
        f = tmp_path / "module.py"
        f.write_text("# This is a comment\nx = 1\n# Another comment\ny = 2\n")
        assert count_loc([f]) == 2

    def test_excludes_blank_lines(self, tmp_path: Path):
        f = tmp_path / "module.py"
        f.write_text("x = 1\n\n\ny = 2\n\n")
        assert count_loc([f]) == 2

    def test_multiple_files(self, tmp_path: Path):
        f1 = tmp_path / "a.py"
        f1.write_text("x = 1\n")
        f2 = tmp_path / "b.py"
        f2.write_text("y = 2\nz = 3\n")
        assert count_loc([f1, f2]) == 3

    def test_empty_list(self):
        assert count_loc([]) == 0

    def test_nonexistent_file(self, tmp_path: Path):
        fake = tmp_path / "nonexistent.py"
        assert count_loc([fake]) == 0


# ---------------------------------------------------------------------------
# StaticScorer.run_ruff tests
# ---------------------------------------------------------------------------


class TestRunRuff:
    def test_clean_file(self, tmp_path: Path):
        """A file with no lint violations should return count 0."""
        f = tmp_path / "clean.py"
        f.write_text("x = 1\n")
        scorer = StaticScorer()
        result = scorer.run_ruff(tmp_path)
        assert result["count"] == 0
        assert result["violations"] == []

    def test_file_with_violations(self, tmp_path: Path):
        """A file with known lint violations should return a non-zero count."""
        f = tmp_path / "messy.py"
        # Unused import is a violation (F401)
        f.write_text("import os\nimport sys\n\nx = 1\n")
        scorer = StaticScorer()
        result = scorer.run_ruff(tmp_path)
        assert result["count"] >= 1
        assert isinstance(result["violations"], list)

    def test_does_not_crash_on_violations(self, tmp_path: Path):
        """Ruff exit code 1 (violations found) must not raise an exception."""
        f = tmp_path / "violations.py"
        f.write_text("import os\nimport sys\nimport json\n\nx = 1\n")
        scorer = StaticScorer()
        # This must NOT raise StaticAnalysisError
        result = scorer.run_ruff(tmp_path)
        assert result["count"] >= 1

    def test_empty_directory(self, tmp_path: Path):
        """A directory with no .py files should return empty results."""
        scorer = StaticScorer()
        result = scorer.run_ruff(tmp_path)
        assert result["count"] == 0
        assert result["violations"] == []

    def test_with_specific_rules(self, tmp_path: Path):
        """Custom rules selection should work."""
        f = tmp_path / "code.py"
        f.write_text("import os\n\nx = 1\n")
        scorer = StaticScorer()
        result = scorer.run_ruff(tmp_path, rules=["F401"])
        # F401 is unused import, should find 'os'
        assert result["count"] >= 1


# ---------------------------------------------------------------------------
# StaticScorer.run_pytest tests
# ---------------------------------------------------------------------------


class TestRunPytest:
    def test_mixed_results(self, tmp_path: Path):
        """Pytest with 2 passing and 1 failing test should report correctly."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text(
            "def test_pass_one():\n    assert True\n\n"
            "def test_pass_two():\n    assert True\n\n"
            "def test_fail():\n    assert False\n"
        )
        scorer = StaticScorer()
        result = scorer.run_pytest(test_file, tmp_path)
        assert result["passed"] == 2
        assert result["failed"] == 1
        assert result["total"] == 3

    def test_all_passing(self, tmp_path: Path):
        """All tests pass."""
        test_file = tmp_path / "test_ok.py"
        test_file.write_text("def test_a():\n    assert True\n\ndef test_b():\n    assert True\n")
        scorer = StaticScorer()
        result = scorer.run_pytest(test_file, tmp_path)
        assert result["passed"] == 2
        assert result["failed"] == 0
        assert result["total"] == 2

    def test_missing_test_file(self, tmp_path: Path):
        """Non-existent test file should return zero counts with error."""
        scorer = StaticScorer()
        result = scorer.run_pytest(tmp_path / "nonexistent_test.py", tmp_path)
        assert result["passed"] == 0
        assert result["total"] == 0
        assert "error" in result

    def test_skipped_tests(self, tmp_path: Path):
        """Skipped tests are counted separately."""
        test_file = tmp_path / "test_skip.py"
        test_file.write_text(
            "import pytest\n\n"
            "def test_pass():\n    assert True\n\n"
            "@pytest.mark.skip(reason='demo')\n"
            "def test_skip():\n    assert True\n"
        )
        scorer = StaticScorer()
        result = scorer.run_pytest(test_file, tmp_path)
        assert result["passed"] == 1
        assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# StaticScorer.analyze_complexity tests
# ---------------------------------------------------------------------------


class TestAnalyzeComplexity:
    def test_simple_function(self, tmp_path: Path):
        """A simple function should have low complexity."""
        f = tmp_path / "simple.py"
        f.write_text("def hello():\n    return 'hello'\n")
        scorer = StaticScorer()
        result = scorer.analyze_complexity([f])
        assert result["average_complexity"] <= 5
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["rank"] == "A"

    def test_complex_function(self, tmp_path: Path):
        """A function with many branches should have higher complexity."""
        f = tmp_path / "complex.py"
        code = (
            "def decide(x, y, z):\n"
            "    if x > 0:\n"
            "        if y > 0:\n"
            "            if z > 0:\n"
            "                return 'all positive'\n"
            "            else:\n"
            "                return 'z negative'\n"
            "        else:\n"
            "            return 'y negative'\n"
            "    elif x == 0:\n"
            "        return 'x zero'\n"
            "    else:\n"
            "        for i in range(10):\n"
            "            if i % 2 == 0:\n"
            "                continue\n"
            "        return 'x negative'\n"
        )
        f.write_text(code)
        scorer = StaticScorer()
        result = scorer.analyze_complexity([f])
        assert result["average_complexity"] > 1
        assert result["max_complexity"] > 1

    def test_syntax_error_returns_f_rank(self, tmp_path: Path):
        """Invalid syntax should get F-rank (complexity=50), not crash."""
        f = tmp_path / "broken.py"
        f.write_text("def broken(\n    this is not valid python\n")
        scorer = StaticScorer()
        result = scorer.analyze_complexity([f])
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["rank"] == "F"
        assert result["blocks"][0]["complexity"] == 50
        assert result["blocks"][0]["name"] == "<unparseable>"

    def test_no_functions(self, tmp_path: Path):
        """A file with no functions/classes should return avg=0."""
        f = tmp_path / "constants.py"
        f.write_text("X = 1\nY = 2\nZ = 3\n")
        scorer = StaticScorer()
        result = scorer.analyze_complexity([f])
        assert result["average_complexity"] == 0.0
        assert result["blocks"] == []

    def test_empty_file_list(self):
        """No source files should return zeros."""
        scorer = StaticScorer()
        result = scorer.analyze_complexity([])
        assert result["average_complexity"] == 0.0
        assert result["max_complexity"] == 0

    def test_multiple_files(self, tmp_path: Path):
        """Complexity is averaged across all files."""
        f1 = tmp_path / "a.py"
        f1.write_text("def simple():\n    return 1\n")
        f2 = tmp_path / "b.py"
        f2.write_text("def also_simple():\n    return 2\n")
        scorer = StaticScorer()
        result = scorer.analyze_complexity([f1, f2])
        assert len(result["blocks"]) == 2


# ---------------------------------------------------------------------------
# StaticScorer.score integration tests
# ---------------------------------------------------------------------------


class TestScoreIntegration:
    def test_score_with_real_files(self, tmp_path: Path):
        """Integration test: a workspace with source and test files."""
        # Create a source file
        src = tmp_path / "calculator.py"
        src.write_text(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n\n"
            "def subtract(a: int, b: int) -> int:\n"
            "    return a - b\n"
        )

        # Create a test file
        test_file = tmp_path / "test_calculator.py"
        test_file.write_text(
            "from calculator import add, subtract\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n\n"
            "def test_subtract():\n"
            "    assert subtract(5, 3) == 2\n"
        )

        scorer = StaticScorer()
        result = scorer.score(tmp_path, test_file)

        # Both tests should pass
        assert result.tests_passed == 2
        assert result.tests_total == 2
        assert result.test_pass_rate == 100.0

        # Simple functions should have high complexity score
        assert result.complexity_score >= 80.0

        # Should have LOC counted
        assert result.lines_of_code > 0

        # Weighted total should be meaningful
        assert 0 <= result.weighted_total <= 100

    def test_empty_directory_returns_zeros(self, tmp_path: Path):
        """Empty directory (no .py files) should return all-zero score."""
        scorer = StaticScorer()
        result = scorer.score(tmp_path, tmp_path / "test_nothing.py")
        assert result.test_pass_rate == 0
        assert result.tests_passed == 0
        assert result.tests_total == 0
        assert result.lint_score == 0
        assert result.lint_errors == 0
        assert result.complexity_score == 0
        assert result.weighted_total == 0
        assert result.lines_of_code == 0

    def test_weighted_total_default_weights(self, tmp_path: Path):
        """Weighted total should use default weights: test(50%) + lint(30%) + complexity(20%)."""
        # Create a simple source file
        src = tmp_path / "mod.py"
        src.write_text("def foo():\n    return 1\n")

        # Create a passing test
        test_file = tmp_path / "test_mod.py"
        test_file.write_text(
            "from mod import foo\n\n" "def test_foo():\n    assert foo() == 1\n"
        )

        scorer = StaticScorer()
        result = scorer.score(tmp_path, test_file)

        # Verify weighted total matches formula
        expected = (
            result.test_pass_rate * 0.50
            + result.lint_score * 0.30
            + result.complexity_score * 0.20
        )
        assert abs(result.weighted_total - round(expected, 2)) < 0.1

    def test_weighted_total_custom_weights(self, tmp_path: Path):
        """Custom weights should be applied correctly."""
        src = tmp_path / "mod.py"
        src.write_text("def foo():\n    return 1\n")

        test_file = tmp_path / "test_mod.py"
        test_file.write_text(
            "from mod import foo\n\n" "def test_foo():\n    assert foo() == 1\n"
        )

        custom_weights = ScoringWeights(
            test_pass_rate=0.3, lint_score=0.2, complexity_score=0.5
        )
        scorer = StaticScorer(weights=custom_weights)
        result = scorer.score(tmp_path, test_file)

        # Verify weighted total matches custom formula
        expected = (
            result.test_pass_rate * 0.3
            + result.lint_score * 0.2
            + result.complexity_score * 0.5
        )
        assert abs(result.weighted_total - round(expected, 2)) < 0.1

    def test_source_files_exclude_test_files(self, tmp_path: Path):
        """Test files (test_*.py) should not be included in source file analysis."""
        src = tmp_path / "module.py"
        src.write_text("def hello():\n    return 'hello'\n")

        test_file = tmp_path / "test_module.py"
        test_file.write_text(
            "from module import hello\n\n" "def test_hello():\n    assert hello() == 'hello'\n"
        )

        scorer = StaticScorer()
        result = scorer.score(tmp_path, test_file)

        # Only the source file LOC should be counted
        assert result.lines_of_code == 2  # "def hello():" and "return 'hello'"

    def test_score_with_failing_tests(self, tmp_path: Path):
        """Score should handle failing tests without crashing."""
        src = tmp_path / "broken.py"
        src.write_text("def broken():\n    return 42\n")

        test_file = tmp_path / "test_broken.py"
        test_file.write_text(
            "from broken import broken\n\n"
            "def test_pass():\n    assert broken() == 42\n\n"
            "def test_fail():\n    assert broken() == 0\n"
        )

        scorer = StaticScorer()
        result = scorer.score(tmp_path, test_file)
        assert result.test_pass_rate == 50.0
        assert result.tests_passed == 1
        assert result.tests_total == 2


# ---------------------------------------------------------------------------
# Import test
# ---------------------------------------------------------------------------


class TestStaticScorerImport:
    def test_import_from_package(self):
        from claude_benchmark.scoring import StaticScorer

        assert StaticScorer is not None
