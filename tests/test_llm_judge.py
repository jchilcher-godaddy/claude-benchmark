"""Tests for the LLM judge scorer.

All tests mock subprocess.run (Claude Code CLI) -- no real API key required.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_benchmark.scoring.errors import LLMJudgeError
from claude_benchmark.scoring.llm_judge import LLMJudgeScorer
from claude_benchmark.scoring.models import LLMCriterionScore, LLMScore


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

def _make_valid_evaluations(
    criteria_scores: list[tuple[str, int, str]] | None = None,
) -> dict:
    """Build a valid evaluations dict matching the judge output schema."""
    if criteria_scores is None:
        criteria_scores = [
            ("code_readability", 4, "Clean code with good naming."),
            ("architecture_quality", 3, "Adequate structure."),
            ("instruction_adherence", 5, "All requirements met."),
            ("correctness_reasoning", 4, "Correct with good error handling."),
        ]
    evaluations = [
        {"criterion": name, "score": score, "reasoning": reasoning}
        for name, score, reasoning in criteria_scores
    ]
    return {"evaluations": evaluations}


def _make_cli_envelope(
    structured_output: dict | None = None,
    result_text: str = "",
) -> str:
    """Build a CLI --output-format json envelope string.

    Mimics the real CLI output which wraps the model response in::

        {"type": "result", "structured_output": {...}, "result": "...", ...}
    """
    envelope = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result_text,
    }
    if structured_output is not None:
        envelope["structured_output"] = structured_output
    return json.dumps(envelope)


def _make_valid_response(
    criteria_scores: list[tuple[str, int, str]] | None = None,
) -> str:
    """Build a valid CLI envelope with structured_output for the judge."""
    evals = _make_valid_evaluations(criteria_scores)
    return _make_cli_envelope(structured_output=evals)


def _mock_cli_result(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    """Create a mock subprocess.CompletedProcess mimicking Claude CLI output."""
    return subprocess.CompletedProcess(
        args=["npx", "claude"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@pytest.fixture
def scorer():
    """Create an LLMJudgeScorer."""
    return LLMJudgeScorer()


# ---------------------------------------------------------------------------
# Tests for _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Tests for LLMJudgeScorer._parse_response."""

    def test_valid_json_returns_criterion_scores(self, scorer):
        """Valid JSON matching expected schema returns list of LLMCriterionScore."""
        response = json.dumps(_make_valid_evaluations())
        expected = [
            "code_readability",
            "architecture_quality",
            "instruction_adherence",
            "correctness_reasoning",
        ]

        result = scorer._parse_response(response, expected)

        assert len(result) == 4
        assert all(isinstance(cs, LLMCriterionScore) for cs in result)
        assert result[0].name == "code_readability"
        assert result[0].score == 4
        assert result[0].reasoning == "Clean code with good naming."

    def test_missing_criterion_raises_value_error(self, scorer):
        """Response missing an expected criterion raises ValueError."""
        # Response has only 3 of 4 expected criteria
        evals = _make_valid_evaluations([
            ("code_readability", 4, "Good."),
            ("architecture_quality", 3, "OK."),
            ("instruction_adherence", 5, "Met."),
        ])
        response = json.dumps(evals)
        expected = [
            "code_readability",
            "architecture_quality",
            "instruction_adherence",
            "correctness_reasoning",
        ]

        with pytest.raises(ValueError, match="Missing criteria"):
            scorer._parse_response(response, expected)

    def test_score_out_of_range_zero_raises_error(self, scorer):
        """Score of 0 (below minimum 1) raises error."""
        evals = _make_valid_evaluations([
            ("code_readability", 0, "Terrible."),
            ("architecture_quality", 3, "OK."),
            ("instruction_adherence", 5, "Met."),
            ("correctness_reasoning", 4, "Good."),
        ])
        response = json.dumps(evals)
        expected = [
            "code_readability",
            "architecture_quality",
            "instruction_adherence",
            "correctness_reasoning",
        ]

        with pytest.raises(ValueError, match="Validation failed"):
            scorer._parse_response(response, expected)

    def test_score_out_of_range_six_raises_error(self, scorer):
        """Score of 6 (above maximum 5) raises error."""
        evals = _make_valid_evaluations([
            ("code_readability", 6, "Amazing."),
            ("architecture_quality", 3, "OK."),
            ("instruction_adherence", 5, "Met."),
            ("correctness_reasoning", 4, "Good."),
        ])
        response = json.dumps(evals)
        expected = [
            "code_readability",
            "architecture_quality",
            "instruction_adherence",
            "correctness_reasoning",
        ]

        with pytest.raises(ValueError, match="Validation failed"):
            scorer._parse_response(response, expected)

    def test_invalid_json_raises_decode_error(self, scorer):
        """Non-JSON text raises json.JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            scorer._parse_response("not valid json at all", ["code_readability"])

    def test_empty_evaluations_raises_value_error(self, scorer):
        """Empty evaluations list raises ValueError."""
        response = json.dumps({"evaluations": []})
        with pytest.raises(ValueError, match="evaluations"):
            scorer._parse_response(response, ["code_readability"])

    def test_missing_evaluations_key_raises_value_error(self, scorer):
        """JSON without 'evaluations' key raises ValueError."""
        response = json.dumps({"results": []})
        with pytest.raises(ValueError, match="evaluations"):
            scorer._parse_response(response, ["code_readability"])


# ---------------------------------------------------------------------------
# Tests for _extract_evaluation_json
# ---------------------------------------------------------------------------


class TestExtractEvaluationJson:
    """Tests for LLMJudgeScorer._extract_evaluation_json."""

    def test_structured_output_extracted(self):
        """structured_output dict is re-serialised as JSON string."""
        evals = {"evaluations": [{"criterion": "test", "score": 4, "reasoning": "OK"}]}
        envelope = _make_cli_envelope(structured_output=evals)

        result = LLMJudgeScorer._extract_evaluation_json(envelope)
        parsed = json.loads(result)

        assert parsed["evaluations"][0]["criterion"] == "test"

    def test_result_text_with_json_code_block(self):
        """JSON embedded in a markdown code block inside result text is extracted."""
        inner_json = '{"evaluations": [{"criterion": "x", "score": 3, "reasoning": "OK"}]}'
        result_text = f"Here is the evaluation:\n```json\n{inner_json}\n```\nDone."
        envelope = _make_cli_envelope(result_text=result_text)

        result = LLMJudgeScorer._extract_evaluation_json(envelope)
        parsed = json.loads(result)

        assert parsed["evaluations"][0]["criterion"] == "x"

    def test_result_text_with_bare_json(self):
        """Bare JSON object inside result text is extracted."""
        inner_json = '{"evaluations": [{"criterion": "y", "score": 5, "reasoning": "Great"}]}'
        result_text = f"Evaluation: {inner_json}"
        envelope = _make_cli_envelope(result_text=result_text)

        result = LLMJudgeScorer._extract_evaluation_json(envelope)
        parsed = json.loads(result)

        assert parsed["evaluations"][0]["criterion"] == "y"

    def test_non_json_stdout_returned_as_is(self):
        """Non-JSON stdout is returned as-is for downstream parsing to handle."""
        raw = "This is not JSON at all"
        result = LLMJudgeScorer._extract_evaluation_json(raw)
        assert result == raw

    def test_empty_stdout_raises_llm_judge_error(self):
        """Empty stdout raises LLMJudgeError with descriptive message."""
        with pytest.raises(LLMJudgeError, match="empty output"):
            LLMJudgeScorer._extract_evaluation_json("")

    def test_whitespace_only_raises_llm_judge_error(self):
        """Whitespace-only stdout raises LLMJudgeError."""
        with pytest.raises(LLMJudgeError, match="empty output"):
            LLMJudgeScorer._extract_evaluation_json("   \n  \t  ")

    def test_envelope_without_structured_or_result_raises(self):
        """Envelope missing both fields raises LLMJudgeError."""
        envelope = json.dumps({"type": "result", "subtype": "success"})
        with pytest.raises(LLMJudgeError, match="missing both"):
            LLMJudgeScorer._extract_evaluation_json(envelope)

    def test_structured_output_preferred_over_result(self):
        """structured_output is used even when result text also contains JSON."""
        evals = {"evaluations": [{"criterion": "preferred", "score": 5, "reasoning": "Best"}]}
        result_text = '{"evaluations": [{"criterion": "ignored", "score": 1, "reasoning": "Worst"}]}'
        envelope = _make_cli_envelope(structured_output=evals, result_text=result_text)

        result = LLMJudgeScorer._extract_evaluation_json(envelope)
        parsed = json.loads(result)

        assert parsed["evaluations"][0]["criterion"] == "preferred"


# ---------------------------------------------------------------------------
# Tests for _compute_llm_score
# ---------------------------------------------------------------------------


class TestComputeLLMScore:
    """Tests for LLMJudgeScorer._compute_llm_score."""

    def test_all_threes_average_3_normalized_50(self, scorer):
        """All scores of 3 -> average=3.0, normalized=50.0."""
        criteria = [
            LLMCriterionScore(name="a", score=3, reasoning="OK."),
            LLMCriterionScore(name="b", score=3, reasoning="OK."),
            LLMCriterionScore(name="c", score=3, reasoning="OK."),
            LLMCriterionScore(name="d", score=3, reasoning="OK."),
        ]
        result = scorer._compute_llm_score(criteria)

        assert isinstance(result, LLMScore)
        assert result.average == 3.0
        assert result.normalized == 50.0
        assert result.model_used == scorer.model

    def test_all_fives_average_5_normalized_100(self, scorer):
        """All scores of 5 -> average=5.0, normalized=100.0."""
        criteria = [
            LLMCriterionScore(name="a", score=5, reasoning="Excellent."),
            LLMCriterionScore(name="b", score=5, reasoning="Excellent."),
            LLMCriterionScore(name="c", score=5, reasoning="Excellent."),
            LLMCriterionScore(name="d", score=5, reasoning="Excellent."),
        ]
        result = scorer._compute_llm_score(criteria)

        assert result.average == 5.0
        assert result.normalized == 100.0

    def test_all_ones_average_1_normalized_0(self, scorer):
        """All scores of 1 -> average=1.0, normalized=0.0."""
        criteria = [
            LLMCriterionScore(name="a", score=1, reasoning="Poor."),
            LLMCriterionScore(name="b", score=1, reasoning="Poor."),
            LLMCriterionScore(name="c", score=1, reasoning="Poor."),
            LLMCriterionScore(name="d", score=1, reasoning="Poor."),
        ]
        result = scorer._compute_llm_score(criteria)

        assert result.average == 1.0
        assert result.normalized == 0.0

    def test_mixed_scores_1234_average_2_5_normalized_37_5(self, scorer):
        """[1,2,3,4] -> average=2.5, normalized=37.5."""
        criteria = [
            LLMCriterionScore(name="a", score=1, reasoning="Poor."),
            LLMCriterionScore(name="b", score=2, reasoning="Below."),
            LLMCriterionScore(name="c", score=3, reasoning="OK."),
            LLMCriterionScore(name="d", score=4, reasoning="Good."),
        ]
        result = scorer._compute_llm_score(criteria)

        assert result.average == 2.5
        assert result.normalized == 37.5


# ---------------------------------------------------------------------------
# Tests for judge_code
# ---------------------------------------------------------------------------


class TestJudgeCode:
    """Tests for LLMJudgeScorer.judge_code (mocked CLI)."""

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_valid_response_returns_llm_score(self, mock_run, scorer):
        """Mocked CLI returning valid response -> returns LLMScore."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        result = scorer.judge_code(
            code="def hello(): return 'world'",
            task_description="Write a hello function",
        )

        assert isinstance(result, LLMScore)
        assert len(result.criteria) == 4
        assert result.average == 4.0  # (4+3+5+4)/4
        assert result.normalized == 75.0  # (4.0-1)*25
        mock_run.assert_called_once()

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_retry_on_first_failure_succeeds(self, mock_run, scorer):
        """First call returns invalid JSON, second returns valid -> succeeds."""
        mock_run.side_effect = [
            _mock_cli_result("not json"),
            _mock_cli_result(_make_valid_response()),
        ]

        result = scorer.judge_code(
            code="def add(a, b): return a + b",
            task_description="Write an add function",
        )

        assert isinstance(result, LLMScore)
        assert mock_run.call_count == 2

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_double_failure_raises_llm_judge_error(self, mock_run, scorer):
        """Both attempts return invalid JSON -> raises LLMJudgeError."""
        mock_run.side_effect = [
            _mock_cli_result("invalid json 1"),
            _mock_cli_result("invalid json 2"),
        ]

        with pytest.raises(LLMJudgeError) as exc_info:
            scorer.judge_code(
                code="def broken(): pass",
                task_description="Write something",
            )

        assert exc_info.value.retry_attempted is True

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_custom_criteria_included_in_prompt(self, mock_run, scorer):
        """Custom criteria are appended to built-in criteria in the stdin prompt."""
        custom = [{"name": "test_coverage", "description": "Test completeness."}]

        # Need response with all 5 criteria (4 built-in + 1 custom)
        all_scores = [
            ("code_readability", 4, "Good."),
            ("architecture_quality", 3, "OK."),
            ("instruction_adherence", 5, "Met."),
            ("correctness_reasoning", 4, "Correct."),
            ("test_coverage", 4, "Well tested."),
        ]
        mock_run.return_value = _mock_cli_result(_make_valid_response(all_scores))

        result = scorer.judge_code(
            code="def tested(): pass",
            task_description="Write tested code",
            criteria=custom,
        )

        assert len(result.criteria) == 5

        # Verify the custom criterion appears in the stdin input
        call_kwargs = mock_run.call_args[1]  # keyword args
        stdin_prompt = call_kwargs.get("input", "")
        assert "test_coverage" in stdin_prompt
        assert "Test completeness" in stdin_prompt

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_cli_failure_raises_llm_judge_error(self, mock_run, scorer):
        """CLI non-zero exit is wrapped in LLMJudgeError."""
        mock_run.return_value = _mock_cli_result("", returncode=1, stderr="CLI error")

        with pytest.raises(LLMJudgeError, match="Claude CLI failed"):
            scorer.judge_code(
                code="def fail(): pass",
                task_description="Test CLI failure",
            )

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_cli_timeout_raises_llm_judge_error(self, mock_run, scorer):
        """CLI timeout is wrapped in LLMJudgeError."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="npx", timeout=120)

        with pytest.raises(LLMJudgeError, match="timed out"):
            scorer.judge_code(
                code="def fail(): pass",
                task_description="Test timeout",
            )

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_reference_solution_passed_to_prompt(self, mock_run, scorer):
        """Reference solution appears in the stdin prompt."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        scorer.judge_code(
            code="def my_impl(): pass",
            task_description="Implement feature",
            reference_solution="def reference_impl(): return 42",
        )

        call_kwargs = mock_run.call_args[1]
        stdin_prompt = call_kwargs.get("input", "")
        assert "Reference Solution" in stdin_prompt
        assert "reference_impl" in stdin_prompt

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_system_prompt_flag_used(self, mock_run, scorer):
        """CLI uses --system-prompt (replace) not --append-system-prompt."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        scorer.judge_code(
            code="def x(): pass",
            task_description="Test flags",
        )

        cli_args = mock_run.call_args[0][0]
        assert "--system-prompt" in cli_args
        assert "--append-system-prompt" not in cli_args

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_json_schema_flag_used(self, mock_run, scorer):
        """CLI uses --json-schema to enforce structured output."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        scorer.judge_code(
            code="def x(): pass",
            task_description="Test flags",
        )

        cli_args = mock_run.call_args[0][0]
        assert "--json-schema" in cli_args
        assert "--output-format" in cli_args

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_prompt_passed_via_stdin(self, mock_run, scorer):
        """User prompt is passed via stdin, not as a positional CLI argument."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        scorer.judge_code(
            code="def x(): pass",
            task_description="Test stdin",
        )

        call_kwargs = mock_run.call_args[1]
        assert "input" in call_kwargs
        assert call_kwargs["input"]  # non-empty

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_empty_stdout_raises_llm_judge_error(self, mock_run, scorer):
        """CLI returning empty stdout raises descriptive LLMJudgeError."""
        mock_run.return_value = _mock_cli_result("")

        with pytest.raises(LLMJudgeError, match="empty output"):
            scorer.judge_code(
                code="def x(): pass",
                task_description="Test empty",
            )


# ---------------------------------------------------------------------------
# Tests for score (convenience method)
# ---------------------------------------------------------------------------


class TestScore:
    """Tests for LLMJudgeScorer.score (directory-based scoring)."""

    def test_empty_directory_raises_llm_judge_error(self, scorer):
        """Empty directory with no .py files raises LLMJudgeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(LLMJudgeError, match="No Python files found"):
                scorer.score(
                    output_dir=Path(tmpdir),
                    task_description="Evaluate code",
                )

    def test_directory_with_only_test_files_raises_error(self, scorer):
        """Directory with only test_* files raises LLMJudgeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test_main.py").write_text("def test_it(): pass")
            with pytest.raises(LLMJudgeError, match="No Python files found"):
                scorer.score(
                    output_dir=Path(tmpdir),
                    task_description="Evaluate code",
                )

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_directory_with_py_files_calls_judge_code(self, mock_run, scorer):
        """Directory with .py files concatenates them and calls judge_code."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("def hello():\n    return 'world'\n")
            (tmppath / "utils.py").write_text("def helper():\n    pass\n")

            result = scorer.score(
                output_dir=tmppath,
                task_description="Write a hello app",
            )

        assert isinstance(result, LLMScore)
        # Verify the concatenated code was passed via stdin
        call_kwargs = mock_run.call_args[1]
        stdin_prompt = call_kwargs.get("input", "")
        assert "main.py" in stdin_prompt
        assert "utils.py" in stdin_prompt
        assert "def hello():" in stdin_prompt
        assert "def helper():" in stdin_prompt

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_score_with_reference_solution_path(self, mock_run, scorer):
        """Reference solution path is read and passed to judge_code."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("def solve(): return 42\n")
            ref_path = tmppath / "reference.py"
            ref_path.write_text("def solve(): return 42  # reference\n")

            result = scorer.score(
                output_dir=tmppath,
                task_description="Solve problem",
                reference_solution_path=ref_path,
            )

        assert isinstance(result, LLMScore)
        call_kwargs = mock_run.call_args[1]
        stdin_prompt = call_kwargs.get("input", "")
        assert "reference" in stdin_prompt

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_score_ignores_pycache(self, mock_run, scorer):
        """Files in __pycache__ are excluded."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text("x = 1\n")
            cache_dir = tmppath / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "main.cpython-312.pyc").write_text("compiled")

            result = scorer.score(
                output_dir=tmppath,
                task_description="Test pycache exclusion",
            )

        assert isinstance(result, LLMScore)
        call_kwargs = mock_run.call_args[1]
        stdin_prompt = call_kwargs.get("input", "")
        assert "__pycache__" not in stdin_prompt


# ---------------------------------------------------------------------------
# Integration-style tests (still mocked)
# ---------------------------------------------------------------------------


class TestIntegration:
    """Higher-level tests for the full scoring flow."""

    def test_default_model_is_haiku(self):
        """Default model is Claude Haiku 4.5 to avoid self-bias."""
        scorer = LLMJudgeScorer()
        assert scorer.model == "haiku"

    def test_custom_model_override(self):
        """Custom model can be specified."""
        scorer = LLMJudgeScorer(model="claude-sonnet-4-5-20250929")
        assert scorer.model == "claude-sonnet-4-5-20250929"

    @patch("claude_benchmark.scoring.llm_judge.subprocess.run")
    def test_model_used_in_score(self, mock_run, scorer):
        """model_used field in LLMScore reflects the scorer's model."""
        mock_run.return_value = _mock_cli_result(_make_valid_response())

        result = scorer.judge_code(
            code="def x(): pass",
            task_description="Test",
        )

        assert result.model_used == scorer.model
