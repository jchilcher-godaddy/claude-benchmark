"""Token counting with Anthropic API and character-based fallback."""

from typing import Optional

# Approximate ratio: ~4 characters per token for English text.
# This is a widely-cited heuristic. Less accurate for code-heavy content.
CHARS_PER_TOKEN_ESTIMATE = 4.0


def count_tokens_approx(text: str) -> int:
    """Approximate token count from character length.

    Uses ~4 chars/token ratio. Rough but works offline.

    Args:
        text: The text to estimate token count for.

    Returns:
        Estimated token count. Returns 0 for empty string.
    """
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN_ESTIMATE))


def count_tokens_api(
    text: str,
    model: str = "claude-sonnet-4-20250514",
    client: Optional[object] = None,
) -> int:
    """Count tokens using Anthropic's official API (free, accurate).

    Args:
        text: The text to count tokens for.
        model: The model to use for tokenization.
        client: Optional Anthropic client instance.

    Returns:
        Exact token count from the API.

    Raises:
        ImportError: If the anthropic SDK is not installed.
        Exception: If the API call fails.
    """
    try:
        import anthropic
    except ImportError as e:
        raise ImportError(
            "The 'anthropic' package is required for exact token counting. "
            "Install it with: pip install anthropic"
        ) from e

    if client is None:
        client = anthropic.Anthropic()

    response = client.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": text}],
    )
    return response.input_tokens


def count_tokens(
    text: str,
    model: str = "claude-sonnet-4-20250514",
    use_api: bool = True,
) -> tuple[int, bool]:
    """Count tokens with API preference and character-based fallback.

    Tries the Anthropic API first for exact counts, falling back to
    character-based approximation on any error.

    Args:
        text: The text to count tokens for.
        model: The model to use for API tokenization.
        use_api: Whether to attempt API counting first.

    Returns:
        Tuple of (token_count, is_exact). is_exact is True only when
        the count came from the API.
    """
    # Special case: empty or whitespace-only text
    if not text or not text.strip():
        return (0, True)

    if use_api:
        try:
            return (count_tokens_api(text, model=model), True)
        except Exception:
            pass  # Fall through to approximation

    return (count_tokens_approx(text), False)
