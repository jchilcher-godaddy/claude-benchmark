---
name: typical-readable
description: Typical community CLAUDE.md profile — build commands, code style, architecture, workflow
variant: readable
---

# Build and Test Commands

- Build the project: `make build`
- Run all tests: `make test`
- Run a single test file: `make test TEST=path/to/test_file::test_name`
- Run the linter (check only): `make lint`
- Auto-format code: `make format`
- Type checking: `make typecheck`
- Quick iteration cycle (lint + typecheck + unit tests): `make check`
- Start the development server: `make dev`
- IMPORTANT: Always run `make check` before committing.

# Code Style

## Naming

- Variables and functions: snake_case
- Classes and type aliases: PascalCase
- Constants: SCREAMING_SNAKE_CASE
- Boolean variables should start with is_, has_, can_, or should_
- Use descriptive names — avoid abbreviations except common ones (id, url, db, api)
- Functions should start with a verb: get_user, create_order, validate_input
- Private members: prefix with underscore (_internal_helper)
- Collection variables should be plural: users, order_items

## Formatting

- Indent with 4 spaces, never tabs
- Maximum line length: 100 characters
- Use trailing commas in multi-line collections and parameter lists
- One blank line between functions, two blank lines between classes
- Files must end with a single newline
- Remove unused imports before committing

## Comments and Documentation

- Comments should explain "why", not "what" — the code shows what happens
- Every public function and class MUST have a docstring
- Use TODO(username) format with a ticket reference when possible
- Do not comment out code — delete it. Version control has the history.
- Magic numbers must be named constants or have an explanatory comment

# Architecture Overview

- Source code lives in `src/`, tests in `tests/`, scripts in `scripts/`
- Tests mirror the source structure: `src/auth/login` -> `tests/auth/test_login`
- Group files by feature or domain, not by type (don't put all models in one directory)
- Keep module interfaces small — only expose what external consumers need
- Business logic belongs in the service layer and should not depend on framework code
- Data access goes through repository interfaces — no direct database calls in services
- New features should follow existing patterns — check similar modules before creating something new
- Configuration files belong in the project root or a config/ directory

# Workflow and Git Conventions

- Commit message format: `type(scope): short description` (max 72 characters)
- Allowed types: feat, fix, refactor, test, docs, chore
- Commit body should explain WHY the change was made, not what changed
- Branch naming: feature/TICKET-123-brief-description or fix/TICKET-456-what-broken
- Keep pull requests small — under 400 lines of diff when possible
- All PRs require at least one approval and passing CI before merge
- Write tests for bug fixes: reproduce the bug in a test first, then fix it
- ALWAYS run the full test suite before pushing
- Don't mix formatting changes with logic changes in the same commit
- Update documentation in the same PR as the feature, not in a follow-up
