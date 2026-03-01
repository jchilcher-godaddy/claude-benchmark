# Contributing to claude-benchmark

## Development Setup

```bash
git clone https://github.com/jchilcher/claude-benchmark.git
cd claude-benchmark
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running Tests

```bash
pytest
```

All tests use mocks and do not require an API key.

## Linting

```bash
ruff check src/
```

Configuration: line-length 100, target Python 3.11 (see `pyproject.toml`).

## Creating New Benchmark Tasks

Use the scaffolding command:

```bash
claude-benchmark new-task
```

Or create a task directory manually under `tasks/`. Each task needs a `task.toml` file defining the task metadata. The required files depend on the task type:

| Task Type | Required Files |
|-----------|---------------|
| bug-fix | `task.toml`, `starter.py`, `test_solution.py`, `reference.py` |
| code-gen | `task.toml`, `test_solution.py`, `reference.py` |
| refactor | `task.toml`, `starter.py`, `test_solution.py`, `reference.py` |
| instruction | `task.toml`, `test_solution.py`, `reference.py`, optionally `claudemd_rules.toml` |

### task.toml format

```toml
name = "my-task-01"
task_type = "bug-fix"        # bug-fix | code-gen | refactor | instruction
difficulty = "easy"          # easy | medium | hard
size = "function"            # function | module
description = "Brief description of the task"
prompt = """The prompt given to the AI."""

prompt_rules = [
    "Rule 1",
    "Rule 2",
]

expected_files = ["solution.py"]
tags = ["tag1", "tag2"]

[scoring]
test_file = "test_solution.py"
ruff_rules = []
```

### File descriptions

- **task.toml** -- Task metadata, prompt, scoring config
- **starter.py** -- Initial code provided to the AI (bug-fix, refactor)
- **test_solution.py** -- Test suite run against the AI's output
- **reference.py** -- Known-good implementation for comparison scoring
- **claudemd_rules.toml** -- Simulated CLAUDE.md rules (instruction tasks)

## Pull Requests

1. Fork the repository
2. Create a feature branch
3. Ensure `ruff check src/` passes with no errors
4. Ensure `pytest` passes
5. Submit a pull request
