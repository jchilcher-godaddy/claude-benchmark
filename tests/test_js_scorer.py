"""Tests for the JavaScript static analysis scorer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_benchmark.scoring.errors import StaticAnalysisError
from claude_benchmark.scoring.lang_javascript import JavaScriptStaticScorer


class TestJsScorerMetadata:
    def test_source_glob(self):
        scorer = JavaScriptStaticScorer()
        assert scorer.source_glob() == "*.js"

    def test_test_glob_patterns(self):
        scorer = JavaScriptStaticScorer()
        patterns = scorer.test_glob_patterns()
        assert "*.test.js" in patterns
        assert "*.spec.ts" in patterns

    def test_comment_prefixes(self):
        scorer = JavaScriptStaticScorer()
        assert scorer.comment_prefixes() == ["//"]


class TestJsCountLoc:
    def test_counts_js_lines(self, tmp_path: Path):
        f = tmp_path / "index.js"
        f.write_text("const x = 1;\n\nfunction add(a, b) {\n  return a + b;\n}\n")
        scorer = JavaScriptStaticScorer()
        # Lines: "const x = 1;", "function add(a, b) {", "return a + b;", "}" = 4
        assert scorer.count_loc([f]) == 4

    def test_excludes_js_comments(self, tmp_path: Path):
        f = tmp_path / "index.js"
        f.write_text("// comment\nconst x = 1;\n// another\nconst y = 2;\n")
        scorer = JavaScriptStaticScorer()
        assert scorer.count_loc([f]) == 2


class TestJsFindSourceFiles:
    def test_excludes_test_files(self, tmp_path: Path):
        (tmp_path / "utils.js").write_text("module.exports = {};\n")
        (tmp_path / "utils.test.js").write_text("test('works', () => {});\n")
        (tmp_path / "helpers.spec.ts").write_text("describe('helpers', () => {});\n")
        scorer = JavaScriptStaticScorer()
        files = scorer.find_source_files(tmp_path)
        names = [f.name for f in files]
        assert "utils.js" in names
        assert "utils.test.js" not in names
        assert "helpers.spec.ts" not in names

    def test_excludes_node_modules(self, tmp_path: Path):
        (tmp_path / "index.js").write_text("const x = 1;\n")
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {};\n")
        scorer = JavaScriptStaticScorer()
        files = scorer.find_source_files(tmp_path)
        names = [f.name for f in files]
        assert len(files) == 1
        assert "index.js" in names

    def test_finds_multiple_extensions(self, tmp_path: Path):
        (tmp_path / "a.js").write_text("x\n")
        (tmp_path / "b.mjs").write_text("y\n")
        (tmp_path / "c.ts").write_text("z\n")
        scorer = JavaScriptStaticScorer()
        files = scorer.find_source_files(tmp_path)
        assert len(files) == 3


class TestJsRunLint:
    def test_empty_directory(self, tmp_path: Path):
        scorer = JavaScriptStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result == {"violations": [], "count": 0}

    @patch("claude_benchmark.scoring.lang_javascript.shutil.which", return_value=None)
    def test_missing_npx_raises(self, mock_which, tmp_path: Path):
        (tmp_path / "index.js").write_text("const x = 1;\n")
        scorer = JavaScriptStaticScorer()
        with pytest.raises(StaticAnalysisError, match="npx not found"):
            scorer.run_lint(tmp_path)

    @patch("claude_benchmark.scoring.lang_javascript.subprocess.run")
    @patch("claude_benchmark.scoring.lang_javascript.shutil.which", return_value="/usr/bin/npx")
    def test_parses_eslint_violations(self, mock_which, mock_run, tmp_path: Path):
        (tmp_path / "index.js").write_text("var x = 1;\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 1,
            "stdout": json.dumps([{
                "filePath": str(tmp_path / "index.js"),
                "messages": [
                    {"ruleId": "no-var", "message": "Unexpected var", "line": 1, "column": 1}
                ],
            }]),
            "stderr": "",
        })()
        scorer = JavaScriptStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result["count"] == 1
        assert result["violations"][0]["code"] == "no-var"

    @patch("claude_benchmark.scoring.lang_javascript.subprocess.run")
    @patch("claude_benchmark.scoring.lang_javascript.shutil.which", return_value="/usr/bin/npx")
    def test_fatal_error_raises(self, mock_which, mock_run, tmp_path: Path):
        (tmp_path / "index.js").write_text("x\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 2,
            "stdout": "",
            "stderr": "fatal config error",
        })()
        scorer = JavaScriptStaticScorer()
        with pytest.raises(StaticAnalysisError, match="eslint failed"):
            scorer.run_lint(tmp_path)


class TestJsRunTests:
    def test_missing_test_file(self, tmp_path: Path):
        scorer = JavaScriptStaticScorer()
        result = scorer.run_tests(tmp_path / "missing.test.js", tmp_path)
        assert result["total"] == 0
        assert "error" in result

    @patch("claude_benchmark.scoring.lang_javascript.subprocess.run")
    @patch("claude_benchmark.scoring.lang_javascript.shutil.which", return_value="/usr/bin/npx")
    def test_parses_jest_json(self, mock_which, mock_run, tmp_path: Path):
        test_file = tmp_path / "index.test.js"
        test_file.write_text("test('works', () => {});\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps({
                "numPassedTests": 3,
                "numFailedTests": 1,
                "numPendingTests": 0,
                "numTotalTests": 4,
                "testResults": [
                    {"perfStats": {"runtime": 150}},
                ],
            }),
            "stderr": "",
        })()
        scorer = JavaScriptStaticScorer()
        result = scorer.run_tests(test_file, tmp_path)
        assert result["passed"] == 3
        assert result["failed"] == 1
        assert result["total"] == 4
        assert result["duration"] == 0.15


class TestJsAnalyzeComplexity:
    def test_empty_list(self):
        scorer = JavaScriptStaticScorer()
        result = scorer.analyze_complexity([])
        assert result["blocks"] == []
        assert result["average_complexity"] == 0.0

    def test_heuristic_fallback(self, tmp_path: Path):
        """When cr is unavailable, falls back to keyword heuristic."""
        f = tmp_path / "complex.js"
        f.write_text(
            "function decide(x) {\n"
            "  if (x > 0) {\n"
            "    for (let i = 0; i < x; i++) {\n"
            "      if (i % 2 === 0) continue;\n"
            "    }\n"
            "  } else if (x < 0) {\n"
            "    while (x < 0) x++;\n"
            "  }\n"
            "}\n"
        )
        scorer = JavaScriptStaticScorer()
        with patch("claude_benchmark.scoring.lang_javascript.shutil.which", return_value=None):
            result = scorer.analyze_complexity([f])
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["complexity"] > 1

    def test_unreadable_file(self, tmp_path: Path):
        f = tmp_path / "bad.js"
        f.write_text("x")
        f.chmod(0o000)
        scorer = JavaScriptStaticScorer()
        with patch("claude_benchmark.scoring.lang_javascript.shutil.which", return_value=None):
            result = scorer.analyze_complexity([f])
        # Should get F-rank fallback
        assert result["blocks"][0]["rank"] == "F"
        assert result["blocks"][0]["complexity"] == 50
        f.chmod(0o644)  # cleanup


class TestJsRank:
    @pytest.mark.parametrize(
        "complexity,rank",
        [(1, "A"), (5, "A"), (6, "B"), (10, "B"), (11, "C"), (20, "C"),
         (21, "D"), (30, "D"), (31, "E"), (40, "E"), (41, "F")],
    )
    def test_rank_boundaries(self, complexity, rank):
        assert JavaScriptStaticScorer._rank(complexity) == rank


class TestJsRegistered:
    def test_js_in_registry(self):
        from claude_benchmark.scoring.registry import get_scorer
        from claude_benchmark.tasks.schema import Language

        scorer = get_scorer(Language.JAVASCRIPT)
        assert isinstance(scorer, JavaScriptStaticScorer)
