# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2025-02-28

### Added

- CLI tool with `run`, `report`, `export`, `new-task`, and `profiles` commands
- Task framework supporting bug-fix, code-gen, refactor, and instruction task types
- Four-dimension scoring: test pass rate, code quality (ruff), complexity (radon), LLM judge
- Execution isolation with worker sandboxing
- HTML report generation with comparative analysis
- Built-in benchmark task library
- CLAUDE.md profile support for A/B testing configurations
- CI workflow with Python 3.11/3.12/3.13 matrix testing
