# Data Availability

This document describes where `claude-benchmark` data lives, what is
released, what is held back, and under what license.

## What's in the repo

The Git repository contains everything needed to *re-run* an experiment:

- The benchmark harness (`src/claude_benchmark/`).
- The task corpus (`tasks/builtin/`, `tasks/custom/`).
- The CLAUDE.md profiles under test (`profiles/`).
- Experiment definitions (`experiments/*.toml`).
- Aggregated, anonymized findings narrative (`docs/experiments.md`,
  `CLAUDE.md`).

License: Apache-2.0 (see `LICENSE`).

## What's *not* in the repo

The repo does **not** contain raw per-run outputs. A typical experiment
produces 10,000–35,000 per-run JSON files, each containing the full
model completion, captured workspace files, scoring breakdown, and
provenance. Total per experiment: hundreds of MB to a few GB. This is
too large for Git and would obscure code changes in diffs.

Raw outputs live under `results/experiment-*/` on the machine that ran
the experiment.

## Releasing raw run data

For findings that are cited in papers or external posts, raw runs
should be archived on **Zenodo** (or an equivalent open archive).
Recommended workflow:

1. Use the export command to produce a clean dataset (CSV + JSON):

   ```sh
   claude-benchmark export --results-dir results/experiment-<name>-<timestamp>
   ```

   See `src/claude_benchmark/cli/commands/export.py` for filtering
   options (`--task`, `--profile`, `--model`).

2. Zip the entire results directory, including:
   - `manifest.json`
   - `reproducibility.json`
   - All per-run `*.json` files
   - The `report.html` if present

3. Upload to Zenodo. The repo's `.zenodo.json` provides the metadata
   template; reuse the `creators`, `keywords`, and license fields.
4. Cite the Zenodo DOI in any paper or post that reports findings
   from that experiment.

## What we hold back

- **API credentials.** No `.env`, AWS profile, or API key has ever
  been committed. The `.gitignore` excludes the standard locations.
- **Personally identifying information.** None expected — tasks are
  synthetic and the model outputs concern code, not user data.
- **Provider-side traces.** Server-side logs (e.g. AWS CloudWatch,
  Anthropic console) are out of scope.

If you find anything in a release that looks like it shouldn't be
public, open an issue and we will redact and re-upload.

## Verifying a release

Every released archive should contain a `reproducibility.json` whose
`task_set.task_set_hash` matches the hash printed by:

```python
from claude_benchmark.reproducibility.hashing import hash_task_set
from pathlib import Path
print(hash_task_set(Path("tasks"))["task_set_hash"])
```

…run from the Git commit recorded in
`reproducibility.json.environment.git_commit`. If the hashes match, the
release was produced from that exact corpus.
