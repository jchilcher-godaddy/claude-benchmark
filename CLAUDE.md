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

1. **30 reps minimum** for statistical power
2. **12+ tasks** spanning all types and difficulties
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

From 9 completed experiments (~20,000 runs):

- **Empty baseline scored 92.15** — higher than all CLAUDE.md profiles (r=-0.95 token/quality)
- **CoT hurts code quality** — every variant scored lower, especially on refactoring (-3.5 pts)
- **Code-reviewer persona** — only beneficial role (+1.0 overall, +2.9 refactoring)
- **Polite framing** — "Could you please" raises floor by +1.5 pts
- **Stacking personas backfires** — multiple roles dilute effectiveness
- **Refactoring tasks most sensitive** to prompting strategy
- **Optimal stack**: code-reviewer persona + polite framing + temp 1.0 + no CoT + clean context

## Common Tasks

**Add CLI command**: Create `src/claude_benchmark/cli/commands/my_command.py`, register in `cli/main.py`, add to README table.

**Add experiment**: Create TOML in `experiments/`, smoke test with `--dry-run`, run with 30 reps, update `docs/experiments.md` findings table.

**Add task**: Run `claude-benchmark new-task`, fill in `task.toml` + `test_solution.py` + `reference.py`.

**Modify scoring**: Edit `src/claude_benchmark/scoring/composite.py`, update `docs/scoring-methodology.md`.
