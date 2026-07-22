"""Pre-flight validation for cross-family judge specs.

Fails fast (before starting an experiment) if a non-default judge spec
is requested but the required environment variable is missing.
"""

from __future__ import annotations

import os


def validate_judge_spec(spec: str | None) -> str | None:
    """Return an error message if the judge spec is unusable, else None.

    Default ``haiku`` and other Anthropic specs always validate (they
    use the same credentials as the benchmark workers).
    """
    if not spec:
        return None

    lower = spec.strip().lower()

    # Anthropic specs reuse worker credentials
    if (
        lower in {"haiku", "sonnet", "opus", "opus-4-7"}
        or lower.startswith("claude-")
        or lower.startswith("anthropic:")
    ):
        return None

    if lower.startswith("gpt-") or lower.startswith("openai:"):
        if not os.environ.get("OPENAI_API_KEY"):
            return (
                f"Judge spec '{spec}' requires OPENAI_API_KEY env var "
                "(not set). Export it before running."
            )
        return None

    if lower.startswith("gemini-") or lower.startswith("gemini:") or lower.startswith("google:"):
        if not os.environ.get("GOOGLE_API_KEY"):
            return (
                f"Judge spec '{spec}' requires GOOGLE_API_KEY env var "
                "(not set). Export it before running."
            )
        try:
            import google.generativeai  # noqa: F401
        except ImportError:
            return (
                f"Judge spec '{spec}' requires the google-generativeai "
                "package. Install with: pip install 'claude-benchmark[gemini]'"
            )
        return None

    return (
        f"Unknown judge spec '{spec}'. Use a Claude alias (haiku/sonnet/opus), "
        "an OpenAI model (gpt-4o), a Gemini model (gemini-2.5-pro), or a "
        "'provider:model-id' form."
    )
