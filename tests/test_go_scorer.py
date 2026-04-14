"""Tests for the Go static analysis scorer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_benchmark.scoring.errors import StaticAnalysisError
from claude_benchmark.scoring.lang_go import GoStaticScorer


class TestGoScorerMetadata:
    def test_source_glob(self):
        scorer = GoStaticScorer()
        assert scorer.source_glob() == "*.go"

    def test_test_glob_patterns(self):
        scorer = GoStaticScorer()
        assert scorer.test_glob_patterns() == ["*_test.go"]

    def test_comment_prefixes(self):
        scorer = GoStaticScorer()
        assert scorer.comment_prefixes() == ["//"]


class TestGoCountLoc:
    def test_counts_go_lines(self, tmp_path: Path):
        f = tmp_path / "main.go"
        f.write_text("package main\n\nimport \"fmt\"\n\nfunc main() {\n\tfmt.Println(\"hi\")\n}\n")
        scorer = GoStaticScorer()
        # Lines: "package main", "import \"fmt\"", "func main() {", "fmt.Println(\"hi\")", "}" = 5
        assert scorer.count_loc([f]) == 5

    def test_excludes_go_comments(self, tmp_path: Path):
        f = tmp_path / "main.go"
        f.write_text("// Package main is the entry point.\npackage main\n// comment\nvar x = 1\n")
        scorer = GoStaticScorer()
        assert scorer.count_loc([f]) == 2


class TestGoFindSourceFiles:
    def test_excludes_test_files(self, tmp_path: Path):
        (tmp_path / "main.go").write_text("package main\n")
        (tmp_path / "main_test.go").write_text("package main\n")
        scorer = GoStaticScorer()
        files = scorer.find_source_files(tmp_path)
        names = [f.name for f in files]
        assert "main.go" in names
        assert "main_test.go" not in names


class TestGoRunLint:
    def test_empty_directory(self, tmp_path: Path):
        scorer = GoStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result == {"violations": [], "count": 0}

    @patch("claude_benchmark.scoring.lang_go.shutil.which", return_value=None)
    def test_missing_tool_raises(self, mock_which, tmp_path: Path):
        (tmp_path / "main.go").write_text("package main\n")
        scorer = GoStaticScorer()
        with pytest.raises(StaticAnalysisError, match="golangci-lint not found"):
            scorer.run_lint(tmp_path)

    @patch("claude_benchmark.scoring.lang_go.subprocess.run")
    @patch("claude_benchmark.scoring.lang_go.shutil.which", return_value="/usr/bin/golangci-lint")
    def test_parses_violations(self, mock_which, mock_run, tmp_path: Path):
        (tmp_path / "main.go").write_text("package main\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 1,
            "stdout": json.dumps({
                "Issues": [
                    {
                        "FromLinter": "errcheck",
                        "Text": "Error return value not checked",
                        "Pos": {"Filename": "main.go", "Line": 5, "Column": 2},
                    }
                ]
            }),
            "stderr": "",
        })()
        scorer = GoStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result["count"] == 1
        assert result["violations"][0]["code"] == "errcheck"

    @patch("claude_benchmark.scoring.lang_go.subprocess.run")
    @patch("claude_benchmark.scoring.lang_go.shutil.which", return_value="/usr/bin/golangci-lint")
    def test_clean_code(self, mock_which, mock_run, tmp_path: Path):
        (tmp_path / "main.go").write_text("package main\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps({"Issues": None}),
            "stderr": "",
        })()
        scorer = GoStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result["count"] == 0

    @patch("claude_benchmark.scoring.lang_go.subprocess.run")
    @patch("claude_benchmark.scoring.lang_go.shutil.which", return_value="/usr/bin/golangci-lint")
    def test_tool_failure_raises(self, mock_which, mock_run, tmp_path: Path):
        (tmp_path / "main.go").write_text("package main\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 3,
            "stdout": "",
            "stderr": "internal error",
        })()
        scorer = GoStaticScorer()
        with pytest.raises(StaticAnalysisError, match="golangci-lint failed"):
            scorer.run_lint(tmp_path)


class TestGoRunTests:
    @patch("claude_benchmark.scoring.lang_go.shutil.which", return_value=None)
    def test_missing_tool_raises(self, mock_which, tmp_path: Path):
        scorer = GoStaticScorer()
        with pytest.raises(StaticAnalysisError, match="go not found"):
            scorer.run_tests(tmp_path / "main_test.go", tmp_path)

    @patch("claude_benchmark.scoring.lang_go.shutil.which", return_value="/usr/bin/go")
    def test_no_go_mod(self, mock_which, tmp_path: Path):
        scorer = GoStaticScorer()
        result = scorer.run_tests(tmp_path / "main_test.go", tmp_path)
        assert result["error"] == f"No go.mod found in {tmp_path}"
        assert result["total"] == 0

    @patch("claude_benchmark.scoring.lang_go.subprocess.run")
    @patch("claude_benchmark.scoring.lang_go.shutil.which", return_value="/usr/bin/go")
    def test_parses_json_events(self, mock_which, mock_run, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module example.com/test\n")
        events = "\n".join([
            json.dumps({"Action": "run", "Test": "TestAdd"}),
            json.dumps({"Action": "pass", "Test": "TestAdd"}),
            json.dumps({"Action": "run", "Test": "TestSub"}),
            json.dumps({"Action": "fail", "Test": "TestSub"}),
            json.dumps({"Action": "run", "Test": "TestSkip"}),
            json.dumps({"Action": "skip", "Test": "TestSkip"}),
            json.dumps({"Action": "pass", "Elapsed": 0.5}),
        ])
        mock_run.return_value = type("Result", (), {
            "returncode": 1,
            "stdout": events,
            "stderr": "",
        })()
        scorer = GoStaticScorer()
        result = scorer.run_tests(tmp_path / "main_test.go", tmp_path)
        assert result["passed"] == 1
        assert result["failed"] == 1
        assert result["skipped"] == 1
        assert result["total"] == 3
        assert result["duration"] == 0.5


class TestGoAnalyzeComplexity:
    def test_empty_list(self):
        scorer = GoStaticScorer()
        result = scorer.analyze_complexity([])
        assert result["average_complexity"] == 0.0
        assert result["blocks"] == []

    @patch("claude_benchmark.scoring.lang_go.subprocess.run")
    @patch("claude_benchmark.scoring.lang_go.shutil.which", return_value="/usr/bin/gocyclo")
    def test_parses_gocyclo_output(self, mock_which, mock_run, tmp_path: Path):
        f = tmp_path / "main.go"
        f.write_text("package main\nfunc main() {}\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 0,
            "stdout": "3 main main main.go:2:1\n7 main handler main.go:10:1\n",
            "stderr": "",
        })()
        scorer = GoStaticScorer()
        result = scorer.analyze_complexity([f])
        assert len(result["blocks"]) == 2
        assert result["blocks"][0]["complexity"] == 3
        assert result["blocks"][0]["rank"] == "A"
        assert result["blocks"][1]["complexity"] == 7
        assert result["blocks"][1]["rank"] == "B"
        assert result["average_complexity"] == 5.0
        assert result["max_complexity"] == 7


class TestGoRank:
    @pytest.mark.parametrize(
        "complexity,rank",
        [(1, "A"), (5, "A"), (6, "B"), (10, "B"), (11, "C"), (20, "C"),
         (21, "D"), (30, "D"), (31, "E"), (40, "E"), (41, "F"), (99, "F")],
    )
    def test_rank_boundaries(self, complexity, rank):
        assert GoStaticScorer._rank(complexity) == rank


class TestGoRegistered:
    def test_go_in_registry(self):
        from claude_benchmark.scoring.registry import get_scorer
        from claude_benchmark.tasks.schema import Language

        scorer = get_scorer(Language.GO)
        assert isinstance(scorer, GoStaticScorer)
