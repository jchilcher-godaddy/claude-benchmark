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
| `report` | Generate an HTML report from one or more result sets |
| `export` | Export raw results data as JSON |
| `new-task` | Scaffold a new benchmark task |
| `profiles` | List available benchmark profiles |

## Scoring

Each task is scored across four dimensions:

| Dimension | Weight | Method |
|-----------|--------|--------|
| Test pass rate | 40% | pytest against task-specific test suite |
| Code quality | 20% | ruff lint rule compliance |
| Complexity | 20% | radon cyclomatic complexity analysis |
| LLM judge | 20% | Claude evaluation of code quality and instruction adherence |

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
