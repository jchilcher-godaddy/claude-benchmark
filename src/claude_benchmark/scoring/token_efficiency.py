"""Token efficiency calculator for claude-benchmark.

Computes quality-per-token metrics to measure how efficiently a model
uses tokens to produce quality output. Higher points-per-1K-tokens
means better efficiency.
"""

from __future__ import annotations

from .models import TokenEfficiency


def compute_token_efficiency(
    composite_score: float,
    claudemd_context_tokens: int,
    task_io_tokens: int,
) -> TokenEfficiency:
    """Compute token efficiency from a composite score and token counts.

    Calculates points-per-1K-tokens as: (composite_score / total_tokens) * 1000.
    Returns 0.0 for zero total tokens to avoid division by zero.

    Args:
        composite_score: The composite quality score (0-100).
        claudemd_context_tokens: Tokens consumed by CLAUDE.md context.
        task_io_tokens: Tokens consumed by task input/output.

    Returns:
        TokenEfficiency with all fields populated.
    """
    total_tokens = claudemd_context_tokens + task_io_tokens

    if total_tokens == 0:
        return TokenEfficiency(
            composite_score=composite_score,
            total_tokens=0,
            claudemd_tokens=claudemd_context_tokens,
            task_io_tokens=task_io_tokens,
            points_per_1k_tokens=0.0,
        )

    ratio = (composite_score / total_tokens) * 1000
    return TokenEfficiency(
        composite_score=composite_score,
        total_tokens=total_tokens,
        claudemd_tokens=claudemd_context_tokens,
        task_io_tokens=task_io_tokens,
        points_per_1k_tokens=round(ratio, 2),
    )
