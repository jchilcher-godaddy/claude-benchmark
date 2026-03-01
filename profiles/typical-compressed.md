---
name: typical-compressed
description: Token-optimized version of typical-readable profile — same semantics, aggressive shorthand
variant: compressed
compressed_from: typical-readable.md
---

# Build/Test
- Build: `make build`
- All tests: `make test`
- Single test: `make test TEST=path::test_name`
- Lint: `make lint`; format: `make format`
- Typecheck: `make typecheck`
- Quick check (lint+typecheck+unit): `make check`
- Dev server: `make dev`
- IMPORTANT: Run `make check` before commit

# Style
- snake_case vars/fns, PascalCase classes, SCREAMING_SNAKE_CASE consts
- Bool prefix: is_/has_/can_/should_
- Descriptive names; no abbrevs except id,url,db,api
- Verb-first fns: get_user, create_order
- Private: _prefix; collections: plural
- 4-space indent, 100 char lines, trailing commas multiline
- 1 blank between fns, 2 between classes; newline at EOF
- Remove unused imports before commit
- Comments explain "why" not "what"
- All public fns/classes MUST have docstrings
- TODO(user) w/ ticket ref; never comment out code
- Named consts for magic numbers

# Architecture
- src/ for code, tests/ mirrors src structure, scripts/ for tooling
- Group by feature/domain not type
- Small module interfaces; expose only needed
- Biz logic in service layer, no framework deps
- Data access via repo interfaces, no direct DB in services
- Follow existing patterns; check similar modules first
- Config in project root or config/ dir

# Workflow
- Commits: type(scope): desc (72 char max)
- Types: feat,fix,refactor,test,docs,chore
- Body: explain WHY not WHAT; ref tickets
- Branches: feature/TICKET-123-desc or fix/TICKET-456-desc
- PRs <400 lines diff; 1+ approval + CI pass required
- Bug fixes: write failing test first, then fix
- ALWAYS run full tests before push
- Don't mix formatting + logic commits; docs in same PR as feature
