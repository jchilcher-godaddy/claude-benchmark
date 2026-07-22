"""Provider-abstracted LLM judges (Anthropic, OpenAI, Gemini).

The default Haiku path remains unchanged — see
``claude_benchmark.scoring.llm_judge.LLMJudgeScorer``. This module exposes
a ``JudgeProvider`` ABC and a ``get_judge`` registry function that route
a spec string (e.g. ``haiku``, ``gpt-4o``, ``gemini-2.5-pro``) to a
provider-specific implementation, enabling cross-family judging for
in-family-bias validation.
"""

from __future__ import annotations

from .base import JudgeError, JudgeProvider
from .registry import get_judge

__all__ = [
    "JudgeError",
    "JudgeProvider",
    "get_judge",
]
