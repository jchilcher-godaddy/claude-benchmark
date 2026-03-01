"""LLM judge prompt templates and criteria definitions for claude-benchmark.

Provides the system prompt, built-in evaluation criteria, and formatting
functions used by the LLMJudgeScorer to construct requests to the Anthropic API.
"""

from __future__ import annotations

# Default judge model: Claude Haiku 4.5 to avoid self-bias when benchmarking
# Sonnet/Opus. Fast and cheap for rubric-based evaluation.
# See RESEARCH.md Pitfall 2.
#
# IMPORTANT: Use the short alias, not a versioned model ID.  The Claude Code
# CLI resolves aliases internally; bare versioned IDs like
# "claude-haiku-4-5-20251001" are rejected with "model identifier is invalid".
DEFAULT_JUDGE_MODEL = "haiku"

# Maximum characters for code and reference solution to avoid exceeding context
# limits on the judge model.
_MAX_CODE_CHARS = 8000

# Four locked built-in criteria per CONTEXT.md decisions.
BUILTIN_CRITERIA: list[dict[str, str]] = [
    {
        "name": "code_readability",
        "description": (
            "Code clarity, naming conventions, commenting, and overall "
            "readability. Well-structured code that another developer could "
            "easily understand and maintain."
        ),
    },
    {
        "name": "architecture_quality",
        "description": (
            "Code organization, separation of concerns, appropriate use of "
            "abstractions, and design patterns. Code that follows SOLID "
            "principles and is extensible."
        ),
    },
    {
        "name": "instruction_adherence",
        "description": (
            "How closely the output follows the task requirements and any "
            "specific instructions. All requested features implemented, "
            "constraints respected, edge cases handled as specified."
        ),
    },
    {
        "name": "correctness_reasoning",
        "description": (
            "Logical correctness of the implementation, appropriate error "
            "handling, and robustness. Code that handles edge cases, validates "
            "inputs, and produces correct results."
        ),
    },
]

# JSON schema for the expected LLM judge output. Used both in the prompt
# and for output_config structured output.
JUDGE_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "evaluations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "score": {"type": "integer"},
                    "reasoning": {"type": "string"},
                },
                "required": ["criterion", "score", "reasoning"],
            },
        },
    },
    "required": ["evaluations"],
}

JUDGE_SYSTEM_PROMPT = """\
You are an expert code reviewer scoring benchmark outputs.

Evaluate the provided code against each criterion using the following 1-5 scale:

  1 = Poor: Fundamentally broken or missing
  2 = Below average: Major issues that affect functionality or quality
  3 = Adequate: Meets basic requirements with some issues
  4 = Good: Well-implemented with minor issues
  5 = Excellent: Exemplary implementation, no meaningful improvements needed

Instructions:
- Think step-by-step about the code quality before assigning scores.
- For each criterion, provide a score (integer 1-5) and a reasoning (1-2 sentences explaining the score).
- Return your evaluation as a JSON object matching the required output format exactly.\
"""


def format_rubric(criteria: list[dict[str, str]]) -> str:
    """Format a list of criteria dicts into a numbered rubric string.

    Each dict must have "name" and "description" keys.

    Example output::

        1. code_readability: Code clarity, naming conventions...
        2. architecture_quality: Code organization...
    """
    lines: list[str] = []
    for i, criterion in enumerate(criteria, start=1):
        lines.append(f"{i}. {criterion['name']}: {criterion['description']}")
    return "\n".join(lines)


def _truncate(text: str, max_chars: int = _MAX_CODE_CHARS) -> str:
    """Truncate text to max_chars, appending a marker if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[truncated]"


def format_judge_user_prompt(
    task_description: str,
    code: str,
    criteria: list[dict[str, str]],
    reference_solution: str | None = None,
) -> str:
    """Build the full user message for the LLM judge.

    Sections:
      - Task description
      - Code to evaluate (truncated to 8000 chars)
      - Optional reference solution (truncated to 8000 chars)
      - Evaluation criteria (numbered rubric)
      - Required output format (JSON schema example)
    """
    code_text = _truncate(code)
    rubric_text = format_rubric(criteria)

    parts: list[str] = [
        f"## Task\n{task_description}",
        f"## Code to Evaluate\n```python\n{code_text}\n```",
    ]

    if reference_solution is not None:
        ref_text = _truncate(reference_solution)
        parts.append(f"## Reference Solution\n```python\n{ref_text}\n```")

    parts.append(f"## Evaluation Criteria\n{rubric_text}")

    parts.append(
        '## Required Output Format\n'
        'Return a JSON object with this exact structure:\n'
        '```json\n'
        '{\n'
        '    "evaluations": [\n'
        '        {"criterion": "<name>", "score": "<1-5>", "reasoning": "<explanation>"}\n'
        '    ]\n'
        '}\n'
        '```'
    )

    return "\n\n".join(parts)
