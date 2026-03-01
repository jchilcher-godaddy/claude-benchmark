"""Composite scorer for claude-benchmark.

Combines static analysis scores and LLM-as-judge scores into a unified
composite score. Supports static-only fallback when LLM scoring is
unavailable.
"""

from __future__ import annotations

from .models import CompositeScore, LLMScore, StaticScore


class CompositeScorer:
    """Combines static and LLM scores into a single composite.

    Default weights: 50% static + 50% LLM per locked decision.
    When LLM is unavailable, degrades gracefully to static-only mode.

    Args:
        static_weight: Weight for the static score component (default 0.5).
        llm_weight: Weight for the LLM score component (default 0.5).

    Raises:
        ValueError: If weights do not sum to 1.0 (within tolerance).
    """

    def __init__(
        self,
        static_weight: float = 0.5,
        llm_weight: float = 0.5,
    ) -> None:
        if abs(static_weight + llm_weight - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0 (got {static_weight + llm_weight:.4f}): "
                f"static_weight={static_weight}, llm_weight={llm_weight}"
            )
        self.static_weight = static_weight
        self.llm_weight = llm_weight

    def compute(
        self,
        static: StaticScore,
        llm: LLMScore | None = None,
    ) -> CompositeScore:
        """Compute the composite score from static and optional LLM scores.

        If llm is provided, composite = static.weighted_total * static_weight
        + llm.normalized * llm_weight.

        If llm is None (static-only mode), composite = static.weighted_total.

        Args:
            static: The static analysis score.
            llm: Optional LLM-as-judge score. If None, uses static-only mode.

        Returns:
            CompositeScore with the combined result.
        """
        if llm is not None:
            composite = (
                static.weighted_total * self.static_weight
                + llm.normalized * self.llm_weight
            )
            return CompositeScore(
                static_score=static,
                llm_score=llm,
                composite=round(composite, 2),
                static_only=False,
            )

        # Static-only fallback
        return CompositeScore(
            static_score=static,
            llm_score=None,
            composite=round(static.weighted_total, 2),
            static_only=True,
        )
