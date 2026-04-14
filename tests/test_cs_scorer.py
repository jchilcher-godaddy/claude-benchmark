"""Tests for the C# static analysis scorer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from claude_benchmark.scoring.errors import StaticAnalysisError
from claude_benchmark.scoring.lang_csharp import CSharpStaticScorer


class TestCsScorerMetadata:
    def test_source_glob(self):
        scorer = CSharpStaticScorer()
        assert scorer.source_glob() == "*.cs"

    def test_test_glob_patterns(self):
        scorer = CSharpStaticScorer()
        patterns = scorer.test_glob_patterns()
        assert "*Tests.cs" in patterns
        assert "*Test.cs" in patterns

    def test_comment_prefixes(self):
        scorer = CSharpStaticScorer()
        assert scorer.comment_prefixes() == ["//", "///"]


class TestCsCountLoc:
    def test_counts_cs_lines(self, tmp_path: Path):
        f = tmp_path / "Program.cs"
        f.write_text(
            "using System;\n\n"
            "namespace App\n{\n"
            "    class Program\n    {\n"
            "        static void Main()\n        {\n"
            "            Console.WriteLine(\"hi\");\n"
            "        }\n    }\n}\n"
        )
        scorer = CSharpStaticScorer()
        loc = scorer.count_loc([f])
        # All non-blank lines: using, namespace, {, class, {, static, {, Console, }, }, }
        assert loc == 11

    def test_excludes_cs_comments(self, tmp_path: Path):
        f = tmp_path / "Service.cs"
        f.write_text(
            "// single line comment\n"
            "/// <summary>XML doc comment</summary>\n"
            "public class Service { }\n"
        )
        scorer = CSharpStaticScorer()
        assert scorer.count_loc([f]) == 1


class TestCsFindSourceFiles:
    def test_excludes_test_files(self, tmp_path: Path):
        (tmp_path / "Calculator.cs").write_text("class Calculator {}\n")
        (tmp_path / "CalculatorTests.cs").write_text("class CalculatorTests {}\n")
        (tmp_path / "CalcTest.cs").write_text("class CalcTest {}\n")
        scorer = CSharpStaticScorer()
        files = scorer.find_source_files(tmp_path)
        names = [f.name for f in files]
        assert "Calculator.cs" in names
        assert "CalculatorTests.cs" not in names
        assert "CalcTest.cs" not in names


class TestCsRunLint:
    def test_empty_directory(self, tmp_path: Path):
        scorer = CSharpStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result == {"violations": [], "count": 0}

    def test_no_csproj(self, tmp_path: Path):
        (tmp_path / "Program.cs").write_text("class P {}\n")
        scorer = CSharpStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result == {"violations": [], "count": 0}

    @patch("claude_benchmark.scoring.lang_csharp.shutil.which", return_value=None)
    def test_missing_dotnet_raises(self, mock_which, tmp_path: Path):
        (tmp_path / "Program.cs").write_text("class P {}\n")
        (tmp_path / "App.csproj").write_text("<Project />\n")
        scorer = CSharpStaticScorer()
        with pytest.raises(StaticAnalysisError, match="dotnet not found"):
            scorer.run_lint(tmp_path)

    @patch("claude_benchmark.scoring.lang_csharp.subprocess.run")
    @patch("claude_benchmark.scoring.lang_csharp.shutil.which", return_value="/usr/bin/dotnet")
    def test_clean_code(self, mock_which, mock_run, tmp_path: Path):
        (tmp_path / "Program.cs").write_text("class P {}\n")
        (tmp_path / "App.csproj").write_text("<Project />\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        })()
        scorer = CSharpStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result["count"] == 0

    @patch("claude_benchmark.scoring.lang_csharp.subprocess.run")
    @patch("claude_benchmark.scoring.lang_csharp.shutil.which", return_value="/usr/bin/dotnet")
    def test_parses_diagnostic_lines(self, mock_which, mock_run, tmp_path: Path):
        (tmp_path / "Program.cs").write_text("class P {}\n")
        (tmp_path / "App.csproj").write_text("<Project />\n")
        mock_run.return_value = type("Result", (), {
            "returncode": 1,
            "stdout": "Program.cs(5,10): warning IDE0003: Name can be simplified\n",
            "stderr": "",
        })()
        scorer = CSharpStaticScorer()
        result = scorer.run_lint(tmp_path)
        assert result["count"] == 1
        assert result["violations"][0]["code"] == "IDE0003"
        assert result["violations"][0]["location"]["row"] == 5


class TestCsRunTests:
    @patch("claude_benchmark.scoring.lang_csharp.shutil.which", return_value="/usr/bin/dotnet")
    def test_no_csproj(self, mock_which, tmp_path: Path):
        scorer = CSharpStaticScorer()
        result = scorer.run_tests(tmp_path / "Tests.cs", tmp_path)
        assert result["total"] == 0
        assert "error" in result

    @patch("claude_benchmark.scoring.lang_csharp.shutil.which", return_value=None)
    def test_missing_dotnet_raises(self, mock_which, tmp_path: Path):
        scorer = CSharpStaticScorer()
        with pytest.raises(StaticAnalysisError, match="dotnet not found"):
            scorer.run_tests(tmp_path / "Tests.cs", tmp_path)


class TestCsParseTrx:
    def test_parses_valid_trx(self, tmp_path: Path):
        trx = tmp_path / "results.trx"
        trx.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">\n'
            '  <ResultSummary outcome="Completed">\n'
            '    <Counters total="5" passed="3" failed="1" />\n'
            '  </ResultSummary>\n'
            '  <Times start="2026-01-01T10:00:00.000+00:00" '
            'finish="2026-01-01T10:00:02.500+00:00" />\n'
            '</TestRun>\n'
        )
        scorer = CSharpStaticScorer()
        result = scorer._parse_trx(trx, exit_code=1)
        assert result["passed"] == 3
        assert result["failed"] == 1
        assert result["total"] == 5
        assert result["skipped"] == 1  # 5 - 3 - 1
        assert result["duration"] == pytest.approx(2.5, abs=0.01)

    def test_invalid_trx(self, tmp_path: Path):
        trx = tmp_path / "bad.trx"
        trx.write_text("not xml")
        scorer = CSharpStaticScorer()
        result = scorer._parse_trx(trx, exit_code=1)
        assert result["total"] == 0
        assert "error" in result


class TestCsAnalyzeComplexity:
    def test_empty_list(self):
        scorer = CSharpStaticScorer()
        result = scorer.analyze_complexity([])
        assert result["blocks"] == []
        assert result["average_complexity"] == 0.0

    def test_simple_method(self, tmp_path: Path):
        f = tmp_path / "Calculator.cs"
        f.write_text(
            "public class Calculator\n{\n"
            "    public int Add(int a, int b)\n    {\n"
            "        return a + b;\n"
            "    }\n}\n"
        )
        scorer = CSharpStaticScorer()
        result = scorer.analyze_complexity([f])
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["name"] == "Add"
        assert result["blocks"][0]["complexity"] == 1  # no branches
        assert result["blocks"][0]["rank"] == "A"

    def test_branching_method(self, tmp_path: Path):
        f = tmp_path / "Logic.cs"
        f.write_text(
            "public class Logic\n{\n"
            "    public string Decide(int x)\n    {\n"
            "        if (x > 0)\n"
            "        {\n"
            "            if (x > 100)\n"
            "                return \"big\";\n"
            "            return \"positive\";\n"
            "        }\n"
            "        else if (x == 0)\n"
            "            return \"zero\";\n"
            "        for (int i = 0; i < 10; i++)\n"
            "        {\n"
            "            if (i % 2 == 0) continue;\n"
            "        }\n"
            "        return \"negative\";\n"
            "    }\n}\n"
        )
        scorer = CSharpStaticScorer()
        result = scorer.analyze_complexity([f])
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["complexity"] > 1

    def test_multiple_methods(self, tmp_path: Path):
        f = tmp_path / "Service.cs"
        f.write_text(
            "public class Service\n{\n"
            "    public void DoA()\n    {\n"
            "        Console.WriteLine(\"a\");\n"
            "    }\n"
            "    public void DoB()\n    {\n"
            "        if (true) return;\n"
            "    }\n}\n"
        )
        scorer = CSharpStaticScorer()
        result = scorer.analyze_complexity([f])
        assert len(result["blocks"]) == 2

    def test_unreadable_file(self, tmp_path: Path):
        f = tmp_path / "Bad.cs"
        f.write_text("x")
        f.chmod(0o000)
        scorer = CSharpStaticScorer()
        result = scorer.analyze_complexity([f])
        assert result["blocks"][0]["rank"] == "F"
        assert result["blocks"][0]["complexity"] == 50
        f.chmod(0o644)  # cleanup


class TestCsExtractBody:
    def test_simple_body(self):
        source = "void Foo() { return; }"
        body = CSharpStaticScorer._extract_body(source, len("void Foo() "))
        assert body == "{ return; }"

    def test_nested_braces(self):
        source = "void Bar() { if (true) { x++; } }"
        body = CSharpStaticScorer._extract_body(source, len("void Bar() "))
        assert body == "{ if (true) { x++; } }"

    def test_no_braces(self):
        body = CSharpStaticScorer._extract_body("no braces here", 0)
        assert body == ""


class TestCsCountComplexity:
    def test_no_branches(self):
        assert CSharpStaticScorer._count_complexity("{ return 1; }") == 1

    def test_single_if(self):
        assert CSharpStaticScorer._count_complexity("{ if (x) return 1; }") == 2

    def test_multiple_branches(self):
        body = "{ if (x) {} else if (y) {} for (;;) {} while (true) {} }"
        c = CSharpStaticScorer._count_complexity(body)
        # base(1) + if(1) + else if(1) + for(1) + while(1) = 5
        assert c == 5

    def test_logical_operators(self):
        body = "{ if (a && b || c) {} }"
        c = CSharpStaticScorer._count_complexity(body)
        # base(1) + if(1) + &&(1) + ||(1) = 4
        assert c == 4

    def test_empty_body(self):
        assert CSharpStaticScorer._count_complexity("") == 1


class TestCsRank:
    @pytest.mark.parametrize(
        "complexity,rank",
        [(1, "A"), (5, "A"), (6, "B"), (10, "B"), (11, "C"), (20, "C"),
         (21, "D"), (30, "D"), (31, "E"), (40, "E"), (41, "F")],
    )
    def test_rank_boundaries(self, complexity, rank):
        assert CSharpStaticScorer._rank(complexity) == rank


class TestCsRegistered:
    def test_cs_in_registry(self):
        from claude_benchmark.scoring.registry import get_scorer
        from claude_benchmark.tasks.schema import Language

        scorer = get_scorer(Language.CSHARP)
        assert isinstance(scorer, CSharpStaticScorer)
