"""LLM-as-judge scorer for claude-benchmark.

Uses the Claude Code CLI (``npx``) to evaluate code with a structured rubric,
matching the same invocation pattern used by the benchmark worker so that no
separate ``ANTHROPIC_API_KEY`` is required.  Supports built-in criteria,
custom criteria, retry logic on validation failure, and graceful degradation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path

import anthropic
from pydantic import ValidationError

from claude_benchmark.execution.client import create_client, create_proxy_client, resolve_model_id

from .errors import LLMJudgeError
from .models import LLMCriterionScore, LLMScore
from .prompts import (
    BUILTIN_CRITERIA,
    DEFAULT_JUDGE_MODEL,
    JUDGE_OUTPUT_SCHEMA,
    JUDGE_SYSTEM_PROMPT,
    format_judge_user_prompt,
)

_NPX_CLAUDE_PACKAGE = "@anthropic-ai/claude-code@latest"


logger = logging.getLogger(__name__)


class LLMJudgeScorer:
    """Scores code using an LLM-as-judge with a structured rubric.

    Invokes the Claude Code CLI (via ``npx``) with the judge system prompt
    and evaluation criteria, parses the JSON response, validates via
    Pydantic, and returns an LLMScore with per-criterion scores and a
    normalized total.

    Args:
        model: Model ID for the judge. Defaults to Claude Haiku 4.5 to
            avoid self-bias when benchmarking other Claude models.
    """

    def __init__(
        self,
        model: str | None = None,
        use_direct_api: bool = False,
        judge_model: str | None = None,
    ) -> None:
        # ``judge_model`` is the new provider-abstracted spec (haiku, sonnet,
        # opus, gpt-4o, gemini-2.5-pro, openai:..., gemini:...). It supersedes
        # ``model`` when both are passed but defaults to ``model`` for
        # backwards compatibility.
        spec = judge_model or model or DEFAULT_JUDGE_MODEL
        self.model = spec
        self.use_direct_api = use_direct_api
        self._logger = logging.getLogger(__name__)
        self._provider = self._resolve_provider(spec)

    def _resolve_provider(self, spec: str):
        """Return a JudgeProvider for non-Anthropic specs, else None.

        Anthropic specs (haiku/sonnet/opus/claude-*) keep the legacy
        in-class call path untouched. Cross-family specs route through
        the provider registry.
        """
        from .judges.registry import (
            _ANTHROPIC_ALIASES,
            get_judge,
        )

        lower = spec.lower()
        if lower in _ANTHROPIC_ALIASES or lower.startswith("claude-"):
            return None
        # Anthropic explicit prefix also keeps legacy path
        if lower.startswith("anthropic:"):
            return None
        return get_judge(spec)

    def _parse_response(
        self,
        response_text: str,
        expected_criteria: list[str],
    ) -> list[LLMCriterionScore]:
        """Parse and validate the JSON response from the LLM judge.

        Args:
            response_text: Raw JSON string from the LLM response.
            expected_criteria: List of criterion names that must be present.

        Returns:
            List of validated LLMCriterionScore instances.

        Raises:
            json.JSONDecodeError: If response_text is not valid JSON.
            ValueError: If validation fails (missing criteria, bad scores, etc.).
        """
        data = json.loads(response_text)

        evaluations = data.get("evaluations")
        if not evaluations or not isinstance(evaluations, list):
            raise ValueError(
                "Response missing 'evaluations' list or evaluations is empty"
            )

        criterion_scores: list[LLMCriterionScore] = []
        for evaluation in evaluations:
            try:
                score_obj = LLMCriterionScore(
                    name=evaluation["criterion"],
                    score=int(evaluation["score"]),
                    reasoning=evaluation["reasoning"],
                )
            except (KeyError, TypeError) as exc:
                raise ValueError(
                    f"Invalid evaluation entry {evaluation!r}: {exc}"
                ) from exc
            except ValidationError as exc:
                raise ValueError(
                    f"Validation failed for criterion "
                    f"'{evaluation.get('criterion', '?')}': {exc}"
                ) from exc

            if not score_obj.reasoning.strip():
                raise ValueError(
                    f"Empty reasoning for criterion '{score_obj.name}'"
                )
            criterion_scores.append(score_obj)

        # Verify all expected criteria are present
        found_names = {cs.name for cs in criterion_scores}
        missing = set(expected_criteria) - found_names
        if missing:
            raise ValueError(
                f"Missing criteria in response: {sorted(missing)}. "
                f"Found: {sorted(found_names)}"
            )

        return criterion_scores

    def _compute_llm_score(
        self,
        criterion_scores: list[LLMCriterionScore],
    ) -> LLMScore:
        """Compute aggregate LLM score from individual criterion scores.

        Normalization: (average - 1) * 25.0
        Maps 1->0, 2->25, 3->50, 4->75, 5->100 per locked decision.
        """
        total = sum(cs.score for cs in criterion_scores)
        average = total / len(criterion_scores)
        normalized = (average - 1) * 25.0

        provider_name = self._provider.provider if self._provider else "anthropic"
        provider_model = self._provider.model_id if self._provider else self.model
        return LLMScore(
            criteria=criterion_scores,
            average=round(average, 2),
            normalized=round(normalized, 2),
            model_used=self.model,
            judge_provider=provider_name,
            judge_model_id=provider_model,
        )

    def judge_code(
        self,
        code: str,
        task_description: str,
        criteria: list[dict[str, str]] | None = None,
        reference_solution: str | None = None,
        language: str = "python",
    ) -> LLMScore:
        """Score code using the LLM judge.

        Merges built-in criteria with any custom criteria, calls the
        Anthropic API, parses and validates the response, and returns
        an LLMScore.

        Retries once on parse/validation failure with a more explicit prompt.
        Raises LLMJudgeError if both attempts fail.

        Args:
            code: The source code to evaluate.
            task_description: Description of the task the code implements.
            criteria: Optional custom criteria to add alongside the 4 built-in.
            reference_solution: Optional reference implementation for comparison.
            language: Language name for code fence formatting in prompts.

        Returns:
            LLMScore with per-criterion scores and normalized total.

        Raises:
            LLMJudgeError: If API call fails or response cannot be parsed
                after retry.
        """
        # Merge built-in + custom criteria
        all_criteria = list(BUILTIN_CRITERIA)
        if criteria:
            all_criteria.extend(criteria)

        expected_names = [c["name"] for c in all_criteria]

        # Build user prompt
        user_prompt = format_judge_user_prompt(
            task_description=task_description,
            code=code,
            criteria=all_criteria,
            reference_solution=reference_solution,
            language=language,
        )

        # Cross-family judge path (OpenAI, Gemini): route through the
        # JudgeProvider abstraction. Anthropic specs continue to use the
        # legacy CLI/direct/proxy chain below.
        if self._provider is not None:
            return self._judge_via_provider(user_prompt, expected_names)

        # First attempt — prefer proxy > direct API > CLI
        call_fn = self._select_call_fn()
        try:
            response_text = call_fn(user_prompt)
            criterion_scores = self._parse_response(response_text, expected_names)
            return self._compute_llm_score(criterion_scores)
        except LLMJudgeError:
            # API unavailable (no credentials); fall back to CLI
            self._logger.info("API unavailable, falling back to CLI")
            call_fn = self._call_api
            try:
                response_text = call_fn(user_prompt)
                criterion_scores = self._parse_response(response_text, expected_names)
                return self._compute_llm_score(criterion_scores)
            except (json.JSONDecodeError, ValueError, ValidationError):
                pass  # fall through to retry
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            self._logger.warning(
                "First judge attempt failed: %s. Retrying with explicit prompt.",
                exc,
            )

        # Retry with more explicit prompt
        retry_prompt = (
            user_prompt
            + "\n\nIMPORTANT: Return ONLY valid JSON matching the exact schema "
            "above. Each criterion must have integer score 1-5."
        )

        try:
            response_text = call_fn(retry_prompt)
            criterion_scores = self._parse_response(response_text, expected_names)
            return self._compute_llm_score(criterion_scores)
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            raise LLMJudgeError(
                f"LLM judge failed after retry: {exc}",
                retry_attempted=True,
            ) from exc

    def _judge_via_provider(
        self,
        user_prompt: str,
        expected_names: list[str],
    ) -> LLMScore:
        """Run the judge through a non-Anthropic JudgeProvider.

        Performs one call plus one retry with an explicit reminder if the
        first response doesn't validate. Mirrors the retry behavior of
        the legacy Anthropic path.
        """
        from .judges.base import JudgeError

        provider = self._provider
        assert provider is not None  # narrow for type-checkers

        try:
            evaluations = provider.score(
                user_prompt, JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA
            )
            criterion_scores = self._parse_response(
                json.dumps({"evaluations": evaluations}), expected_names
            )
            return self._compute_llm_score(criterion_scores)
        except (JudgeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
            self._logger.warning(
                "First %s judge attempt failed: %s. Retrying with explicit prompt.",
                provider.provider, exc,
            )

        retry_prompt = (
            user_prompt
            + "\n\nIMPORTANT: Return ONLY valid JSON matching the exact schema "
            "above. Each criterion must have integer score 1-5."
        )
        try:
            evaluations = provider.score(
                retry_prompt, JUDGE_SYSTEM_PROMPT, JUDGE_OUTPUT_SCHEMA
            )
            criterion_scores = self._parse_response(
                json.dumps({"evaluations": evaluations}), expected_names
            )
            return self._compute_llm_score(criterion_scores)
        except (JudgeError, json.JSONDecodeError, ValueError, ValidationError) as exc:
            raise LLMJudgeError(
                f"{provider.provider} judge failed after retry: {exc}",
                retry_attempted=True,
            ) from exc

    def _select_call_fn(self):
        """Select the best available API call function.

        Priority: proxy (if direct_api + proxy configured) > direct API > CLI.
        Matches the routing logic in worker.py.
        """
        if self.use_direct_api:
            from claude_benchmark.execution.proxy_auth import is_proxy_configured
            if is_proxy_configured():
                self._logger.debug("LLM judge using proxy path")
                return self._call_api_proxy
        return self._call_api_direct

    def _call_api_proxy(self, user_prompt: str) -> str:
        """Call proxy (OpenAI-compatible) API with temperature=0 for deterministic judging.

        Returns:
            A JSON string containing the ``evaluations`` array.

        Raises:
            LLMJudgeError: If the API call fails or credentials are unavailable.
        """
        model_id = resolve_model_id(self.model, use_proxy=True)

        try:
            client = create_proxy_client()
            messages: list[dict] = [
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            response = client.chat.completions.create(
                model=model_id,
                max_tokens=2048,
                temperature=0,
                messages=messages,
            )
        except Exception as exc:
            raise LLMJudgeError(f"proxy API call failed: {exc}") from exc

        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message or not choice.message.content:
            raise LLMJudgeError("proxy API returned no content")

        return self._extract_json(choice.message.content)

    def _call_api_direct(self, user_prompt: str) -> str:
        """Call the Anthropic API directly with temperature=0 for deterministic judging.

        Uses AnthropicBedrock client (same as worker.py) to bypass the CLI
        and set temperature=0, ensuring reproducible judge scores.

        Returns:
            A JSON string containing the ``evaluations`` array.

        Raises:
            LLMJudgeError: If the API call fails or credentials are unavailable.
        """
        model_id = resolve_model_id(self.model, use_direct_api=self.use_direct_api)

        try:
            client = create_client(use_direct_api=self.use_direct_api)
            response = client.messages.create(
                model=model_id,
                max_tokens=2048,
                temperature=0,
                system=JUDGE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            raise LLMJudgeError(f"Direct API call failed: {exc}") from exc

        # Extract text from the response
        text_parts = [
            block.text for block in response.content if block.type == "text"
        ]
        if not text_parts:
            raise LLMJudgeError("Direct API returned no text content")

        return self._extract_json("\n".join(text_parts))

    @staticmethod
    def _extract_json(raw_text: str) -> str:
        """Extract JSON from model response text.

        Handles responses wrapped in markdown code blocks or bare JSON.
        """
        code_block = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL
        )
        if code_block:
            return code_block.group(1)

        bare_json = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if bare_json:
            return bare_json.group(0)

        return raw_text

    @staticmethod
    def _clean_env() -> dict[str, str]:
        """Build a subprocess environment with ``CLAUDECODE`` removed.

        The Claude Code CLI refuses to start when it detects the
        ``CLAUDECODE`` variable (set by a parent Claude Code session).
        Stripping it allows the benchmark to invoke the CLI as a nested
        subprocess without hitting the "cannot be launched inside another
        Claude Code session" guard.
        """
        return {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    def _call_api(self, user_prompt: str) -> str:
        """Call Claude via the Claude Code CLI and return the evaluation JSON.

        Uses the same ``npx`` invocation as the benchmark worker so that
        no separate ``ANTHROPIC_API_KEY`` is needed.

        Key design choices:

        * ``--system-prompt`` (replace) instead of ``--append-system-prompt``
          to prevent the user's global CLAUDE.md from overriding the judge
          instructions.
        * ``--output-format json`` so the CLI wraps the response in a
          structured envelope we can parse reliably.
        * ``--json-schema`` to force the model to produce structured output
          that the CLI places in a dedicated ``structured_output`` field.
        * The user prompt is piped via *stdin* rather than passed as a
          positional argument, which is more robust for long prompts.

        Returns:
            A JSON string containing the ``evaluations`` array.

        Raises:
            LLMJudgeError: If the CLI call fails or the response cannot be
                extracted.
        """
        cmd = [
            "npx",
            _NPX_CLAUDE_PACKAGE,
            "--print",
            "--dangerously-skip-permissions",
            "--model",
            self.model,
            "--system-prompt",
            JUDGE_SYSTEM_PROMPT,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(JUDGE_OUTPUT_SCHEMA),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env=self._clean_env(),
                input=user_prompt,
            )
            if result.returncode != 0:
                # The Claude Code CLI may output errors to stdout (not
                # stderr), e.g. "API Error ... model identifier is
                # invalid".  Check both streams for a useful message.
                error_msg = (
                    result.stderr.strip()
                    or result.stdout.strip()
                    or f"Exit code {result.returncode}"
                )
                raise LLMJudgeError(f"Claude CLI failed: {error_msg}")

            return self._extract_evaluation_json(result.stdout)
        except subprocess.TimeoutExpired as exc:
            raise LLMJudgeError("Claude CLI timed out after 120s") from exc
        except LLMJudgeError:
            raise
        except Exception as exc:
            raise LLMJudgeError(f"Claude CLI call failed: {exc}") from exc

    @staticmethod
    def _extract_evaluation_json(raw_stdout: str) -> str:
        """Extract the evaluations JSON from CLI ``--output-format json`` output.

        The CLI wraps the model response in an envelope like::

            {"type": "result", "structured_output": {...}, "result": "...", ...}

        Extraction priority:

        1. ``structured_output`` (set when ``--json-schema`` is used) --
           already a dict, so we re-serialise it.
        2. ``result`` text field -- may contain a JSON code block; we
           extract the first ``{...}`` block.
        3. Raw stdout as-is (fallback for plain-text ``--print`` output).
        """
        stdout_stripped = raw_stdout.strip()
        if not stdout_stripped:
            raise LLMJudgeError(
                "Claude CLI returned empty output. "
                "The model may not have produced a response."
            )

        # Try to parse the CLI JSON envelope
        try:
            envelope = json.loads(stdout_stripped)
        except json.JSONDecodeError:
            # Not a JSON envelope -- treat raw text as the response
            return stdout_stripped

        if not isinstance(envelope, dict):
            return stdout_stripped

        # Priority 1: structured_output (from --json-schema)
        structured = envelope.get("structured_output")
        if structured and isinstance(structured, dict):
            return json.dumps(structured)

        # Priority 2: result text field -- extract embedded JSON
        result_text = envelope.get("result", "")
        if result_text:
            # Try to find a JSON code block
            code_block = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```",
                result_text,
                re.DOTALL,
            )
            if code_block:
                return code_block.group(1)

            # Try to find a bare JSON object
            bare_json = re.search(r"\{.*\}", result_text, re.DOTALL)
            if bare_json:
                return bare_json.group(0)

            # Return the result text as-is (will likely fail JSON parsing
            # downstream, which triggers the retry logic)
            return result_text

        raise LLMJudgeError(
            "Claude CLI JSON response missing both 'structured_output' "
            "and 'result' fields."
        )

    def score(
        self,
        output_dir: Path,
        task_description: str,
        custom_criteria: list[dict[str, str]] | None = None,
        reference_solution_path: Path | None = None,
        language: str = "python",
    ) -> LLMScore:
        """Convenience method that reads code from an output directory.

        Uses the language-specific scorer to discover source files,
        concatenates them with filename headers, and calls judge_code.

        Args:
            output_dir: Directory containing the benchmark output files.
            task_description: Description of the task.
            custom_criteria: Optional custom criteria to add.
            reference_solution_path: Optional path to a reference solution file.
            language: Language name for file discovery and code fence formatting.

        Returns:
            LLMScore from judge_code.

        Raises:
            LLMJudgeError: If no source files found or judge fails.
        """
        from .registry import get_scorer
        from claude_benchmark.tasks.schema import Language

        # Use the language-specific scorer to find source files
        try:
            lang_enum = Language(language)
            scorer = get_scorer(lang_enum)
            source_files = sorted(scorer.find_source_files(output_dir))
        except (ValueError, KeyError):
            # Fallback for unknown languages: use Python-style discovery
            self._logger.warning(
                "No scorer registered for language '%s', falling back to *.py",
                language,
            )
            source_files = sorted(
                f
                for f in output_dir.rglob("*.py")
                if "__pycache__" not in str(f)
                and not f.name.startswith("test_")
                and not f.name.endswith("_test.py")
            )

        if not source_files:
            raise LLMJudgeError(
                f"No {language} source files found in output directory"
            )

        # Concatenate with filename headers
        parts: list[str] = []
        for src_file in source_files:
            try:
                content = src_file.read_text(encoding="utf-8")
                relative = src_file.relative_to(output_dir)
                parts.append(f"# --- {relative} ---\n{content}")
            except (OSError, UnicodeDecodeError) as exc:
                self._logger.warning("Could not read %s: %s", src_file, exc)

        if not parts:
            raise LLMJudgeError(
                f"Could not read any {language} source files in output directory"
            )

        code = "\n\n".join(parts)

        # Read reference solution if provided
        reference_solution: str | None = None
        if reference_solution_path is not None:
            try:
                reference_solution = reference_solution_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                self._logger.warning(
                    "Could not read reference solution %s: %s",
                    reference_solution_path,
                    exc,
                )

        return self.judge_code(
            code=code,
            task_description=task_description,
            criteria=custom_criteria,
            reference_solution=reference_solution,
            language=language,
        )
