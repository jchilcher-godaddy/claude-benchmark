# claude-benchmark

A CLI tool for benchmarking CLAUDE.md configurations against standardized coding tasks. Runs tasks across bug fixes, code generation, refactoring, and instruction-following scenarios, then scores outputs using a composite of static analysis and LLM-as-judge evaluation.

## Architecture

```
src/claude_benchmark/
  cli/           # Typer-based CLI commands (run, experiment, report, compare, etc.)
  tasks/         # Task loader and validation
  execution/     # Parallel worker pool, retry logic, context padding
  scoring/       # Static analysis (pytest/ruff/radon) + LLM judge pipeline
  reporting/     # HTML report generation, charts, statistical analysis
  experiments/   # Multi-variant experiment schema and loader
  calibration/   # Judge model calibration (degrader, runner, metrics)
  catalog/       # Result set indexing, search, and cross-run comparison
  profiles/      # Profile loader
  templates/     # Jinja2 HTML report templates
  engine/        # Core benchmark engine
  display/       # Terminal output formatting
  results/       # Result models
  assets/        # Static assets for reports
```

## Scoring Pipeline

Composite = 50% static + 50% LLM judge.

**Static** (50/30/20): pytest pass rate, ruff lint, radon complexity.
**LLM judge**: Haiku 4.5 scores code_readability, architecture_quality, instruction_adherence, correctness_reasoning on 1-5 scale. See `docs/scoring-methodology.md` and `docs/judge-selection.md`.

## Experiment Design

Experiments test prompting hypotheses with controlled variants. Key principles:

1. **15 reps** per cell (keeps experiments under $500 with 48 tasks x 3 models)
2. **All 48 cross-language tasks** (12 each: Python, Go, JS, C#) — prompting effects flip direction across languages, so single-language experiments are incomplete
3. **All 3 models** (haiku, sonnet, opus) unless testing model-specific effects
4. **`profiles = ["empty"]`** to isolate prompt variations
5. **Prefer `compare --cross-variant` over duplicating controls** — existing bare baselines can be referenced across experiments via catalog IDs

See `docs/experiments.md` for the full guide.

## Testing

```bash
pytest
```

All tests use mocks — no API key required. When adding features, add unit tests for core logic and CLI integration tests using `typer.testing.CliRunner`.

## Key Experimental Findings

From 21 completed experiments (~212,000 runs):

- **Empty baseline wins for Python** — higher than all CLAUDE.md profiles (r=-0.95 token/quality)
- **Kitchen-sink lift is a baseline effect** — low bare baselines respond to prompting regardless of language (-0.647 lift per +1 bare point). JS shows largest raw lift (+7.25) because it has the lowest baseline (67.40), not because it's uniquely receptive
- **Universal kitchen-sink beats language-specific** — "follow the target language's conventions" (79.22) outperforms all language-specific variants. Language-matched wins only for Go (+14.37) and JS (+8.57). C#-specific rules hurt C# (-1.68). For multi-language repos, use universal phrasing
- **Sonnet + C# collapses with verbose prompts** — 17-18 point drop replicated across 2 experiments (34,560 runs). Never use kitchen-sink for Sonnet + C#
- **CoT hurts Python** — but helps Go (+5.3) and C# (+7.7)
- **Code-reviewer persona** — only beneficial role (+1.0 overall, +2.9 refactoring)
- **Polite framing** — helps JS (+2.8) only; hurts Go/C#
- **Verification redundant with persona** — standalone +3.2 JS, but zero marginal lift when stacked on persona
- **WHAT vs HOW flips by language** — JS wants HOW (+5.72), C# wants WHAT (+7.94), Python/Go neutral
- **Positive vs negative framing is noise** — original +0.66 was confounded; no significant difference (21,600 runs)
- **Persona + CoT dilutive in JS** — interaction -2.40, but synergistic in Go/C#
- **Sonnet is resistant to prompting** — max lift +1.13; Haiku +3.15, Opus +3.67
- **Python optimal stack**: code-reviewer persona + polite framing + temp 1.0 + no CoT + /init context
- **Low-baseline rule**: stack techniques when Claude's baseline is low (JS on average, Haiku+Go, Haiku+C#, hard Python tasks); keep minimal when baselines are high
- **JS optimal stack**: kitchen-sink or implementation-focused + persona + polite framing + temp 1.0
- **Blind self-review hurts, but test-feedback iteration helps low baselines** — unconditional "review and fix" follow-ups degrade quality (-0.38 two-turn, -5.09 three-turn). But injecting test results between turns helps low-baseline combos substantially: Haiku+C# +19.04, Haiku+Go +14.71 (10,748 scored). Front-loading still beats iteration for same token budget (kitchen-sink 76.77 > test-feedback 73.92)
- **Don't threaten, tip, or pressure Claude** — growth-mindset is the only positive emotional framing (+1.88). Life-or-death -3.33 (Sonnet collapses -9.2 to 65.96), tip-incentive -3.16. Consequence framing inflates tokens 69% with worse quality (15,120 runs)
- **Compressed instructions outperform verbose** — compressed rules (+3.36) beat verbose rules (+2.16) at 20% fewer tokens. Code-adapted (compress prose, preserve code markers) is the quality/cost sweet spot at 51.83 score/kTok. "Answer concisely" (2 tokens) outperforms 89-token structured caveman rules (15,120 runs)

## Running Experiments (GoCode / Direct API)

```bash
# 1. Set cert paths for mTLS auth against your OpenAI-compatible proxy
export GOCODE_CERT_PATH=~/.certificates/your-cert.crt
export GOCODE_KEY_PATH=~/.certificates/your-cert.key

# 2. Optionally override SSO/API endpoints (defaults to example.com placeholders)
export GOCODE_SSO_URL_DEV=https://your-sso.example.com/v1/secure/api/token
export GOCODE_API_URL_DEV=https://your-api-proxy.example.com/v1

# 3. Run experiment via direct API with high concurrency
claude-benchmark experiment experiments/<name>.toml --direct-api -c 50 -y
```

`-c` sets both task execution and LLM judge concurrency. Use `--judge-concurrency` to override just the judge side (e.g., `-c 50 --judge-concurrency 20`).

## Common Tasks

**Add CLI command**: Create `src/claude_benchmark/cli/commands/my_command.py`, register in `cli/main.py`, add to README table.

**Add experiment**: Create TOML in `experiments/`, smoke test with `--dry-run`, run with 30 reps, update `docs/experiments.md` findings table.

**Add task**: Run `claude-benchmark new-task`, fill in `task.toml` + `test_solution.py` + `reference.py`.

**Modify scoring**: Edit `src/claude_benchmark/scoring/composite.py`, update `docs/scoring-methodology.md`.
