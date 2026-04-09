"""Context padding generator for context window pollution experiments.

Generates blocks of irrelevant text that can be prepended to task prompts
via ``prompt_prefix`` to test whether irrelevant context degrades output quality.
"""

from __future__ import annotations

import random
import textwrap

# Approximate tokens per character (conservative; 1 token ~ 4 chars for English)
_CHARS_PER_TOKEN = 4

_LOREM_PARAGRAPHS = [
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat.",
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum "
    "dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non "
    "proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
    "Curabitur pretium tincidunt lacus. Nulla gravida orci a odio. Nullam "
    "varius, turpis et commodo pharetra, est eros bibendum elit, nec luctus "
    "magna felis sollicitudin mauris.",
    "Praesent dapibus, neque id cursus faucibus, tortor neque egestas augue, "
    "eu vulputate magna eros eu erat. Aliquam erat volutpat. Nam dui mi, "
    "tincidunt quis, accumsan porttitor, facilisis luctus, metus.",
]

_PROSE_PARAGRAPHS = [
    "The history of computing stretches back to the earliest mechanical "
    "calculators. Charles Babbage conceived his Analytical Engine in the 1830s, "
    "envisioning a general-purpose computing machine powered by steam.",
    "In 1936, Alan Turing published his seminal paper describing what would "
    "become known as the Turing machine. This theoretical construct laid the "
    "groundwork for the field of computability theory.",
    "The first electronic general-purpose computer, ENIAC, was completed in "
    "1945. It weighed 30 tons and occupied 1,800 square feet of floor space, "
    "yet had less computing power than a modern pocket calculator.",
    "The invention of the transistor at Bell Labs in 1947 revolutionized "
    "electronics. Transistors replaced vacuum tubes, leading to smaller, "
    "faster, and more reliable computing machines.",
    "Grace Hopper developed the first compiler in 1952, enabling programmers "
    "to write code in human-readable languages rather than machine code. "
    "This innovation dramatically accelerated software development.",
    "The internet began as ARPANET in 1969, connecting four university "
    "research centers. It would take another two decades before Tim "
    "Berners-Lee invented the World Wide Web in 1989.",
]

_CODE_COMMENTS = [
    "# This module handles configuration for the legacy authentication system.\n"
    "# It was originally written for the v1 API and has been maintained for\n"
    "# backwards compatibility. The v2 API uses OAuth2 instead.\n",
    "# Database connection pooling settings. These values were tuned for\n"
    "# the production workload in Q3 2024. The max_connections value of 50\n"
    "# was determined through load testing with 10,000 concurrent users.\n",
    "# Retry logic for external API calls. Uses exponential backoff with\n"
    "# jitter to avoid thundering herd problems. The base delay is 100ms\n"
    "# and the maximum delay is 30 seconds.\n",
    "# Feature flag configuration. These flags control gradual rollout of\n"
    "# new functionality. Each flag has a rollout percentage that determines\n"
    "# what fraction of users see the new behavior.\n",
    "# Caching layer configuration. We use a two-tier cache: L1 is an\n"
    "# in-process LRU cache (100MB limit), L2 is Redis. TTL values are\n"
    "# specified in seconds.\n",
    "# Logging configuration. In production, we emit structured JSON logs\n"
    "# that are ingested by our ELK stack. Debug logging is disabled by\n"
    "# default but can be enabled per-module via environment variables.\n",
]


def generate_padding(token_count: int, style: str = "random_prose") -> str:
    """Generate a block of irrelevant text approximately ``token_count`` tokens long.

    The generated text is wrapped in a clear delimiter so it can be identified
    in the prompt, and a note explains it should be ignored.

    Args:
        token_count: Approximate number of tokens to generate.
        style: One of ``"random_prose"``, ``"code_comments"``, ``"lorem_ipsum"``,
            or ``"mixed"``.

    Returns:
        A string of approximately ``token_count`` tokens of irrelevant content,
        bookended with context markers.

    Raises:
        ValueError: If ``style`` is not recognized.
    """
    valid_styles = ("random_prose", "code_comments", "lorem_ipsum", "mixed")
    if style not in valid_styles:
        raise ValueError(f"Unknown style '{style}', must be one of {valid_styles}")

    target_chars = token_count * _CHARS_PER_TOKEN

    if style == "mixed":
        # Interleave all styles
        sources = _PROSE_PARAGRAPHS + _CODE_COMMENTS + _LOREM_PARAGRAPHS
    elif style == "random_prose":
        sources = _PROSE_PARAGRAPHS
    elif style == "code_comments":
        sources = _CODE_COMMENTS
    elif style == "lorem_ipsum":
        sources = _LOREM_PARAGRAPHS
    else:
        sources = _PROSE_PARAGRAPHS

    rng = random.Random(42)  # deterministic for reproducibility
    parts: list[str] = []
    total_chars = 0
    while total_chars < target_chars:
        block = rng.choice(sources)
        parts.append(block)
        total_chars += len(block) + 2  # +2 for newlines

    content = "\n\n".join(parts)

    # Trim to approximate target
    if len(content) > target_chars:
        content = content[:target_chars].rsplit(" ", 1)[0]

    return (
        "--- BEGIN BACKGROUND CONTEXT (for reference only) ---\n"
        f"{content}\n"
        "--- END BACKGROUND CONTEXT ---\n\n"
    )
