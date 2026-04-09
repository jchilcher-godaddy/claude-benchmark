# claude-benchmark

![CI](https://github.com/jchilcher/claude-benchmark/actions/workflows/ci.yml/badge.svg)

A CLI tool for benchmarking CLAUDE.md configurations against standardized coding tasks. Test how well your CLAUDE.md instructions guide AI code generation across bug fixes, code generation, refactoring, and instruction-following scenarios.

## Prerequisites

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and configured
- `ANTHROPIC_API_KEY` environment variable set

## Installation

```bash
pip install .
```

For development:

```bash
pip install -e .
```

## Quick Start

Run a benchmark against your CLAUDE.md file:

```bash
claude-benchmark run --claudemd path/to/your/CLAUDE.md
```

Generate a report from results:

```bash
claude-benchmark report results/
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `run` | Execute benchmark tasks against a CLAUDE.md configuration |
| `experiment` | Run a multi-variant experiment from a TOML configuration file |
| `report` | Generate an HTML report from one or more result sets |
| `compare` | Compare results across cataloged runs with statistical analysis |
| `rescore` | Re-run scoring on existing results (e.g., after judge recalibration) |
| `calibrate` | Calibrate and compare LLM judge models |
| `catalog` | View and filter the catalog of completed benchmark runs |
| `intake` | Import external benchmark results into the catalog |
| `export` | Export raw results data as JSON |
| `new-task` | Scaffold a new benchmark task |
| `profiles` | List available benchmark profiles |

## Scoring

Each task receives a **composite score (0-100)** combining automated static analysis with LLM-as-judge evaluation:

```
composite = (static_score x 0.50) + (llm_score x 0.50)
```

**Static analysis** (50% of composite) combines three sub-scores:

| Sub-score | Weight | Method |
|-----------|--------|--------|
| Test pass rate | 50% of static | pytest against task-specific test suite |
| Lint cleanliness | 30% of static | ruff lint violations per LOC |
| Cyclomatic complexity | 20% of static | radon complexity analysis |

**LLM judge** (50% of composite) evaluates code readability, architecture quality, instruction adherence, and correctness reasoning on a 1-5 scale.

See [docs/scoring-methodology.md](docs/scoring-methodology.md) for detailed formulas and [docs/judge-selection.md](docs/judge-selection.md) for judge calibration data.

## Task Types

- **bug-fix** -- Diagnose and fix bugs in provided starter code
- **code-gen** -- Generate code from scratch given a specification
- **refactor** -- Improve existing code while preserving behavior
- **instruction** -- Follow specific coding rules from both prompt and CLAUDE.md

See `examples/` for sample CLAUDE.md files to get started.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and how to create new benchmark tasks.

## License

Apache 2.0. See [LICENSE](LICENSE).
