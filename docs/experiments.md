# Experiment System

Experiments are structured comparisons of multiple prompting strategies (variants) across tasks, models, and replications with statistical analysis. Unlike single benchmark runs, experiments isolate the effect of a single variable and test it with enough power to detect real differences.

---

## Headline Findings

### Baseline competence predicts prompting responsiveness (primary)

The strongest pattern across 233K runs is not that any specific technique works — it is that low-baseline cells respond to prompting and high-baseline cells do not. Across all language × model combinations, kitchen-sink lift over bare baseline tracks bare baseline with slope -0.647 (each +1 bare-baseline point predicts -0.647 kitchen-sink lift, OLS, n=21,600). The apparent language-specific narrative — "JS is special," "Haiku+Go responds to CoT," "C# needs different rules" — collapses into baseline competence after residualization. JS shows the largest raw kitchen-sink lift (+7.25) because it has the lowest bare baseline (67.40), not because it is uniquely receptive. Residualized JS lift is -0.49 ± 1.02, right on the trendline. Python actually overperforms the trendline (+6.56 ± 1.06). C# underperforms (-6.76 ± 2.35) due to prompt contamination, not a structural property of C# (see insight #14).

The practical implication: identify your model × language × task combinations with low bare baselines, and apply prompting scaffolding there. Avoid stacking techniques on high-baseline combinations — you pay tokens with no return. Reference: experiment `capstone-v2` (21,600 runs); see insight #15.

### Universal phrasing beats language-specific rules (secondary)

A language-agnostic kitchen-sink ("follow the target language's standard conventions") scored 79.22 overall, outperforming every language-specific variant tested. Language-matched variants won only for Go (+14.37 over bare vs +12.57 universal) and JS (+8.57 vs +8.00). Language-specific C# rules hurt C# (-1.68 vs bare) even when correctly targeted (PascalCase, XML doc comments, constructor injection). Sonnet on C# collapses 17-18 points with any verbose prompt, replicated across two independent experiments totaling 34,560 runs. For multi-language repositories, "follow the target language's conventions" is the best default. Reference: experiment `language-kitchen-sink` (12,960 runs); see insight #17.

### Front-loading beats blind iteration (secondary)

Single-turn front-loading outperforms unconditional multi-turn self-review both in quality and token cost. Single-turn kitchen-sink (80.20) beats two-turn kitchen-sink (79.44) at half the output tokens (2,391 vs 5,039). Three-turn blind review is catastrophic for Sonnet (-8.5 to -11.1 across languages). Opus is the only model where two-turn sometimes helps (+1.4 Python, +1.7 JS).

Scope limitation: these results measure blind self-review, not closed-loop iteration where the model receives test results between turns. A follow-up experiment (multi-turn-v2, 10,748 scored runs) showed that test-feedback iteration substantially helps low-baseline combinations (Haiku+C# +19.04, Haiku+Go +14.71) — but front-loading still wins on cost-efficiency for the same token budget (kitchen-sink 76.77 vs test-feedback 73.92). Reference: experiments `multi-turn-conversation` and `multi-turn-conversation-v2`; see insight #16.

---

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
tasks = [
    # Python
    "code-gen-01", "code-gen-02", "code-gen-03", "code-gen-04", "code-gen-05",
    "bug-fix-01", "bug-fix-02", "bug-fix-03", "bug-fix-04",
    "refactor-01", "refactor-02", "refactor-03",
    # Go
    "code-gen-01-go", "code-gen-02-go", "code-gen-03-go", "code-gen-04-go", "code-gen-05-go",
    "bug-fix-01-go", "bug-fix-02-go", "bug-fix-03-go", "bug-fix-04-go",
    "refactor-01-go", "refactor-02-go", "refactor-03-go",
    # JavaScript
    "code-gen-01-js", "code-gen-02-js", "code-gen-03-js", "code-gen-04-js", "code-gen-05-js",
    "bug-fix-01-js", "bug-fix-02-js", "bug-fix-03-js", "bug-fix-04-js",
    "refactor-01-js", "refactor-02-js", "refactor-03-js",
    # C#
    "code-gen-01-cs", "code-gen-02-cs", "code-gen-03-cs", "code-gen-04-cs", "code-gen-05-cs",
    "bug-fix-01-cs", "bug-fix-02-cs", "bug-fix-03-cs", "bug-fix-04-cs",
    "refactor-01-cs", "refactor-02-cs", "refactor-03-cs",
]
models = ["haiku", "sonnet", "opus"]
profiles = ["empty"]
reps = 15

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

### 1. Use 15 reps per cell
With 48 cross-language tasks and 3 models, 15 reps keeps experiments under $500 estimated cost. The larger task set (48 vs 12) compensates for fewer reps per task — you get more data points across languages and task types. 5 reps is acceptable for smoke testing only.

### 2. Cover task diversity — all 4 languages
Include all 48 cross-language tasks (12 each for Python, Go, JS, C#) spanning bug-fix, code-gen, and refactor types. Single-language experiments are no longer acceptable — prompting effects frequently flip direction across languages (e.g., CoT hurts Python but helps Go/C#), so Python-only results are incomplete by default.

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

## Limitations and Validity Threats

**Pre-registration.** 0 of 21 experiments were pre-registered. Hypotheses were formed before data collection but were not registered with an independent registry prior to running. All findings should be treated as exploratory unless explicitly replicated under pre-registration. Per-finding classification is in `docs/findings-classification.md`; the template is in `docs/pre-registration-template.md`.

**Multiple comparisons.** Across 21 experiments and hundreds of pairwise comparisons, the family-wise error rate has not been controlled. The within-experiment reports apply Bonferroni correction for the variants in that experiment, but no correction spans the full corpus. The `claude-benchmark rigor` command applies Holm-Bonferroni (for primary contrasts) and Benjamini-Hochberg (for exploratory contrasts) and should be consulted before citing borderline findings.

**Statistical model.** Original within-experiment p-values use independent-sample tests (Mann-Whitney U or Welch's t). Runs are nested in (task, model, variant); the appropriate model is a mixed-effects regression with task and model as random intercepts. Treating nested observations as independent inflates degrees of freedom and may produce false positives, especially for effects in the 1-3 point range. Re-analyses using the rigor command address this.

**Judge in-family bias.** The judge (Haiku 4.5) is in the same model family as the subjects (Sonnet 4.6, Opus 4.6). In-family bias cannot be ruled out. See `docs/judge-selection.md` for calibration data and `docs/cross-family-judges.md` for cross-family rescoring tooling.

**Confound discovery.** Insight #14 documents a post-hoc confound: our Python-flavored kitchen-sink prompt contaminates C# scoring. Other confounds of this type may exist in the experiment corpus. See `docs/confound-audit.md` for a per-experiment confound table.

**Researcher allegiance.** The same author designed the tasks, prompts, judge criteria, and analysis pipeline. The scoring system, which determines whether a finding is significant, was built by the same person running the experiments. Independent replication has not occurred.

**Model drift.** Anthropic ships model updates without API-level snapshot guarantees on the aliases used (`claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-6`). Experiments run more than ~6 months apart may not be directly comparable even at the same alias. The Opus 4.7 pilot data (2026-05-12) shows measurable per-variant differences from the 4.6 baseline. See `docs/reproducibility.md` for the replication procedure.

**Generality.** 12 tasks per language is a small sample of programming work. Tasks are isolated single-file functions or modules, not features embedded in real codebases. The token-efficiency and prompting-sensitivity findings may not transfer to multi-file navigation, long-context refactoring, or domain-specific tasks with unfamiliar frameworks.

---

## Key Findings (as of 2026-04-30)

### Completed Experiments (20)

| Experiment | Runs | Key Finding | Effect |
|---|---|---|---|
| temperature-sweep | 720 | temp=1.0 marginally best, lowest stdev | ~0 pts |
| chain-of-thought | 270 | CoT hurts on every variant and model (Python) | -3.5 pts (refactor) |
| politeness-sweep | 810 | Polite framing raises floor, reduces variance (Python) | +1.5 pts |
| context-pollution | 1,080 | Sonnet degrades at 50k padding; Opus improves (bizarre) | +/-8 pts |
| model-selection | 2,160 | Task-aware model routing beats any single model | ~5 pt spread |
| persona-sweep | 1,080 | Code-reviewer persona helps; others neutral | +2.9 pts (refactor) |
| persona-stacking | 5,400 | Stacking personas dilutes effectiveness | -0.5 pts |
| capstone-best-practices | 6,480 | Empty baseline (88.0) outperforms all 13 tested CLAUDE.md profiles (exploratory); tuned-sonnet (96.3) wins | r=-0.95 |
| cross-language | 5,760 | Model gap widens 10-30x outside Python; persona is language-dependent | up to 29 pt spread |
| cot-cross-language | 2,880 | CoT hurts Python (-0.5) but helps Go (+5.3), JS (+1.7), C# (+7.7) | +13.9 (Haiku+C#) |
| politeness-cross-language | 2,880 | Polite framing helps JS (+2.8) only; hurts Go (-2.4) and C# (-1.8) | -8.0 (Haiku+Go) |
| gsd-methodology | 1,800 | Minimal executor prompts outperform verbose ones | +0.3 vs -1.4 |
| init-vs-best-practices | 4,320 | /init alone neutral; /init + code-reviewer persona is strongest variant (+1.64) | p=0.0001 |
| verification-instructions | 10,800 | Verification helps JS (+3.2, p=0.0002) but not Python; "trace 3 examples" is best variant | +4.6 (Opus+JS) |
| targeted-constraints | 4,320 | "Brief docstrings" is quality-neutral (-0.33, n.s.), 19% cheaper; "no docstrings" hurts Opus (-4.3) | -19% cost |
| capstone-v2 | 21,600 | Kitchen-sink lift predicted by bare baseline (-0.647/pt, OLS); JS lift is baseline effect not JS-specific; C# underperformance is prompt contamination; WHAT/HOW flips by language; framing direction is noise; verification redundant with persona; persona+CoT dilutive in JS | +2.17 overall (kitchen-sink) |
| language-kitchen-sink | 12,960 | Universal kitchen-sink (79.22) beats all language-specific variants overall; language-matched wins for Go (+14.37) and JS (+8.57) only; C#-specific rules also hurt C# (-1.68 vs bare); Sonnet+C# collapses 17-18 pts with any verbose prompt; for multi-language repos, "follow the target language's conventions" is the best default | +6.90 overall (universal) |
| multi-turn-conversation | 12,960 | Unconditional self-review degrades quality: two-turn bare -0.38, three-turn bare -5.09 vs single-turn. Front-loaded instructions (single-turn kitchen-sink, 80.20) beat iterative review (two-turn kitchen-sink, 79.44) at half the token cost. Sonnet collapses -8.5 to -11.1 at three turns. **Caveat:** follow-ups are generic and unconditional — model cannot run tests or see failures between turns. Results measure blind self-review, not closed-loop iteration with feedback. v2 experiment planned with conditional/evidence-based follow-ups. | -5.09 (three-turn) |
| verbosity-curve-cross-language | 8,640 | r=-0.95 is Python-specific content (PEP 8 rules), not verbosity per se. Language-neutral instructions: Python r=+0.03, Go r=+0.04, JS r=+0.15 (positive, p<0.001, monotonic +5.11 from bare to lines-200), C# r=+0.02. Output tokens: JS +54.5% at lines-200 for +7.5% quality. | r=+0.15 (JS) |
| doc-brevity-cross-language | 6,480 | "Keep docs brief" confirmed cross-language. Token reduction: Python 31.63%, JS 19.92%, C# 18.39%, Go 15.32%. Quality neutral or positive everywhere (C# +2.36%). No-docs: Python -2%, C# +5.4%. Haiku sees largest reductions (16-43%); Sonnet smallest (11-25%). | ~21% avg reduction |
| cheap-model-rich-prompt-cross-language | 3,600 | Haiku+persona = Opus in Python only (+0.76). JS close (-3.12). Go catastrophic: 47.62 vs 79.09 (-31.47). C# catastrophic: 42.96 vs 75.51 (-32.56). Persona hurts Haiku in Go (-2.5) and C# (-4.2). Model spread: Python ~8pts, Go ~29pts, C# ~28pts. | -31 to -33 pts (Go/C#) |

### Presentation Gap Experiments (6) — Status

Experiments designed to back claims in the best practices presentation that lack direct evidence. See `experiments/CHECKLIST.md` Tier 0.

| Experiment | Runs | Gap Addressed | Status |
|---|---|---|---|
| outcome-vs-implementation | — | "State WHAT not HOW" claim | **CLOSED by capstone-v2.** WHAT/HOW flips by language: JS wants HOW (+5.72), C# wants WHAT (+7.94), Python/Go neutral |
| positive-vs-negative-framing | — | +0.66 finding was confounded | **CLOSED by capstone-v2.** Framing direction is noise (P-N: +0.07 Python, -0.27 JS, +0.71 Go, +2.36 C# borderline) |
| optimal-stack-cross-language | — | Go/C# stack never tested as unit | **CLOSED by capstone-v2.** go-cs-stack (CoT only) scored +0.36 overall (n.s.); python-js-stack (persona+polite) scored +1.22 (p=0.016) |
| front-load-vs-iterate | 4,320 | "Iteration is the skill" hook has zero runs | **PARTIALLY CLOSED.** Kitchen-sink (front-loading proxy) is +0.77 Python but +7.25 JS -- baseline-dependent (low baselines respond to front-loading), not a universal anti-pattern |
| targeted-constraints | 4,320 | Docstring verbosity caveat untested | **CLOSED.** Completed as standalone experiment (see findings table) |
| interaction-persona-politeness | — | Persona x politeness interaction | **CLOSED by capstone-v2.** python-js-stack = persona+polite; persona+CoT is dilutive in JS (-2.40) but synergistic in Go/C# |

### Pending Experiments (7+)

Not yet run: anchoring, constraint-formatting, context-depth-quality, emotional-stakes, instruction-ordering, instruction-position-in-claudemd, instruction-topic-density, skeleton-of-thought, static-vs-dynamic-context, step-back.

### /init Evaluation Experiment (completed)

Tested whether `/init`'s auto-generated CLAUDE.md helps or hurts vs. the empirically-derived best-practices stack. Decomposed the contribution of build commands (trimmed) vs. full architectural context (raw).

| Experiment | Runs | Result | Key Numbers |
|---|---|---|---|
| init-vs-best-practices | 4,320 | /init alone is neutral (+0.02, n.s.); /init + code-reviewer persona is the strongest variant measured (+1.64, p=0.0001). Trimming /init hurts rather than helps. | init-raw 88.03, init+practices **89.66**, best-practices 89.16, bare 88.01 |

**Key insight:** The r=-0.95 token/quality correlation is driven by *generic* instructions (style rules, design principles), not project-specific context. `/init` output (build commands, architecture, data models) is a different category — it carries neutral-to-positive signal and doesn't interfere with the code-reviewer persona.

### Source Leak–Inspired Experiments (4)

Designed after analysis of the Claude Code source leak (March 2026) which revealed CLAUDE.md reloads per-turn, 11-layer section-based prompt construction, 60+ tool definitions competing for attention, and 5 compaction strategies at ~167k tokens.

| Experiment | Runs | Hypothesis | Motivated By |
|---|---|---|---|
| instruction-position-in-claudemd | 4,320 | Primacy effects: critical instructions at top of CLAUDE.md outperform buried ones | 11-layer section-based prompt |
| static-vs-dynamic-context | 6,480 | Task-relevant context inverts r=-0.95 correlation vs. static boilerplate | UserPromptSubmit hook additionalContext |
| instruction-topic-density | 7,560 | Single-topic focus outperforms multi-topic at same token count | 60+ tools competing for attention |
| context-depth-quality | 3,240 | Quality degradation curve from 0-80k padding across all 3 models | 5 compaction strategies, 167k boundary |

### Cross-Cutting Insights

1. **Less is more -- unless baselines are low**: r=-0.95 correlation between instruction token count and quality in Python. Kitchen-sink shows its largest lift where bare baselines are lowest (JS +7.25, bare 67.40). A regression analysis (21,600 runs) found this is a **baseline competence effect**: each +1 bare baseline point predicts -0.647 kitchen-sink lift (OLS). Residualized analysis shows JS is right on the trendline (-0.49 +/- 1.02) -- it's not uniquely receptive, it just has the lowest baseline. Python actually overperforms the trendline (+6.56 +/- 1.06). C# underperforms (-6.76 +/- 2.35) due to prompt contamination (see insight #14).
2. **Refactoring is sensitive**: Most prompting variations show largest effects on refactor tasks. Kitchen-sink shows its largest lift on refactoring (+2.98 over bare).
3. **Python optimal stack**: code-reviewer persona + polite framing + temperature 1.0 + no CoT + /init project context.
4. **Go/C# optimal stack**: CoT prefix + no persona + no polite framing + Sonnet (Go) or Opus (C#). Opposite of Python.
5. **JS optimal stack**: kitchen-sink (everything) or implementation-focused instructions + code-reviewer persona + polite framing. JS benefits most from verbose instructions because it has the lowest bare baseline -- but the underlying mechanism is baseline competence, not a JS-specific property.
6. **Language is the biggest moderator**: CoT, politeness, persona, WHAT-vs-HOW, and kitchen-sink all flip direction between languages. Capstone-v2 (21,600 runs) confirms: no single prompting strategy is universally optimal.
7. **Haiku is the canary**: prompting effects are largest (positive and negative) on Haiku. If a technique helps Haiku, it probably helps everywhere; if it hurts Haiku, proceed with caution.
8. **Sonnet is resistant to prompting**: Max prompting lift for Sonnet is +1.13 (capstone-v2). Haiku responds at +3.15, Opus at +3.67. If you're using Sonnet, don't overthink your prompts.
9. **Project context ≠ generic instructions**: /init's project-specific output (build commands, architecture, data models) doesn't hurt despite adding ~600 tokens, while the same token count of generic style rules actively degrades quality in Python. The type of content matters more than the token count.
10. **Verification is redundant with persona**: "Trace 3 examples" helps JS (+3.2) as a standalone technique, but adds zero marginal value when stacked on the persona stack. The persona already captures the benefit.
11. **WHAT vs HOW flips by language**: Outcome-focused ("produce correct code") helps C# (+3.57) but implementation-focused ("use early returns, extract helpers") helps JS (+5.72). Python and Go are indifferent. The "state WHAT not HOW" advice needs a language qualifier. The JS preference for HOW may be partially a baseline effect. The C# preference for WHAT (and strong aversion to HOW) may be prompt contamination -- our implementation-focused prompt uses Python-specific rules (snake_case, list comprehensions) that actively misdirect C# generation.
12. **Framing direction is noise**: Positive vs negative rule phrasing showed no significant difference across 20,499 clean scored runs. The original +0.66 was confounded by content differences, not framing valence.
13. **Persona + CoT interaction is language-dependent**: Dilutive in JS (-2.40 interaction), synergistic in Go (+0.78) and C# (+0.90). Never combine both for JS.
14. **C# kitchen-sink underperformance is prompt contamination**: Our kitchen-sink prompt uses Python-flavored rules (snake_case, list comprehensions, type hints, PEP 8 references) that actively misdirect C# code generation. After residualization, C# underperforms the baseline trendline by -6.76 +/- 2.35 points. Tight-band analysis (bare 68-73) confirms: Python +2.28, JS +4.37, Go -1.35, C# -10.51 -- overlapping CIs for Python/JS/Go, C# is the outlier. We are designing language-specific kitchen-sink variants to test this hypothesis.
15. **Baseline competence predicts prompting responsiveness**: The global slope of -0.647 (kitchen-sink lift per +1 bare point) means the "JS is special" framing was wrong. The correct model: low baselines respond to prompting regardless of language. This applies across language/model/task combinations -- Haiku+Go, Haiku+C#, and hard Python tasks all show the same pattern as JS on average.
16. **Unconditional self-review hurts — front-load instead of iterate (12,960 runs)**: Asking the model to "review and fix" its own output without evidence (test results, error messages) degrades quality (-0.38 at two turns, -5.09 at three turns vs single-turn bare). The model feels obligated to change *something*, introducing regressions in already-correct code. Single-turn with good instructions (kitchen-sink 80.20) beats two-turn with the same instructions (79.44) at half the output tokens (2,391 vs 5,039). Three-turn is catastrophic for Sonnet (-8.5 to -11.1 across languages). Opus is the only model where two-turn sometimes helps (+1.4 Python, +1.7 JS). **Important scope limitation:** this tests blind self-review, not closed-loop iteration where the model can run tests and react to specific failures. Real multi-turn with tool use may behave differently — v2 experiment planned.
17. **Language-agnostic phrasing beats language-specific rules (12,960 runs)**: A universal kitchen-sink ("follow the target language's standard conventions") scored 79.22 overall, beating every language-specific variant including Go-specific (78.10) and the Python original (76.85). Language-matched variants won for Go (+14.37 over bare, vs +12.57 universal) and JS (+8.57 vs +8.00), but the universal variant won for Python (+1.50 vs +0.70) and C# (+5.51 vs -1.68). The C#-specific variant actively hurt C# — even correctly-targeted rules (PascalCase, XML doc comments, DI patterns) interfere with the model's priors. Sonnet on C# collapses 17-18 points with any kitchen-sink variant (replicated in capstone-v2 and this experiment). For multi-language repos, universal phrasing is the optimal default.
18. **Verbosity r=-0.95 was content-driven, not length-driven (8,640 runs)**: The original correlation was driven by Python-specific instruction content (PEP 8 rules, list comprehensions, snake_case). With language-neutral instructions across 4 languages: Python r=+0.03 (flat), JS r=+0.15 (significant, p<0.001), Go r=+0.04 (flat), C# r=+0.02 (noisy). JS improves monotonically +5.11 from bare to 200 lines — consistent with the baseline-competence model (JS has lowest baseline). Token cost: JS +54.5% output at lines-200 for +7.5% quality.
19. **Doc brevity confirmed cross-language (6,480 runs)**: "Keep docstrings brief" produces 15-32% output token reduction with quality neutral or positive in all 4 languages. Per-language: Python 31.63%, JS 19.92%, C# 18.39%, Go 15.32%. C# actually improved +2.36% with the rule. No-docs variant is language-dependent: hurts Python (-2%) but helps C# (+5.4%). Haiku sees largest reductions (16-43%); Sonnet smallest (11-25%).
20. **Model substitution is Python-specific (3,600 runs)**: Haiku+persona matches Opus in Python (+0.76) and is close in JS (-3.12). Go and C# gaps are catastrophic: -31.47 and -32.56 respectively. Persona actually hurts Haiku in Go (-2.5) and C# (-4.2). The "use Haiku for cost savings" recommendation must be scoped to Python only. Model spread: Python ~8pts, Go ~29pts, C# ~28pts.

## Pilot Findings — Awaiting Confirmation

These findings are **5-rep pilot results** (not the standard 15 reps) and should be treated as directional signal, not validated guidance, until a 15-rep follow-up lands. Wider confidence intervals than the cross-cutting insights above; effects under ~2 points are inside the noise floor.

### Opus 4.7 vs Opus 4.6 on capstone-v2 (2026-05-12, 2,151 scored runs)

Compares run-055 (`capstone-v2-opus47`, opus-4-7 only, 5 reps) against the opus slice of `experiment-capstone-v2-20260423-120039` (15 reps, opus-4-6).

**Aggregate:** 4.7 essentially matches 4.6 (-0.58, opus-4-7 80.63 vs opus-4-6 81.21). Opus remains the strongest model overall.

**Per-language deltas:**
- Python: **+1.73** (91.09 vs 89.36)
- Go: +0.28 (essentially flat)
- JS: -0.82 (essentially flat)
- C#: **-3.40** (74.51 vs 77.91) — only meaningful regression

**Variant deltas (4.7 minus 4.6, 5-rep pilot):**
- outcome-focused: **+3.07** (best Opus 4.7 variant)
- positive-framing: +1.58
- negative-framing: +1.45
- implementation-focused: +0.25 (n.s.)
- persona-plus-cot: -0.71 (n.s.)
- bare: -1.88
- verify-on-stack: -2.26
- go-cs-stack (CoT): -3.05
- python-js-stack (persona+polite): **-4.53**

**Pattern:** the persona/CoT/verify scaffolding stacks that lifted 4.6 hurt 4.7 in this pilot, while terse outcome statements and framing variants help. Reads like Opus 4.7 is less malleable to prompt scaffolding — but needs 15-rep confirmation before changing published guidance (insights #3, #4, #5 above).

**Best variant per language flipped (4.6 → 4.7):**
- Python: verify-on-stack → outcome-focused
- Go: implementation-focused → persona-plus-cot
- C#: outcome-focused → positive-framing
- JS: kitchen-sink → implementation-focused (data artifact, see caveats)

**Caveats:**
1. **Kitchen-sink had zero scored runs on 4.7** — Opus 4.7 rejects any explicit `temperature` value (`"`temperature` is deprecated for this model"`). The variant config was fixed (temperature pin removed) but no kitchen-sink data exists yet for 4.7. The JS "best variant" comparison above is therefore a data artifact, not a real flip.
2. **Power asymmetry:** 5 reps × 240 cells (4.7) vs 15 reps × 1,440 cells (4.6). Effects under ~2 points are inside the noise floor on the 4.7 side.
3. **Judge calibration drift:** 4.7 was scored ~3 weeks after the 4.6 baseline. Same judge model (Haiku 4.5) and weights, but tokenization or proxy version drift could nudge ~1 point.
4. **15-rep follow-up blocked:** attempted on 2026-05-12 but tripped a $300 hard budget cap on the API proxy token after 143 runs. Deferred until cap is raised or a different token/backend is available. The original 5-rep pilot used $181 of that cap; a full 15-rep run is dry-run-estimated at $543.

**What to do until confirmed:** flag any 4.7-specific guidance as preliminary. Don't update insights #3 (Python optimal stack), #4 (Go/C# optimal stack), or #5 (JS optimal stack) yet — the 5-rep pilot suggests they may not transfer to 4.7, but two of those four "best variant" flips have n=60 cells per side and one (JS) is corrupted by missing kitchen-sink data.

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

---

## Related Work

Claude-benchmark differs from existing code-generation benchmarks in two ways: (1) it measures prompting and configuration effects rather than raw model capability, and (2) it controls for cross-language generalization, which is rare in the prompting literature.

**Capability benchmarks** — The primary peer benchmarks measure what models can do, not how configuration affects what they do:

- **HumanEval** (Chen et al., 2021) — 164 Python programming problems, function completion from docstrings. Single-language, no prompting variation.
- **MBPP** (Austin et al., 2021) — 974 Python problems sourced from programming challenges. Single-language capability, no configuration treatment.
- **SWE-bench** (Jimenez et al., 2024) — Repository-level bug fixing from GitHub issues. Tests agentic task completion, not prompting effects on single-file generation.
- **BigCodeBench** (Zhuo et al., 2024) — 1,140 function completion problems across diverse libraries. Broader capability coverage but no prompting variation.
- **LiveCodeBench** (Jain et al., 2024) — Contamination-resistant capability benchmark using problems after the training cutoff. Single-language focus.

**Prompting literature** — The techniques tested in this benchmark have roots in:

- **Wei et al. (2022)** — Chain-of-thought prompting. Demonstrated CoT benefits for arithmetic and commonsense reasoning. Does not evaluate code generation across languages.
- **Kojima et al. (2022)** — Zero-shot CoT ("Let's think step by step"). Generalization of Wei et al. to zero-shot settings. Same scope limitation.
- **Lilian Weng's prompt engineering guide** and the **Anthropic prompt engineering documentation** — Practitioner-oriented summaries of technique research. Not empirically validated on cross-language code generation.

This benchmark extends the prompting literature by treating language and model as moderating variables. The CoT finding — it hurts Python, helps Go and C# substantially — is not predicted by the reasoning-task literature and would not appear in single-language capability evaluations. Similarly, the baseline-competence model (slope -0.647, insight #15) is a cross-language generalization of the prompting-responsiveness question that has no direct analog in the published literature.

