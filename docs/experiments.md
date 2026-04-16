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

## Key Findings (as of 2026-04-15)

### Completed Experiments (12)

| Experiment | Runs | Key Finding | Effect |
|---|---|---|---|
| temperature-sweep | 720 | temp=1.0 marginally best, lowest stdev | ~0 pts |
| chain-of-thought | 270 | CoT hurts on every variant and model (Python) | -3.5 pts (refactor) |
| politeness-sweep | 810 | Polite framing raises floor, reduces variance (Python) | +1.5 pts |
| context-pollution | 1,080 | Sonnet degrades at 50k padding; Opus improves (bizarre) | +/-8 pts |
| model-selection | 2,160 | Task-aware model routing beats any single model | ~5 pt spread |
| persona-sweep | 1,080 | Code-reviewer persona helps; others neutral | +2.9 pts (refactor) |
| persona-stacking | 5,400 | Stacking personas dilutes effectiveness | -0.5 pts |
| capstone-best-practices | 6,480 | Empty baseline (88.0) > all 13 CLAUDE.md profiles; tuned-sonnet (96.3) wins | r=-0.95 |
| cross-language | 5,760 | Model gap widens 10-30x outside Python; persona is language-dependent | up to 29 pt spread |
| cot-cross-language | 2,880 | CoT hurts Python (-0.5) but helps Go (+5.3), JS (+1.7), C# (+7.7) | +13.9 (Haiku+C#) |
| politeness-cross-language | 2,880 | Polite framing helps JS (+2.8) only; hurts Go (-2.4) and C# (-1.8) | -8.0 (Haiku+Go) |
| gsd-methodology | 1,800 | Minimal executor prompts outperform verbose ones | +0.3 vs -1.4 |

### Pending Experiments (8+)

Not yet run: anchoring, constraint-formatting, context-depth-quality, emotional-stakes, init-vs-best-practices, instruction-ordering, instruction-position-in-claudemd, instruction-topic-density, skeleton-of-thought, static-vs-dynamic-context, step-back, interaction-persona-politeness.

### /init Evaluation Experiment (1)

Tests whether `/init`'s auto-generated CLAUDE.md helps or hurts vs. the empirically-derived best-practices stack. Decomposes the contribution of build commands (trimmed) vs. full architectural context (raw).

| Experiment | Runs | Hypothesis | Motivated By |
|---|---|---|---|
| init-vs-best-practices | 4,320 | /init output is net-negative due to token cost; trimmed project facts + best practices may be optimal | r=-0.95 token/quality, /init adoption |

### Source Leak–Inspired Experiments (4)

Designed after analysis of the Claude Code source leak (March 2026) which revealed CLAUDE.md reloads per-turn, 11-layer section-based prompt construction, 60+ tool definitions competing for attention, and 5 compaction strategies at ~167k tokens.

| Experiment | Runs | Hypothesis | Motivated By |
|---|---|---|---|
| instruction-position-in-claudemd | 4,320 | Primacy effects: critical instructions at top of CLAUDE.md outperform buried ones | 11-layer section-based prompt |
| static-vs-dynamic-context | 6,480 | Task-relevant context inverts r=-0.95 correlation vs. static boilerplate | UserPromptSubmit hook additionalContext |
| instruction-topic-density | 7,560 | Single-topic focus outperforms multi-topic at same token count | 60+ tools competing for attention |
| context-depth-quality | 3,240 | Quality degradation curve from 0-80k padding across all 3 models | 5 compaction strategies, 167k boundary |

### Cross-Cutting Insights

1. **Less is more**: r=-0.95 correlation between instruction token count and quality.
2. **Refactoring is sensitive**: Most prompting variations show largest effects on refactor tasks.
3. **Python optimal stack**: code-reviewer persona + polite framing + temperature 1.0 + no CoT + clean context.
4. **Go/C# optimal stack**: CoT prefix + no persona + no polite framing + Sonnet (Go) or Opus (C#). Opposite of Python.
5. **Language is the biggest moderator**: CoT, politeness, and persona all flip direction between Python and Go/C#.
6. **Haiku is the canary**: prompting effects are largest (positive and negative) on Haiku. If a technique helps Haiku, it probably helps everywhere; if it hurts Haiku, proceed with caution.

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
