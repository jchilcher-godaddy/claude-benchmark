# Scoring Methodology

This document describes how claude-benchmark scores code outputs. Every run produces a **composite score** (0-100) combining automated static analysis with LLM-as-judge evaluation, plus a separate token efficiency metric.

## Composite Score

```
composite = (static_total * 0.50) + (llm_normalized * 0.50)
```

Both halves are normalized to 0-100 before combining. If the LLM judge fails or is skipped, the composite falls back to the static score alone.

---

## Static Analysis (50% of composite)

Three tools run against the output code, each producing a 0-100 sub-score. These are combined with fixed weights:

```
static_total = (test_pass_rate * 0.50) + (lint_score * 0.30) + (complexity_score * 0.20)
```

### Test Pass Rate (50% of static)

**Tool**: pytest with `pytest-json-report`

Tests are defined per-task in the task directory. The score is the percentage of tests passing:

```
test_pass_rate = (passed / total) * 100
```

If a task has no tests, the score is 0 (no tests = no credit). Pytest runs with a 120-second timeout; timeouts score 0.

### Lint Cleanliness (30% of static)

**Tool**: Ruff

Measures code cleanliness by counting lint violations relative to lines of code:

```
lint_score = max(0, 100 - (error_count / LOC) * 1000)
```

This means roughly 10 errors per 100 lines of code yields a score of 0. Zero errors = 100. If there's no code (0 LOC), the score is 100 (nothing to lint). LOC counts non-empty, non-comment lines.

### Cyclomatic Complexity (20% of static)

**Tool**: Radon (Python API)

Measures average cyclomatic complexity across all functions/methods. Lower complexity scores higher. The mapping uses piecewise linear segments aligned with Radon's letter grades:

| Avg Complexity | Radon Grade | Score Range |
|---------------|-------------|-------------|
| 1-5           | A           | 100 - 80    |
| 6-10          | B           | 80 - 60     |
| 11-20         | C           | 60 - 40     |
| 21-30         | D           | 40 - 20     |
| 31-40         | E           | 20 - 5      |
| 41+           | F           | 5 - 0       |

If there are no functions (complexity = 0), the score is 100. Code that fails to parse receives worst-case complexity of 50 (F-rank).

---

## LLM-as-Judge (50% of composite)

An LLM evaluates the code against a structured rubric, producing qualitative scores that complement the mechanical static analysis.

### Judge Model

The default judge is **Claude Haiku 4.5**, chosen to avoid self-evaluation bias when benchmarking Sonnet or Opus. The judge model is configurable.

### Criteria

Four built-in criteria are evaluated on a 1-5 Likert scale. Each requires a 1-2 sentence reasoning justification.

| Criterion | What it measures |
|-----------|-----------------|
| `code_readability` | Clarity, naming conventions, commenting, maintainability |
| `architecture_quality` | Separation of concerns, abstractions, SOLID principles, extensibility |
| `instruction_adherence` | Whether the output follows task requirements, constraints, and edge case specifications |
| `correctness_reasoning` | Logical correctness, error handling, robustness, edge case coverage |

Tasks can define additional custom criteria that are evaluated alongside the built-in four.

### Scale

```
1 = Poor: Fundamentally broken or missing
2 = Below average: Major issues that affect functionality or quality
3 = Adequate: Meets basic requirements with some issues
4 = Good: Well-implemented with minor issues
5 = Excellent: Exemplary implementation, no meaningful improvements needed
```

### Normalization

The average across all criteria is linearly mapped to 0-100:

```
llm_normalized = (average - 1) * 25
```

| Average Score | Normalized |
|--------------|------------|
| 1.0          | 0          |
| 2.0          | 25         |
| 3.0          | 50         |
| 4.0          | 75         |
| 5.0          | 100        |

### Reliability

The judge uses structured JSON output (`--json-schema`) to force well-formed responses. If the first attempt fails validation (missing criteria, malformed JSON, empty reasoning), it retries once with a more explicit prompt. If both attempts fail, the run falls back to static-only scoring.

---

## Token Efficiency (separate metric)

Token efficiency measures quality relative to cost. It is reported alongside the composite score but is **not** folded into it.

### Primary: points_per_dollar (cost-weighted)

```
cost_usd = (input_tokens / 1M) * model_input_price + (output_tokens / 1M) * model_output_price
points_per_dollar = composite_score / cost_usd
```

Higher is better. This accounts for the fact that output tokens cost 5x more than input tokens across all models. Model-specific pricing is applied automatically (Haiku: $1/$5, Sonnet: $3/$15, Opus: $5/$25 per MTok input/output).

### Secondary: points_per_1k_tokens (raw)

```
points_per_1k_tokens = (composite_score / total_tokens) * 1000
```

Retained for backward compatibility. Treats all tokens equally regardless of direction or model, so it understates the cost of verbose output and overstates the cost of large input contexts.

### Token breakdown

Token counts are split into two components:
- **CLAUDE.md context tokens**: tokens consumed by the system prompt / CLAUDE.md content
- **Task I/O tokens**: tokens consumed by the task prompt and model response

This separation lets you see whether a large CLAUDE.md is paying for itself in quality.

---

## Aggregation Across Runs

When multiple runs are executed per configuration, the following statistics are computed:

- **Mean** and **standard deviation** of composite scores
- **95% confidence interval** (useful for small sample sizes)
- **Min/max** values
- Raw values preserved for transparency

### Experiment Mode

In experiment mode (variant comparisons), statistical tests compare each treatment variant against a control:
- **p-value** from the comparison test (significance threshold: p < 0.05)
- **Effect size** (Cohen's d)
- Per-task breakdowns in a variant-by-task heatmap

---

## Customization

### Per-Task Weight Overrides

Task definitions can override the default static analysis weights. For example, a refactoring task might weight complexity higher:

```yaml
scoring_weights:
  test_pass_rate: 0.40
  lint_score: 0.20
  complexity_score: 0.40
```

Weights must sum to 1.0.

### Custom LLM Criteria

Tasks can add criteria beyond the four built-in ones:

```yaml
custom_criteria:
  - name: performance_awareness
    description: "Considers algorithmic efficiency and avoids unnecessary allocations"
```

Custom criteria are scored on the same 1-5 scale and averaged together with the built-in criteria.

---

## Source Code Reference

| Component | File |
|-----------|------|
| Static scorer (Ruff, pytest, radon) | `src/claude_benchmark/scoring/static.py` |
| LLM judge scorer | `src/claude_benchmark/scoring/llm_judge.py` |
| Judge prompts and criteria | `src/claude_benchmark/scoring/prompts.py` |
| Composite combination | `src/claude_benchmark/scoring/composite.py` |
| Token efficiency | `src/claude_benchmark/scoring/token_efficiency.py` |
| Pydantic models | `src/claude_benchmark/scoring/models.py` |
| Scoring pipeline orchestration | `src/claude_benchmark/scoring/pipeline.py` |

---

## Limitations

**Composite weights are author-specified, not empirically derived.** The 50/50 static/LLM split and the 50/30/20 within-static weighting reflect the author's judgment about relative importance, not an optimization against ground-truth quality assessments. A sensitivity analysis is available via `claude-benchmark sensitivity` (see Stream 2 tooling). Findings that hinge on close composite-score comparisons should be confirmed against the individual sub-scores.

**The 1-5 Likert-to-100 mapping assumes equal-interval scaling.** Treating Likert responses as a continuous interval scale is contested in measurement theory. For borderline findings (effect sizes under ~2 points), confirm using the raw Likert distribution — Wilcoxon signed-rank or ordinal regression is more appropriate than comparing linearized means.

**Test pass rate weights all tests equally regardless of difficulty.** A single-assertion test for a trivial helper and a multi-assertion integration test for a complex function count the same. This may inflate pass-rate scores for tasks where the test suite is unbalanced.

**Lint score is calibrated to Python.** The lint score formula is derived from Ruff, a Python linter. For Go, JavaScript, and C# tasks, the lint sub-score uses language-appropriate tools (see language-specific scorer files `lang_*.py`), but the 50/30/20 weighting was tuned on Python experiments. Cross-language lint scores are not directly comparable to Python lint scores.

**Cyclomatic complexity via Radon is Python-only.** For non-Python languages, language-specific parsers in the `lang_*.py` scorer files compute equivalent metrics, but the piecewise linear mapping to 0-100 was defined against Radon's grade thresholds and may not be well-calibrated for those parsers' output distributions.

**Token efficiency uses Anthropic list pricing.** Cost figures use published list prices: Haiku $1/$5, Sonnet $3/$15, Opus $5/$25 per MTok input/output. Actual costs may differ due to enterprise agreements, prompt caching discounts, batch API pricing, or proxy-layer markup. Cost figures in experiment reports and the cheat sheet are list-price approximations and should not be cited as actualized savings.

---

## Pre-registration and Multiple Comparisons

None of the 21 historical experiments in this benchmark were pre-registered. Hypotheses were formed before running each experiment, but were not registered with an independent registry (OSF or equivalent) prior to data collection. All findings should be treated as exploratory until replicated under pre-registration. Per-finding classification is in `docs/findings-classification.md`; the pre-registration template is in `docs/pre-registration-template.md`.

For multiple comparisons across the full experiment family, the recommended correction procedures are:

- **Holm-Bonferroni** (familywise error rate control) for primary contrasts — the handful of findings that inform published guidance
- **Benjamini-Hochberg** (false discovery rate control) for secondary and exploratory contrasts

The `claude-benchmark rigor` command (Stream 1 tooling) applies both procedures to a specified set of comparisons and reports adjusted p-values alongside the original ones.

