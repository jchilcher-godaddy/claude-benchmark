"""Abstract base class for LLM judge providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class JudgeError(Exception):
    """Raised when a judge provider call fails."""


class JudgeProvider(ABC):
    """Provider-agnostic LLM judge contract.

    Implementations call out to a specific model API (Anthropic, OpenAI,
    Gemini, ...) and return a parsed list of evaluation dicts matching
    the JUDGE_OUTPUT_SCHEMA.

    Each evaluation dict has the shape::

        {"criterion": str, "score": int (1-5), "reasoning": str}
    """

    #: Provider identifier for run metadata (e.g. "anthropic", "openai").
    provider: str = "unknown"

    #: Concrete model identifier sent to the provider API.
    model_id: str = "unknown"

    @abstractmethod
    def score(self, prompt: str, system: str, schema: dict) -> list[dict]:
        """Send a judging request to the provider and return evaluations.

        Args:
            prompt: User prompt containing task, code, criteria, output format.
            system: System prompt establishing the judge persona and scale.
            schema: JSON schema describing the expected output structure.

        Returns:
            List of evaluation dicts (the value of the ``evaluations`` key).

        Raises:
            JudgeError: If the API call fails or the response cannot be parsed.
        """
        raise NotImplementedError
