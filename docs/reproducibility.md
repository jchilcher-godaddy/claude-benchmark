# Reproducibility

This document describes how `claude-benchmark` makes experiments
reproducible, what *cannot* be made bit-exact, and the procedure for
verifying or replicating a published finding.

## What we record

Every experiment writes a `reproducibility.json` alongside `manifest.json`
in its results directory. The file contains:

- **`task_set`** — A SHA-256 over the entire task corpus, plus a
  per-task SHA-256 map (`task_id -> sha256`). The corpus hash flips
  if any task file (prompt, starter, reference, tests) changes.
- **`judge_prompt`** — Hashes of `JUDGE_SYSTEM_PROMPT`, `BUILTIN_CRITERIA`,
  `JUDGE_OUTPUT_SCHEMA`, and the entire `scoring/prompts.py` module.
  Any change to scoring rubrics or judge wording is detectable.
- **`environment`** — Python version, platform string, full
  `pip freeze`, Git commit SHA, `git_dirty` flag, branch name, and the
  installed `claude-benchmark` version.
- **`base_seed` / `seed_recipe`** — How per-run seeds are derived. Each
  per-run JSON also records its own `seed` field.
- **`model_seed_supported: false`** — A static reminder that the
  Anthropic API does not currently accept a sampling seed.

## Model snapshots: the limitation

`claude-benchmark` exposes short aliases (`haiku`, `sonnet`, `opus`).
At runtime these resolve to a versioned Bedrock or Anthropic model ID
(see `src/claude_benchmark/execution/client.py`). The resolved ID is
captured per-run as `model_snapshot`.

**However:** Anthropic occasionally retires or updates a versioned model
behind the same ID. A snapshot pin guarantees reproducibility only as
long as Anthropic keeps that snapshot served. Plan for this by:

1. Citing both the alias and the resolved snapshot ID in any paper.
2. Archiving raw run outputs (a Zenodo upload is the recommended
   destination — see `data-availability.md`).
3. Treating any re-execution months later as a *replication* rather
   than a *reproduction*; report effect-size comparisons, not exact
   matches.

## Verifying a task-set hash

Given a paper that reports `task_set_hash: <hex>`, a reader can verify
their checkout produces the same digest:

```python
from pathlib import Path
from claude_benchmark.reproducibility.hashing import hash_task_set

print(hash_task_set(Path("tasks"))["task_set_hash"])
```

If the digest differs, inspect `task_hashes` in the paper's
`reproducibility.json` against the local result of `hash_task_set` to
find which specific tasks differ.

## Re-running an experiment from a manifest

Each experiment results directory contains:

- `manifest.json` — The high-level shape of the experiment (models,
  profiles, tasks, variants, reps).
- `reproducibility.json` — Provenance hashes and environment.
- The original TOML config (find it via the `experiment_config_path`
  field of `reproducibility.json`).

To replicate:

1. Check out the Git commit recorded in `reproducibility.json.environment.git_commit`.
2. Recreate the Python environment from `pip_freeze`. A faithful
   recreation requires the same Python minor version
   (`environment.python_version`).
3. Run `claude-benchmark experiment <config_path> --results-dir <new>`.
4. Compare the new `reproducibility.json` against the old. The
   `task_set` and `judge_prompt` hashes must match. If they don't,
   diagnose before running.

## Known sources of non-determinism

Even with identical inputs, results will not be bit-exact across runs.
The dominant sources, ordered by typical impact:

1. **Sampling.** Most experiments run at `temperature > 0`. The model
   draws stochastically; identical seeds do not produce identical
   completions because the API does not honor a seed. This is the
   biggest source of variance and is the reason `--reps` exists.
2. **Provider-side updates.** Anthropic may patch a model under the
   same versioned ID (rare but documented). Replication runs months
   apart should treat this as expected drift.
3. **Timeouts and retries.** Network-induced retries can change which
   completion is observed for a given run. Aggregate metrics are
   robust to this; per-run comparison is not.
4. **Judge non-determinism.** The Haiku judge also samples. We score
   each run once; a re-score will produce slightly different LLM judge
   numbers even on identical code.
5. **Static-analysis tooling drift.** `ruff`, `radon`, and `pytest`
   produce stable results within a major version, but version pinning
   (via `pip_freeze`) is necessary for full determinism.

## Pointers

- `reproducibility.json` (per-experiment provenance)
- `CITATION.cff` (repo-level citation metadata)
- `.zenodo.json` (Zenodo DOI metadata)
- `data-availability.md` (where to find / how to release raw runs)
- `scoring-methodology.md` (what the scores mean)
- `judge-selection.md` (why Haiku is the judge)
