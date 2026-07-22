"""Provider registry — resolves a spec string to a JudgeProvider instance."""

from __future__ import annotations

from .base import JudgeProvider

_ANTHROPIC_ALIASES = {"haiku", "sonnet", "opus", "opus-4-7"}
_OPENAI_ALIASES = {"gpt-4o", "gpt-4o-2024-11-20", "gpt-4-turbo", "gpt-4.1", "gpt-5"}
_GEMINI_ALIASES = {
    "gemini-2.5-pro",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
}


def get_judge(spec: str, **kwargs) -> JudgeProvider:
    """Resolve a judge spec string to a concrete provider instance.

    Recognized specs:
      - Anthropic: ``haiku``, ``sonnet``, ``opus``, ``opus-4-7``,
        any string matching ``claude-*``, or ``anthropic:<model-id>``.
      - OpenAI: ``gpt-4o``, ``gpt-4-turbo``, ``gpt-4.1``, ``gpt-5``,
        any string starting with ``gpt-``, or ``openai:<model-id>``.
      - Gemini: ``gemini-2.5-pro``, ``gemini-1.5-pro``, ``gemini-1.5-flash``,
        any string starting with ``gemini-``, or ``gemini:<model-id>``.

    Args:
        spec: Provider/model identifier.
        **kwargs: Provider-specific options (e.g. ``use_direct_api`` for
            Anthropic, ``api_key`` for OpenAI/Gemini).

    Raises:
        ValueError: If the spec cannot be matched to a provider.
    """
    if not spec or not isinstance(spec, str):
        raise ValueError(f"Invalid judge spec: {spec!r}")

    s = spec.strip()

    # Explicit provider prefix
    if ":" in s:
        prefix, _, model_id = s.partition(":")
        prefix = prefix.lower()
        if prefix == "anthropic":
            from .anthropic_judge import AnthropicJudge
            return AnthropicJudge(model=model_id, **kwargs)
        if prefix == "openai":
            from .openai_judge import OpenAIJudge
            return OpenAIJudge(model=model_id, **kwargs)
        if prefix == "gemini" or prefix == "google":
            from .gemini_judge import GeminiJudge
            return GeminiJudge(model=model_id, **kwargs)
        raise ValueError(
            f"Unknown judge provider prefix '{prefix}'. "
            "Expected one of: anthropic, openai, gemini."
        )

    lower = s.lower()

    # Anthropic aliases / claude model IDs
    if lower in _ANTHROPIC_ALIASES or lower.startswith("claude-"):
        from .anthropic_judge import AnthropicJudge
        return AnthropicJudge(model=s, **kwargs)

    # OpenAI aliases / gpt model IDs
    if lower in _OPENAI_ALIASES or lower.startswith("gpt-"):
        from .openai_judge import OpenAIJudge
        return OpenAIJudge(model=s, **kwargs)

    # Gemini aliases / gemini model IDs
    if lower in _GEMINI_ALIASES or lower.startswith("gemini-"):
        from .gemini_judge import GeminiJudge
        return GeminiJudge(model=s, **kwargs)

    raise ValueError(
        f"Unknown judge spec '{spec}'. "
        "Use a Claude alias (haiku/sonnet/opus), a Claude model ID, "
        "an OpenAI model (gpt-4o, gpt-4-turbo), a Gemini model "
        "(gemini-2.5-pro, gemini-1.5-pro), or a 'provider:model-id' form "
        "(e.g. 'openai:gpt-4o-2024-11-20')."
    )
