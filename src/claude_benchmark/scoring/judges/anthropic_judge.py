"""Anthropic judge provider — wraps the existing Haiku call path.

Delegates to ``LLMJudgeScorer`` so the proxy > direct-API > CLI fallback
chain and the structured-output extraction logic remain a single
implementation.
"""

from __future__ import annotations

import json

from .base import JudgeError, JudgeProvider


class AnthropicJudge(JudgeProvider):
    """Judge backed by Claude (Haiku/Sonnet/Opus) via the existing call path.

    Accepts a model alias (``haiku``, ``sonnet``, ``opus``) or an explicit
    Anthropic model ID. The actual transport (proxy, direct API, or
    Claude Code CLI) is selected by ``LLMJudgeScorer`` based on the
    runtime environment.
    """

    provider = "anthropic"

    def __init__(self, model: str = "haiku", use_direct_api: bool = False) -> None:
        self.model_id = model
        self.use_direct_api = use_direct_api

    def score(self, prompt: str, system: str, schema: dict) -> list[dict]:
        # Lazy import to avoid a circular dependency: llm_judge imports
        # the registry which may import this module.
        from claude_benchmark.scoring.errors import LLMJudgeError
        from claude_benchmark.scoring.llm_judge import LLMJudgeScorer

        scorer = LLMJudgeScorer(model=self.model_id, use_direct_api=self.use_direct_api)
        try:
            call_fn = scorer._select_call_fn()
            try:
                response_text = call_fn(prompt)
            except LLMJudgeError:
                # API path unavailable — fall back to CLI (preserves the
                # behavior previously inlined in judge_code).
                response_text = scorer._call_api(prompt)
        except LLMJudgeError as exc:
            raise JudgeError(str(exc)) from exc

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise JudgeError(f"Anthropic judge returned non-JSON: {exc}") from exc

        evaluations = data.get("evaluations")
        if not isinstance(evaluations, list):
            raise JudgeError("Anthropic judge response missing 'evaluations' list")
        return evaluations
