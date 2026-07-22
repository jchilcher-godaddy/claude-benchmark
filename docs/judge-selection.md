# Judge Model Selection

This document explains why **Claude Haiku 4.5** is the default LLM judge for claude-benchmark, backed by calibration data from a 351-call experiment run on 2026-03-09.

## The Problem

The LLM judge scores benchmark outputs on four criteria (1-5 scale). Before trusting any single judge, we need to know:

1. **Is it deterministic?** If the same code gets different scores on repeated runs, measurement noise drowns out real signal.
2. **Can it discriminate?** If gold-standard code and degraded code get similar scores, the judge can't detect quality differences.
3. **Does it agree with other models?** If judges disagree wildly, we need to understand why.

## Calibration Method

The `cb calibrate` command answers these questions by scoring **known-quality code** with each candidate model.

### Calibration Samples

Reference solutions from all 9 builtin tasks are programmatically degraded into 3 quality tiers:

| Tier | Transformation | Purpose |
|------|---------------|---------|
| **gold** | Unchanged reference solution | Establishes the quality ceiling |
| **mild** | Docstrings stripped | Tests sensitivity to readability cues |
| **severe** | Docstrings stripped + local variables renamed to single letters + type hints removed + try/except blocks flattened | Simulates poor-quality code that still runs |

This produces 27 samples (9 tasks x 3 tiers). Each sample is scored multiple times per model (5 reps for haiku/sonnet, 3 for opus) for a total of 351 API calls.

### Metrics

**Per-model:**
- **Determinism**: percentage of (sample, criterion) groups where repeated scoring produces identical results
- **Mean variance**: average intra-sample score variance across all groups
- **Discrimination** (Cohen's d): effect size between gold and severe tier scores — measures how well the judge separates quality levels
- **Tier correlation** (Spearman r): correlation between tier ordinal (severe=1, mild=2, gold=3) and judge score — measures whether the judge's ordering matches known quality

**Cross-model:**
- **Inter-rater agreement**: averaged pairwise Spearman correlation of mean scores across all models

### Recommendation Formula

```
score = 0.40 * norm(discrimination) + 0.30 * norm(determinism) + 0.30 * norm(inverse_variance)
```

All components normalized 0-1 across candidate models. Discrimination is weighted highest because a judge that can't tell good code from bad is useless regardless of consistency.

## Results

Run date: 2026-03-09. All 351 API calls succeeded (0 failures).

### Summary

| Model | Determinism | Variance | Discrimination (d) | Gold Mean | Mild Mean | Severe Mean | Tier Corr | Score |
|-------|-------------|----------|-------------------|-----------|-----------|-------------|-----------|-------|
| **Haiku** | **99.1%** | **0.003** | **2.03** | 96.5 | 91.7 | 71.1 | **0.67** | **0.99** |
| Opus | 99.1% | 0.003 | 1.42 | 90.3 | 87.5 | 70.4 | 0.51 | 0.87 |
| Sonnet | 71.3% | 0.126 | 1.14 | 86.7 | 86.9 | 70.3 | 0.42 | 0.44 |

### Per-Criterion Discrimination (Cohen's d)

| Model | code_readability | architecture_quality | instruction_adherence | correctness_reasoning |
|-------|-----------------|---------------------|----------------------|----------------------|
| **Haiku** | **3.96** | **1.71** | 0.33 | 0.92 |
| Opus | 2.08 | 0.68 | **0.74** | 0.19 |
| Sonnet | 2.12 | 0.35 | -0.18 | 0.70 |

**Inter-rater agreement**: 0.63 (moderate — model choice meaningfully affects scores).

## Why Haiku

### 1. Best discrimination (d = 2.03)

Haiku separates gold from severe code with a "huge" effect size (d > 0.8 is large by convention; 2.03 is exceptional). This means quality differences in benchmark outputs will show up clearly in scores rather than being buried in noise.

Opus (1.42) is good but less sharp. Sonnet (1.14) is the weakest discriminator.

### 2. Highest determinism (99.1%)

Haiku and Opus both achieve 99.1% deterministic scoring — the same code gets the same score on repeated evaluations. This is critical for experiments like temperature sweeps where you need to isolate the effect of a single variable without judge noise confounding results.

Sonnet at 71.3% determinism (45x higher variance) would inject unacceptable measurement noise.

### 3. Strongest readability sensitivity (d = 3.96)

Haiku's `code_readability` discrimination is nearly double opus/sonnet. Since quality variations in LLM-generated code most commonly manifest as style and readability differences (not correctness failures), this sensitivity is exactly what a benchmark judge needs.

### 4. Correct tier ordering

Haiku's tier means show clear monotonic separation: gold (96.5) > mild (91.7) > severe (71.1). The 4.8-point gap between gold and mild confirms it detects even subtle quality drops like missing docstrings.

Sonnet cannot distinguish mild from gold at all (86.9 vs 86.7) — a judge that gives the same score to documented and undocumented code is not useful for quality measurement.

### 5. Cheapest and fastest

Haiku is the least expensive model per call and has the lowest latency. Since a full benchmark run may invoke the judge dozens of times, cost and speed matter. Using Haiku as the judge lets the budget go toward more reps (statistical power) rather than a more expensive judge that performs worse.

### 6. Avoids self-evaluation bias

The benchmark's primary subjects are Sonnet and Opus. Using Haiku as the judge avoids the self-evaluation trap where a model grades its own output. There is no guarantee that self-evaluation produces inflated scores, but eliminating the possibility removes a confound.

## When to Re-Calibrate

Re-run `cb calibrate` if:

- A new Claude model is released that could serve as judge
- The builtin task set changes substantially (new reference solutions)
- You add custom criteria that might change model sensitivity
- You observe unexpected scoring patterns in experiment results
- After human-rater validation, to compare per-criterion human-judge agreement
- After a cross-family judge run, to verify Haiku's ranking holds when using GPT-4o or Gemini

```bash
# Quick check with one task
cb calibrate --task code-gen-01 --reps 1 --model haiku

# Full calibration (saves JSON report)
cb calibrate --output calibration-report.json
```

---

## Limitations of the Calibration Method

**The calibration gradient is synthetic, not drawn from real model outputs.** The three quality tiers (gold, mild, severe) are produced by programmatic degradation of reference solutions: stripping docstrings, renaming variables to single letters, removing type hints, flattening try/except blocks. This is a controlled signal, not a sample of LLM outputs at varying quality. The high discrimination score (d=2.03) reflects Haiku's ability to separate this specific synthetic gradient. Whether that discrimination transfers to real model outputs — where quality differences are more subtle and multi-dimensional — has not been verified. The calibration establishes a necessary condition for judge utility, not a sufficient one.

**No expert-human-rater study has been conducted.** The judge has not been validated against assessments by professional software engineers or domain experts. Human-judge agreement is the standard validity check for LLM-as-judge systems and has not been performed here. This is the single largest validity gap and the recommended next step before any external publication of findings. Results from a human-rater study may revise the per-criterion weights or the choice of judge model.

**Haiku is in the same model family as the subjects.** The primary benchmark subjects are Sonnet and Opus, which are in the same Claude family as Haiku. While the calibration demonstrates determinism and discrimination, in-family bias — where Haiku's aesthetic or stylistic preferences align with Sonnet/Opus outputs in ways that diverge from human preferences — cannot be ruled out. Cross-family judge support (`docs/cross-family-judges.md`) allows rescoring a sampled subset with GPT-4o or Gemini to check for sign-stability of key effects.

**Calibration sample size is small.** The calibration study used 27 samples (9 tasks × 3 tiers) scored 5 times each for Haiku and Sonnet, and 3 times for Opus, totaling 351 API calls. The Sonnet-judge variance estimate (0.126) is based on this small sample and may understate true variability. The discrimination and tier-correlation estimates carry meaningful uncertainty that is not reflected in the summary table.

## Source Code Reference

| Component | File |
|-----------|------|
| Calibration samples & degrader | `src/claude_benchmark/calibration/degrader.py` |
| Calibration runner | `src/claude_benchmark/calibration/runner.py` |
| Metrics & recommendation | `src/claude_benchmark/calibration/metrics.py` |
| CLI command | `src/claude_benchmark/cli/commands/calibrate.py` |
