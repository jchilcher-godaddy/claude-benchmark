"""Reproducibility scaffolding for claude-benchmark experiments.

Provides hashing, environment capture, and seed-derivation helpers so that
every experiment run can be re-identified, re-checked, and (within the
limits documented in ``docs/reproducibility.md``) replicated months or
years later.

Public API:
    - ``hash_task_set``, ``hash_judge_prompt``, ``hash_string`` (hashing.py)
    - ``capture_environment`` (environment.py)
    - ``generate_run_seed``, ``set_global_seeds`` (seeds.py)
"""

from __future__ import annotations

from claude_benchmark.reproducibility.environment import capture_environment
from claude_benchmark.reproducibility.hashing import (
    hash_judge_prompt,
    hash_string,
    hash_task_set,
)
from claude_benchmark.reproducibility.seeds import generate_run_seed, set_global_seeds

__all__ = [
    "capture_environment",
    "generate_run_seed",
    "hash_judge_prompt",
    "hash_string",
    "hash_task_set",
    "set_global_seeds",
]
