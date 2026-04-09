# Experiment System

Experiments are structured comparisons of multiple prompting strategies (variants) across tasks, models, and replications with statistical analysis. Unlike single benchmark runs, experiments isolate the effect of a single variable and test it with enough power to detect real differences.

## Quick Start

```bash
# Run an experiment
claude-benchmark experiment experiments/cot.toml -c 5

# Dry-run to see execution plan
claude-benchmark experiment --dry-run experiments/cot.toml

# Compare results across experiments
claude-benchmark compare --cross-variant -x run-003 run-005 -o comparison.html
```

## TOML Format

```toml
name = "my-experiment"
description = "Hypothesis: X improves Y because Z"

[defaults]
tasks = ["code-gen-01", "bug-fix-01", "refactor-01"]
models = ["haiku", "sonnet", "opus"]
profiles = ["empty"]
reps = 30

[[variants]]
label = "control"
# No modifications — bare baseline

[[variants]]
label = "treatment"
prompt_prefix = "Think step by step. "
```

### Variant Fields

| Field | Type | Description |
|-------|------|-------------|
| `label` | string (required) | Unique identifier for this variant |
| `prompt_prefix` | string | Text prepended to the task prompt |
| `system_prompt_extra` | string | Text appended to the system prompt |
| `temperature` | float | Override default temperature |
| `padding_tokens` | integer | Inject random padding tokens (context-pollution testing) |
| `models` | array | Restrict this variant to specific models |

## Design Principles

### 1. Use 30 reps minimum
Statistical power requires at least 30 replications per cell. 10 reps is acceptable for smoke testing only.

### 2. Cover task diversity
Include tasks across all types (bug-fix, code-gen, refactor, instruction) and difficulties (easy, medium, hard). 12 tasks is the standard; 14-16 for comprehensive coverage.

### 3. Test across models
Run all three models (haiku, sonnet, opus) unless investigating model-specific effects.

### 4. Use the "empty" profile
Set `profiles = ["empty"]` to isolate prompt variations without CLAUDE.md confounds.

### 5. Avoid duplicating controls — use `compare`
Many experiments share the same bare/empty baseline. Instead of adding a control arm to every experiment, use `compare --cross-variant` to pull control data from completed experiments.

**Existing bare controls you can reference:**

| Experiment | Control variant | Tasks | Catalog ID |
|---|---|---|---|
| capstone-best-practices | `bare-default` | 12 | run-003 |
| persona-sweep | `no-persona` | 3 | run-009 |
| context-pollution | `clean` | 3 | run-006 |
| emotional-stakes | `neutral` | 15 | TBD |
| anchoring | `no-anchor` | 16 | TBD |

Example — compare GSD variants against capstone's bare baseline:
```bash
claude-benchmark compare --cross-variant -x run-018 run-003 -o gsd-vs-baseline.html
```

Include a within-experiment control only when:
- Your tasks don't overlap with existing baselines
- You need the control scored in the same run for time-controlled comparison
- It's a factorial design where the "neither" cell is part of the analysis

## Running Experiments

```bash
# Standard run with 5 workers
claude-benchmark experiment experiments/my-experiment.toml -c 5

# Skip confirmation prompt
claude-benchmark experiment experiments/my-experiment.toml -c 5 -y

# Resume interrupted experiment
claude-benchmark experiment experiments/my-experiment.toml --results-dir results/my-experiment-<timestamp>

# Re-run failed runs
claude-benchmark experiment experiments/my-experiment.toml --results-dir results/my-experiment-<timestamp> --retry-failures

# Skip LLM judge (static-only scoring)
claude-benchmark experiment experiments/my-experiment.toml --skip-llm-judge
```

## Analyzing Results

### Within-experiment report
```bash
claude-benchmark report results/my-experiment-<timestamp>/
```

Produces an HTML report with:
- Per-variant summary statistics (mean, stdev, 95% CI)
- Statistical tests (Mann-Whitney U, fallback Welch's t-test)
- Effect sizes (Cohen's d) with Bonferroni correction
- Task x variant heatmap
- Token efficiency metrics

### Cross-experiment comparison
```bash
claude-benchmark compare --cross-variant -x run-003 run-005 -o comparison.html
```

Finds overlapping (model, profile, task) combinations and performs pairwise statistical comparison. The `--cross-variant` flag expands each variant into a separate arm.

### Post-run compare workflows

After completing all experiments, build a unified picture:

```bash
# Validate bare controls are consistent across experiments
claude-benchmark compare --cross-variant -x run-003 run-005 -o control-consistency.html

# Best single-factor treatments head-to-head
claude-benchmark compare --cross-variant -x run-009 run-012 run-003 -o best-treatments.html

# All reasoning techniques: CoT vs skeleton-of-thought vs step-back
claude-benchmark compare --cross-variant -x run-005 <sot-id> <stepback-id> -o reasoning-techniques.html
```

## Key Findings (as of 2026-03-25)

### Completed Experiments (9/15)

| Experiment | Runs | Key Finding | Effect |
|---|---|---|---|
| temperature-sweep | 720 | temp=1.0 marginally best, lowest stdev | ~0 pts |
| chain-of-thought | 270 | CoT hurts on every variant and model | -3.5 pts (refactor) |
| politeness-sweep | 810 | Polite framing raises floor, reduces variance | +1.5 pts |
| context-pollution | 1,080 | Sonnet degrades at 50k padding; Opus improves (bizarre) | +/-8 pts |
| model-selection | 2,160 | Task-aware model routing beats any single model | ~5 pt spread |
| persona-sweep | 1,080 | Code-reviewer persona helps; others neutral | +2.9 pts (refactor) |
| persona-stacking | 5,400 | Stacking personas dilutes effectiveness | -0.5 pts |
| capstone-best-practices | 6,480 | Empty baseline (92.15) > all 13 CLAUDE.md profiles | r=-0.95 |
| gsd-methodology | 1,800 | GSD framing variants compared (no control; use compare) | TBD |

### Pending Experiments (7)

Not yet run: anchoring, constraint-formatting, emotional-stakes, instruction-ordering, skeleton-of-thought, step-back, interaction-persona-politeness.

### Cross-Cutting Insights

1. **Less is more**: r=-0.95 correlation between instruction token count and quality.
2. **Refactoring is sensitive**: Most prompting variations show largest effects on refactor tasks.
3. **Optimal stack**: code-reviewer persona + polite framing + temperature 1.0 + no CoT + clean context.
4. **Single factors only so far**: interaction-persona-politeness is the first factorial experiment testing whether effects combine.

## Creating New Experiments

1. Copy an existing experiment as a template
2. Write a clear hypothesis in the `description` field
3. Smoke test: `claude-benchmark experiment --dry-run experiments/my-experiment.toml`
4. Run with 30 reps: `claude-benchmark experiment experiments/my-experiment.toml -c 5`
5. Generate report and update the findings table in this document

## Source Code

| Component | File |
|---|---|
| TOML schema | `src/claude_benchmark/experiments/schema.py` |
| Loader and expander | `src/claude_benchmark/experiments/loader.py` |
| CLI command | `src/claude_benchmark/cli/commands/experiment.py` |
| Report generator | `src/claude_benchmark/reporting/experiment_generator.py` |
| Statistical tests | `src/claude_benchmark/reporting/regression.py` |
| Cross-run comparison | `src/claude_benchmark/catalog/compare.py` |
