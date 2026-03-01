"""LLM-generated narrative summary for benchmark reports.

Calls Claude Haiku via the ``npx`` CLI to produce a 3-5 paragraph narrative
interpreting aggregated benchmark data.  Gracefully degrades on any failure
so the report always generates.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any

_NPX_CLAUDE_PACKAGE = "@anthropic-ai/claude-code@latest"
_DEFAULT_MODEL = "haiku"
_TIMEOUT_SECONDS = 90

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a benchmark analyst summarizing code-generation benchmark results.
Write 3-5 plain paragraphs (under 400 words total) interpreting the data.
Focus on actionable insights about variant comparison: which profiles or
models performed best and why, where trade-offs exist, and what a reader
should take away.  Do NOT repeat raw numbers verbatim — synthesize them.
Do NOT use markdown formatting, headers, or bullet points — just paragraphs.
Do NOT include any preamble like "Here is my analysis" — start directly
with the first insight."""


def generate_llm_summary(
    *,
    quality_scores: dict[str, float],
    best_combo_model: str,
    best_combo_profile: str,
    best_combo_score: float,
    best_profile_overall: str,
    best_profile_score: float,
    tw_model: str,
    tw_profile: str,
    tw_score: float,
    category_analysis: list[dict[str, Any]],
    model_preferences: list[dict[str, Any]],
    insights: list[str],
    regressions_list: list[Any],
    token_counts: dict[str, int],
    profiles: list[str],
    tasks: list[str],
    models: list[str],
) -> str | None:
    """Generate an LLM narrative summary of benchmark results.

    Returns the summary text (plain paragraphs) on success, or ``None`` on
    any failure.  All exceptions are caught and logged so report generation
    is never blocked.
    """
    try:
        user_prompt = _build_prompt(
            quality_scores=quality_scores,
            best_combo_model=best_combo_model,
            best_combo_profile=best_combo_profile,
            best_combo_score=best_combo_score,
            best_profile_overall=best_profile_overall,
            best_profile_score=best_profile_score,
            tw_model=tw_model,
            tw_profile=tw_profile,
            tw_score=tw_score,
            category_analysis=category_analysis,
            model_preferences=model_preferences,
            insights=insights,
            regressions_list=regressions_list,
            token_counts=token_counts,
            profiles=profiles,
            tasks=tasks,
            models=models,
        )
        result = _call_claude(user_prompt, _SYSTEM_PROMPT, _DEFAULT_MODEL, _TIMEOUT_SECONDS)
        if not result or not result.strip():
            logger.warning("LLM summary returned empty response")
            return None
        return result.strip()
    except Exception:
        logger.warning("LLM summary generation failed", exc_info=True)
        return None


def _build_prompt(
    *,
    quality_scores: dict[str, float],
    best_combo_model: str,
    best_combo_profile: str,
    best_combo_score: float,
    best_profile_overall: str,
    best_profile_score: float,
    tw_model: str,
    tw_profile: str,
    tw_score: float,
    category_analysis: list[dict[str, Any]],
    model_preferences: list[dict[str, Any]],
    insights: list[str],
    regressions_list: list[Any],
    token_counts: dict[str, int],
    profiles: list[str],
    tasks: list[str],
    models: list[str],
) -> str:
    """Serialize aggregated benchmark data into a compact prompt."""
    regressions_data = []
    for r in regressions_list:
        regressions_data.append({
            "profile": getattr(r, "profile", str(r)),
            "task": getattr(r, "task", ""),
            "dimension": getattr(r, "dimension", ""),
            "delta_pct": round(getattr(r, "delta_pct", 0) * 100, 1),
            "p_value": round(getattr(r, "p_value", 0), 3),
        })

    # Serialize category_analysis — may be dicts or objects with attributes
    cat_data = []
    for cat in category_analysis:
        if isinstance(cat, dict):
            cat_data.append(cat)
        else:
            cat_data.append({
                "category": getattr(cat, "category", ""),
                "task_count": getattr(cat, "task_count", 0),
                "winner": getattr(cat, "winner", ""),
                "winner_score": round(getattr(cat, "winner_score", 0), 1),
                "margin": round(getattr(cat, "margin", 0), 1),
                "is_exception": getattr(cat, "is_exception", False),
            })

    pref_data = []
    for pref in model_preferences:
        if isinstance(pref, dict):
            pref_data.append(pref)
        else:
            pref_data.append({
                "model": getattr(pref, "model", ""),
                "preferred_profile": getattr(pref, "preferred_profile", ""),
                "score": round(getattr(pref, "score", 0), 1),
                "is_exception": getattr(pref, "is_exception", False),
            })

    data = {
        "models": models,
        "profiles": profiles,
        "tasks": tasks,
        "quality_scores_by_profile": quality_scores,
        "token_counts_by_profile": token_counts,
        "best_combo": {
            "model": best_combo_model,
            "profile": best_combo_profile,
            "score": round(best_combo_score, 1),
        },
        "best_profile_overall": {
            "profile": best_profile_overall,
            "score": round(best_profile_score, 1),
        },
        "token_efficiency_winner": {
            "model": tw_model,
            "profile": tw_profile,
            "score": round(tw_score, 1),
        },
        "category_analysis": cat_data,
        "model_preferences": pref_data,
        "rule_based_insights": insights,
        "regressions": regressions_data,
    }

    return (
        "Analyze these code-generation benchmark results and write a narrative summary.\n\n"
        + json.dumps(data, indent=2, default=str)
    )


def _call_claude(
    user_prompt: str,
    system_prompt: str,
    model: str,
    timeout: int,
) -> str:
    """Call Claude via the Claude Code CLI and return plain text output."""
    cmd = [
        "npx",
        _NPX_CLAUDE_PACKAGE,
        "--print",
        "--dangerously-skip-permissions",
        "--model",
        model,
        "--system-prompt",
        system_prompt,
    ]

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        input=user_prompt,
    )

    if result.returncode != 0:
        error_msg = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"Exit code {result.returncode}"
        )
        raise RuntimeError(f"Claude CLI failed: {error_msg}")

    return result.stdout
