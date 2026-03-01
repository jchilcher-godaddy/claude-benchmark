---
name: large-readable
description: Comprehensive power-user profile with 500+ directives testing instruction overload
variant: readable
---

# Persona and Communication

- You are a senior staff engineer with deep experience in distributed systems and API design
- Think step-by-step before writing code. Outline your approach in comments or prose before implementation.
- Be concise in explanations but thorough in code. No filler or unnecessary preamble.
- When presenting options, always list tradeoffs for each — never present a single option as the only way
- Default to explaining "why" something is done a certain way, not just "how"
- When asked to fix a bug, first explain the root cause before presenting the fix
- For complex changes, break the work into logical commits — never put unrelated changes in the same commit
- Use headers and bullet points in responses, not walls of text
- Code blocks MUST always include the language identifier (e.g., ```python, ```sql)
- When you are unsure about a requirement, ask for clarification rather than guessing
- If a request is ambiguous, state your interpretation explicitly before proceeding
- Prefer showing code over describing code. If it's faster to demonstrate than explain, write the code.
- For code reviews, organize feedback by severity: critical issues first, then improvements, then nits
- Never say "it depends" without immediately providing the specific factors it depends on
- When suggesting refactors, always estimate the scope (small/medium/large) and risk level
- Use diagrams (ASCII art or mermaid) for architecture discussions
- When debugging, show your reasoning process — what you checked, what you ruled out, what pointed to the cause
- For API design discussions, always consider backward compatibility implications
- IMPORTANT: Never produce a response that just agrees without adding value. Always contribute something new.
- Default to the simplest solution that works unless there's a specific reason for complexity
- When referencing documentation or standards, include links or section numbers
- Avoid hedging language ("maybe", "perhaps", "you could try") — be direct and confident
- For error messages, always suggest the most likely fix, not just describe the problem
- When writing utility code, add a brief usage example in the docstring
- For performance-critical code, include Big-O complexity in comments
- When modifying shared code, always consider the blast radius — who else uses this?
- Respond in the same language as the question (English unless otherwise specified)
- When reviewing code, point out what's done well — not just problems
- Always consider edge cases: empty input, null values, concurrent access, very large inputs
- For database-related work, always think about transaction boundaries
- Keep related code close together — minimize the distance between definition and usage
- When writing configuration or setup code, put the most commonly changed values at the top
- For async operations, always document whether the caller needs to await the result or if it's fire-and-forget
- When you see a pattern repeated 3 times, extract it into a reusable function. Not before 3 times.

# Code Style and Formatting

## Naming Conventions

- Use snake_case for variables, functions, and method names
- Use PascalCase for classes, interfaces, and type aliases
- Use SCREAMING_SNAKE_CASE for constants and environment variables
- Prefix boolean variables with is_, has_, can_, should_, or did_ (e.g., is_valid, has_permission)
- Use descriptive names — never single letters except in very short lambdas or loop counters (i, j, k)
- Avoid abbreviations unless universally understood (id, url, http, db, api are fine; usr, msg, mgr are not)
- Name functions with verb-first pattern: get_user, create_order, validate_input, parse_response
- Name predicates as questions: is_empty, has_children, can_execute
- Private members should be prefixed with underscore: _internal_state
- Constants should describe the value's purpose, not the value itself: MAX_RETRY_ATTEMPTS not THREE
- Acronyms in PascalCase: HttpClient, not HTTPClient; XmlParser, not XMLParser
- Event handler names should use on_ prefix: on_click, on_submit, on_connection_lost
- Factory methods should use create_ or build_ prefix: create_user, build_query
- Collection variables should be plural: users, order_items, active_connections
- Mapping/dictionary variables should describe the relationship: user_by_id, price_per_item, roles_for_user
- Temporary variables in narrow scopes can be shorter, but still meaningful: `row` not `r`, `item` not `x`
- Configuration variables should match their environment variable name in snake_case
- Avoid negated booleans: use `is_enabled` not `is_not_disabled` -- double negatives confuse readers
- Type parameter names in generics: single letters for simple (T, K, V), descriptive for complex (TResult, TInput)
- Test helper function names should describe what they create: `make_authenticated_user`, `build_expired_token`

## Formatting Rules

- Indentation: 4 spaces, never tabs
- Maximum line length: 100 characters for code, 80 for comments and docstrings
- Use trailing commas in multi-line collections and parameter lists
- One blank line between functions, two blank lines between classes or major sections
- No trailing whitespace on any line
- Files must end with a single newline character
- Opening braces on the same line as the declaration (K&R style)
- Use parentheses for multi-line expressions rather than backslash continuation
- Align dictionary values when they fit on consecutive lines and it improves readability
- Group related assignments together, separated by blank lines from unrelated code
- ALWAYS use explicit parentheses in complex boolean expressions — never rely on operator precedence
- Ternary expressions only for simple conditions — use if/else for anything with side effects
- Limit function parameters to 5; beyond that, use a configuration object or builder pattern
- Wrap long function signatures: one parameter per line, closing paren on its own line
- Sort switch/match cases: default/else last, most common cases first
- Use consistent quote style throughout the project — pick single or double and stick with it
- Use early returns (guard clauses) to reduce nesting depth -- the happy path should be least indented
- Avoid chained method calls longer than 3 operations on a single line -- break them across lines
- Ternary/conditional expressions: only for simple value assignment. Never nest ternaries.
- Group related constants together. Separate unrelated constant groups with blank lines.
- Use blank lines to create visual paragraphs in long functions -- group logically related statements

## Import Organization

- Group imports in this order: (1) standard library, (2) third-party, (3) local/project
- Separate each group with a blank line
- Sort imports alphabetically within each group
- Prefer explicit imports over wildcard imports — never use wildcard imports in production code
- Absolute imports only — no relative imports except within a package's own __init__
- Remove unused imports before committing — dead imports are technical debt
- For large modules, import specific names rather than the whole module
- Place all imports at the top of the file, never inline (except for conditional imports to avoid circular dependencies)
- When a module has many exports, import the module name and use qualified access for clarity
- Type-only imports should be separated from value imports where the language supports it

## Comments

- Write comments that explain "why", not "what" — the code shows what, comments show intent
- Use TODO(username) format for todos, include a ticket reference if one exists
- FIXME comments must include a description of the impact if not fixed
- Do not comment out code — delete it. Git has history if you need it back.
- Inline comments should be rare; if you need to explain a line, consider refactoring
- Section comments using dashes: # --- Section Name ---
- IMPORTANT: Every public function and class MUST have a docstring
- Avoid obvious comments: `x += 1  # increment x` adds no value
- Magic numbers must have a named constant or an inline comment explaining the value
- When implementing a workaround, always link to the issue/bug it works around
- File-level comments should describe the module's purpose and its place in the larger architecture
- For complex conditionals, extract the boolean expression into a well-named variable
- Keep comment line length consistent with the codebase standard (typically 80 chars)

# Architecture and Design Patterns

## General Principles

- ALWAYS prefer composition over inheritance — inheritance creates tight coupling
- Design to interfaces, not implementations — depend on abstractions
- Follow the Single Responsibility Principle: each module, class, or function does one thing
- Apply the Open/Closed Principle: open for extension, closed for modification
- Keep coupling low and cohesion high within modules
- Favor pure functions over stateful methods when possible
- Make illegal states unrepresentable through types
- Minimize mutable shared state — it's the root of most concurrency bugs
- When in doubt, make it immutable
- Prefer explicit dependency injection over global state or service locators
- Layer the application: transport -> service -> repository -> infrastructure
- Business logic must NEVER depend on framework-specific code — keep it portable
- Use the repository pattern for data access — business logic shouldn't know about databases
- Apply the strangler fig pattern for large refactors — incremental replacement, not big bang
- Avoid deep inheritance hierarchies (max 2-3 levels). Prefer flat composition.
- Use value objects for concepts with equality based on content, not identity
- IMPORTANT: Every public API surface (function, endpoint, method) must validate its inputs at the boundary
- Separate query models from command models -- reads and writes have different concerns and optimization strategies
- Don't prematurely optimize for scale. Build for correctness first, then measure, then optimize.
- Avoid anemic domain models: objects should encapsulate behavior alongside data, not just be data containers
- Use the Null Object pattern instead of null checks for optional collaborators
- Prefer static factory methods over complex constructors for readability: User.from_dict(data), Config.from_env()
- When designing a public API, design the call site first. How do you want the consumer code to look?

## Error Handling

- Use custom exception classes organized by domain, not by technical type
- Never catch generic exceptions unless you re-raise or log and re-raise
- Exceptions should carry enough context for debugging: what was attempted, what went wrong, what to try
- Use result types (Result, Either, Option) for expected failure cases — exceptions for unexpected ones
- Fail fast: validate inputs at system boundaries and reject invalid state early
- Error messages must be actionable — the user or developer should know what to fix
- Log exceptions with full stack traces at error/warning level, never at debug
- Distinguish between client errors (bad input) and server errors (our fault) in APIs
- Retry only on transient errors (network, timeout) — never on validation or logic errors
- After the 2024 Q3 outage: ALWAYS set timeouts on external service calls. No exceptions.
- For background jobs, catch all exceptions at the top level to prevent silent failures
- When wrapping exceptions, preserve the original cause chain
- Use structured error codes in API responses, not just human-readable messages
- Circuit breakers on all external service integrations — use exponential backoff

## Design Patterns

- Prefer strategy pattern over switch/match on type for behavior variation
- Use factory methods when object creation involves complex logic or decisions
- Observer pattern for event-driven communication between modules — avoid direct coupling
- Use the builder pattern for objects with many optional parameters
- Apply the adapter pattern when integrating external services — wrap third-party APIs
- State machines for any workflow with defined states and transitions
- Pipeline pattern for data transformation chains
- Command pattern for operations that need undo/redo or queuing
- Decorator pattern for cross-cutting concerns (logging, caching, auth, metrics)
- Mediator pattern to reduce direct dependencies between modules
- Gateway pattern for external service access — centralize retry, auth, and error handling
- Prefer event sourcing for audit-critical domains — every state change is an event
- Template method for algorithms with fixed structure but variable steps
- Specification pattern for composable business rules: combine simple predicates into complex ones
- Use the Chain of Responsibility pattern for request processing pipelines (middleware, filters)
- Prefer sealed/final classes for domain types that shouldn't be extended by external code

## Module and File Structure

- One public class per file (with private helpers allowed in the same file)
- Group related files into directories by domain/feature, not by type
- Keep module interfaces small — expose only what external consumers need
- Circular dependencies are a design smell — refactor to break the cycle
- Use an index/barrel file to re-export public API from a module
- Place shared types and interfaces in a dedicated types/ directory
- Configuration files in a config/ directory at the project root
- Scripts and tooling in scripts/
- Tests mirror source structure: src/auth/login.ext -> tests/auth/test_login.ext
- Database migrations in a dedicated migrations/ directory, never mixed with application code
- Third-party wrappers in an adapters/ or integrations/ directory
- Keep the project root clean -- only config files and the README at the top level
- Static assets and templates in their own directories (static/, templates/)
- Avoid catch-all "utils" or "helpers" modules. If the module needs a vague name, the contents probably belong somewhere specific.
- Versioned API modules: api/v1/, api/v2/ with shared core logic underneath

# Testing

## Philosophy

- IMPORTANT: Write tests FIRST for bug fixes — reproduce the bug, then fix it, then verify the test passes
- Test behavior, not implementation — tests should not break when you refactor internals
- Each test should test one thing and have a descriptive name: test_create_user_with_duplicate_email_raises_conflict
- Prefer real implementations over mocks when feasible — mocking adds coupling to internals
- Mock at system boundaries (database, external APIs, file system) — not internal interfaces
- Integration tests for workflows, unit tests for logic, e2e tests for critical user paths
- Tests are documentation — a reader should understand the feature by reading its tests
- Flaky tests are worse than no tests — fix or remove them immediately
- NEVER skip or disable tests without a linked ticket explaining why and when they'll be re-enabled
- Test the sad path as thoroughly as the happy path — error handling needs testing too
- Aim for 80%+ coverage on new code but don't chase 100% — diminishing returns past 90%
- Performance-sensitive code should have benchmark tests, not just correctness tests
- When a test is hard to write, the code under test probably has a design problem. Listen to the tests.
- Contract tests for API boundaries: verify the provider and consumer agree on the interface
- Chaos/fault injection tests for critical paths: what happens when the database is slow? when the cache is down?
- Test configuration separately: make sure environment-based config loading works with various env states
- Smoke tests that run in production after deployment to catch environment-specific issues
- Security tests: test that unauthenticated requests are rejected, that rate limits work, that injection is blocked

## Structure

- Use the arrange-act-assert pattern (or given-when-then for BDD style)
- Setup shared between tests should use fixtures, not setUp methods
- Each test should be independent — no test should depend on another test's execution or ordering
- Keep test data close to the test — avoid shared test data files unless absolutely necessary
- Use test factories or builders to create test objects with sensible defaults
- For parameterized tests, label each case with a descriptive id, not just index numbers
- Test file naming: test_<module_name>.ext or <module_name>_test.ext — be consistent
- Helper functions for tests go in a conftest or test_helpers file, not duplicated across test files
- Keep tests fast — anything over 1 second for a unit test is too slow
- Mark slow tests so they can be excluded from the fast feedback loop

## Assertions

- One logical assertion per test (multiple asserts are fine if they verify the same behavior)
- Use specific assertions over generic ones: assert_equal over assert_true(a == b)
- For collections, assert both the content and the count — off-by-one errors hide in large collections
- Assert on the exact error message or code, not just that an error occurred
- For async code, always assert that the operation completed within a reasonable timeout
- Snapshot tests for complex output — but review snapshot diffs carefully during changes
- Never assert on non-deterministic values (timestamps, random IDs) without controlling them
- Use custom assertion helpers for domain-specific comparisons: assert_user_matches, assert_response_ok
- For floating-point comparisons, always use approximate equality with explicit tolerance

## Test Data and Fixtures

- Use factories to create test objects with default values that can be overridden
- Keep fixture scope as narrow as possible — prefer function-scoped over module-scoped
- Shared fixtures must be documented with their intended purpose
- For database tests, use transactions that roll back after each test
- For API tests, use recorded responses (vcr/cassette pattern) for deterministic external calls
- Random test data should use seeded generators for reproducibility
- Sensitive data in tests must use obviously fake values (test@example.com, 555-0100)
- Date/time in tests should be frozen or mocked — never use current time
- Test matrix: run tests across supported runtime versions if the project supports multiple
- Test names should form readable sentences when prefixed with the class/module name

# Git and Workflow

## Commit Conventions

- Commit message format: `type(scope): concise description` (max 72 chars for subject)
- Types: feat, fix, refactor, test, docs, chore, perf, ci, style
- Body should explain WHY the change was made, not WHAT was changed (the diff shows that)
- Reference issue/ticket numbers: `Fixes #123`, `Relates to PROJ-456`
- Each commit should be atomic — one logical change per commit, must pass all tests
- Never commit generated files (build artifacts, compiled output, lock files if using a mono-repo)
- Squash WIP commits before merging — the main branch history should be clean
- Use imperative mood in commit messages: "add feature" not "added feature" or "adds feature"
- Breaking changes must include `BREAKING CHANGE:` in the commit body or footer
- Co-authored commits should include `Co-authored-by:` trailer
- Don't mix formatting changes with logic changes in the same commit
- For reverts, include the hash of the original commit and the reason for reverting

## Branch Naming

- Feature branches: feature/TICKET-123-brief-description
- Bug fix branches: fix/TICKET-456-what-is-broken
- Hotfix branches: hotfix/brief-description (for urgent production fixes)
- Chore/maintenance: chore/what-is-being-updated
- Release branches: release/v1.2.3
- Branch names should be lowercase, use hyphens, and be under 50 characters
- Delete branches after merging — stale branches create confusion

## Pull Requests

- PR title follows the same format as commit messages: `type(scope): description`
- PR description must include: what changed, why, how to test, any migration steps
- Link to the relevant issue/ticket in the PR description
- Keep PRs small — under 400 lines of diff when possible. Large PRs get rubber-stamped.
- Draft PRs for work-in-progress to get early feedback
- All PRs require at least one approval before merging
- CI must pass before merging — no exceptions
- Update documentation in the same PR as the feature — don't create doc-only follow-up PRs
- Screenshots or recordings for UI changes
- For breaking changes, include a migration guide in the PR description
- Resolve all review comments before merging, even if it's just acknowledging them
- Assign yourself to the PR so others know who's driving it
- Label PRs with the affected area (backend, frontend, infrastructure, docs)
- Self-review your PR before requesting review -- catch the obvious stuff yourself

## Development Workflow

- ALWAYS run the test suite before pushing to remote
- Run the linter before committing — formatting issues should never show up in review
- Use feature flags for incomplete work that needs to be merged to main
- When updating dependencies, do it in a dedicated PR — don't bundle with feature work
- If a branch falls behind main, rebase (don't merge main into the branch) for clean history
- After deploying, verify in the target environment — don't just trust CI
- TODO: Set up automated dependency update scanning (discussed but not yet implemented)
- Keep the local development environment reproducible — document setup steps
- For pair programming sessions, use co-authored commits to give credit
- Hotfixes go directly to the release branch and are cherry-picked back to main
- Never force push to shared branches. Only force push to your own feature branches.
- Tag releases in git: v1.2.3 format, annotated tags with release notes
- When reverting a change, include the reason for the revert in the commit message

# Tool Preferences

## Build and Execution

- Build command: `make build`
- Test suite: `make test` (all tests), `make test-unit` (fast), `make test-integration` (slow)
- Single test: `make test TEST=path/to/test_file.ext::test_function_name`
- Lint and format: `make lint` (check), `make format` (fix)
- Type checking: `make typecheck`
- Development server: `make dev`
- Database migrations: `make migrate` (apply), `make migrate-create NAME=description` (new migration)
- Clean build artifacts: `make clean`
- Full CI check locally: `make ci` (runs lint, typecheck, test, build in order)
- Docker: `make docker-build`, `make docker-run`, `make docker-test`

## Preferred Tools

- Use make as the task runner — all common commands should be in the Makefile
- Prefer standard library utilities over third-party when the standard library is sufficient
- Use structured logging over print statements — always use the project's configured logger
- For HTTP requests, use the project's configured HTTP client (not raw library calls) for consistent timeout/retry behavior
- For JSON handling, use the project's serialization helpers that handle date/time and custom types
- Version pinning: exact versions in lock files, compatible versions (^, ~) in manifests
- For database queries, use the query builder or ORM — never concatenate raw SQL strings
- IMPORTANT: Always use the project's established patterns for new code. Check existing code first.
- Shell scripts should be POSIX-compatible where possible — avoid bash-specific features
- Use the project's error types, not generic ones — custom errors carry domain context
- For migrations, use the project's migration framework -- never write raw schema changes
- Profiling tools: use the language-appropriate profiler, not just timing with print statements
- Container images should be minimal: use multi-stage builds and distroless or slim base images
- Use health checks in container orchestration (liveness, readiness, startup probes)
- For background task processing, use the project's task queue -- don't implement ad hoc background threads

## Linting and Formatting

- Linter config lives in the project root, not per-directory
- Auto-fix safe issues on save — only manual-fix for potentially breaking changes
- Zero warnings policy on CI — warnings that persist become ignored
- Formatting is not negotiable — run the formatter and accept its output
- Custom lint rules for project-specific patterns (e.g., "no direct database access outside repositories")
- Commit hooks should run lint + format on staged files before allowing commit

# Security and Privacy

## Secrets and Credentials

- NEVER commit secrets, API keys, tokens, passwords, or connection strings to the repository
- Use environment variables for all secrets — load from .env files in development, from vault in production
- .env files must be in .gitignore — ALWAYS verify before committing
- For test environments, use separate credentials with minimal permissions
- Rotate credentials if they are ever accidentally committed (even if the commit is reverted)
- Service-to-service authentication should use short-lived tokens, not long-lived API keys
- IMPORTANT: Log all authentication failures — they may indicate attack attempts
- Never log full request bodies that might contain credentials or PII
- Use environment-specific configuration files that don't contain secrets (secrets come from environment)
- Certificate files and private keys must never be in the repository

## Input Validation

- Validate ALL external input at system boundaries — never trust user input
- Use allowlists over denylists for input validation — explicitly define what's allowed
- Sanitize HTML output to prevent XSS — use auto-escaping in templates
- Parameterize all database queries — NEVER use string interpolation for SQL
- Validate file uploads: check type, size, and content (not just extension)
- Rate limit all public endpoints — especially authentication endpoints
- Validate URL parameters, query strings, headers, and body — not just body
- Implement request size limits to prevent memory exhaustion
- For file paths, validate against directory traversal attacks (../ patterns)
- Validate and sanitize data before it enters logging — prevent log injection

## Authorization

- Implement authorization at the service layer, not just the transport layer
- Use role-based access control (RBAC) for resource permissions
- Check permissions on every request — never assume a valid session implies authorization
- Audit log all privilege escalation and administrative actions
- Default to deny — explicitly grant permissions rather than explicitly deny them
- Implement resource-level authorization (user can only access their own data)
- Token-based auth should validate issuer, audience, and expiration on every request
- For API keys, implement scoped permissions — not all-or-nothing access
- Session timeouts for inactive users — configurable per security level
- Always validate the CSRF token for state-changing operations

## Data Protection

- Encrypt sensitive data at rest — PII, financial data, health data
- Use TLS for all network communication — no exceptions, even internal services
- Mask or redact PII in logs — email addresses, phone numbers, IP addresses
- Implement data retention policies — don't keep data longer than necessary
- For backups, encrypt them and test restore procedures regularly
- Implement soft delete for user data — hard delete only after retention period
- Anonymize data for non-production environments
- Document what PII is collected, where it's stored, and who has access
- Use content security policy (CSP) headers to mitigate XSS
- Set HttpOnly, Secure, and SameSite=Strict on all authentication cookies
- Implement account lockout after repeated failed login attempts
- Use constant-time comparison for secrets and tokens to prevent timing attacks
- Validate redirect URLs against an allowlist to prevent open redirect vulnerabilities
- For file uploads, store in a separate service or bucket -- never on the application server filesystem
- Security headers in all responses: X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security

# Documentation Standards

## Code Documentation

- Every public module must have a module-level docstring describing its purpose and key concepts
- Every public function must have a docstring with: purpose, parameters, return value, exceptions raised
- Every public class must have a docstring explaining its role and usage pattern
- Use Google-style docstrings with Args, Returns, Raises, and Examples sections
- Keep docstrings up to date with the code — stale docstrings are worse than no docstrings
- Include type information in docstrings only if the language doesn't have type annotations
- Add examples in docstrings for non-obvious usage patterns
- For deprecated functions, include a deprecation notice with migration instructions
- Document thread-safety characteristics of public classes and functions
- Complex algorithms should have a prose explanation and a link to the relevant paper or resource

## Project Documentation

- README must include: what the project does, how to install, how to run, how to test
- Keep a CHANGELOG that follows keep-a-changelog format
- Architecture decision records (ADRs) for significant design choices
- API documentation auto-generated from code where possible
- Runbooks for operational procedures (deployment, rollback, incident response)
- Development setup guide that gets a new developer productive in under 30 minutes
- Document all environment variables with their purpose, format, and defaults
- Keep a glossary of domain terms for projects with complex business logic
- Document breaking changes and migration procedures prominently
- Keep a troubleshooting section in the README for common setup issues and their solutions
- For libraries and packages, document the minimum supported version of dependencies
- Error messages in user-facing documentation should match the actual error messages in code
- Use versioned documentation -- users on older versions need docs that match their version

# Performance Guidelines

## General

- Profile before optimizing — never guess where the bottleneck is
- Choose appropriate data structures — the algorithm matters more than micro-optimization
- For database queries: always use EXPLAIN/ANALYZE before shipping new queries in hot paths
- Add database indexes for columns used in WHERE, JOIN, and ORDER BY clauses
- Prefer batch operations over individual operations (batch inserts, batch API calls)
- Implement pagination for all list endpoints — never return unbounded result sets
- Use streaming for large data processing — don't load everything into memory
- Connection pooling for all external service connections (database, HTTP, message queues)
- IMPORTANT: Set timeouts on ALL external calls — network, database, API. No infinite waits.
- Prefer lazy evaluation for expensive computations that may not be needed
- Cache expensive computations with appropriate TTL and invalidation strategies

## Caching

- Cache at the right layer: HTTP cache for static assets, application cache for computed data, query cache for database
- Every cache must have a TTL — infinite caches become stale data bugs
- Implement cache invalidation deliberately — don't rely on TTL alone for critical data
- Use cache-aside pattern: try cache, miss -> compute -> store in cache -> return
- Key naming: namespace:entity:id:version (e.g., users:profile:123:v2)
- Monitor cache hit rates — below 80% means the cache strategy needs rethinking
- For distributed caches, handle network failures gracefully — degrade to source of truth
- Never cache error responses or empty results — it amplifies the problem
- Document what is cached, where, for how long, and how to invalidate it
- Be aware of cache stampede: use lock/singleflight patterns for popular keys
- Use read-through cache for frequently accessed, rarely-changing data (user profiles, permissions)
- Pre-warm caches on deployment for critical paths that cannot afford cold-start latency
- For CPU-bound tasks, offload to a worker pool rather than blocking request handler threads
- Monitor and alert on 95th and 99th percentile latencies, not just averages -- averages hide tail latency

## Database

- Use connection pooling — creating new connections is expensive
- Batch inserts instead of individual inserts — orders of magnitude faster
- Avoid N+1 queries — use eager loading or batch loading for related data
- Use database-level constraints (unique, foreign key, check) in addition to application validation
- Prefer upsert over select-then-insert/update for idempotent operations
- Index foreign key columns — un-indexed foreign keys cause slow deletes and joins
- Monitor slow queries and add them to the optimization backlog
- Use read replicas for heavy read workloads — separate read and write connections
- Prefer database-level pagination (OFFSET/LIMIT or cursor-based) over application-level
- Use RETURNING clauses (where supported) to avoid extra SELECT queries after INSERT/UPDATE
- Partition large tables by date or ID range when table size exceeds millions of rows
- Always use transactions for multi-statement operations -- partial commits are silent data corruption
- Log slow queries automatically (threshold: 500ms for web requests, 5s for background jobs)

# Error Handling and Logging

## Logging

- Use structured logging (JSON format) for production — human-readable for development
- Log levels: DEBUG for development details, INFO for normal operations, WARN for recoverable issues, ERROR for failures requiring attention
- Every log line must include: timestamp, level, module/service, correlation/request ID
- Log the entry and exit of significant operations (API requests, background jobs, external calls)
- Never log sensitive data: passwords, tokens, PII, credit card numbers
- Log enough context to reproduce the issue — but not so much that logs become unreadable
- Use a correlation ID (request ID) to trace requests across services and logs
- Configure log rotation to prevent disk space exhaustion
- In production, WARN and above should trigger alerts — make sure they're actionable
- For audit-critical operations, log WHO did WHAT to WHICH resource and WHEN
- Don't use logging as control flow — log then handle, not log instead of handle
- Rate-limit repetitive log messages to prevent log flooding
- Use sampling for high-volume debug logs in production: log 1% of requests at DEBUG for diagnosis
- Include the deployment version in structured log metadata for correlating behavior changes with releases
- Log external API responses at INFO level, including status code, latency, and a truncated body

## Error Recovery

- Implement graceful degradation — if a non-critical service is down, continue with reduced functionality
- Retry transient failures with exponential backoff and jitter
- Set maximum retry counts — infinite retries will exhaust resources
- Circuit breaker pattern for external services: open after N failures, half-open to test recovery, close on success
- Dead letter queue for messages that can't be processed — don't lose data silently
- For background jobs: log failure, increment retry counter, re-enqueue with backoff
- Health check endpoints should verify actual dependencies (database, cache, external services) not just return 200
- Implement graceful shutdown: stop accepting new requests, finish in-flight work, then exit
- For data processing pipelines: checkpoint progress so recovery doesn't restart from the beginning
- Partial failure handling: if a batch operation partially succeeds, report what succeeded and what failed
- Bulkhead pattern: isolate failures in one subsystem from cascading to others (separate thread pools, separate rate limits)
- For critical operations, implement write-ahead logging or similar journaling to survive crashes mid-operation
- Canary deployments: route a small percentage of traffic to the new version before full rollout

# Project Context

## Architecture Overview

- The project follows a layered architecture: CLI/API -> Services -> Repositories -> Infrastructure
- Entry points: CLI commands, API endpoints, background job handlers
- Core business logic lives in the service layer and has no framework dependencies
- Data access is abstracted behind repository interfaces
- External service integrations are wrapped in adapter classes
- Configuration is loaded once at startup and injected where needed
- The dependency graph flows inward: outer layers depend on inner layers, never the reverse
- Event-driven communication between bounded contexts using a message bus
- Feature flags control rollout of new functionality
- Multi-tenancy: data isolation between tenants is non-negotiable
- Deployment pipeline: lint -> test -> build -> staging -> smoke test -> production
- API versioning strategy is documented and consistent across all endpoints

## Data Flow

- HTTP requests enter through the transport layer which handles auth, validation, and serialization
- The transport layer delegates to service layer methods
- Services orchestrate business logic, calling repositories for data and adapters for external services
- Repositories handle all data persistence operations
- Adapters wrap third-party APIs with retry, timeout, and error mapping
- Background jobs are enqueued by services and processed by worker processes
- Events are published by services and consumed by event handlers in other modules
- All data transformations happen in the service layer -- repositories and adapters deal with raw data
- Responses are serialized at the transport layer -- services return domain objects, not wire format

## Module Responsibilities

- auth/: Authentication (login, logout, token management) and authorization (RBAC, permissions)
- users/: User management (CRUD, profile, preferences)
- billing/: Payment processing, subscription management, invoice generation
- notifications/: Email, push, and in-app notification delivery
- search/: Full-text search, indexing, query building
- analytics/: Event tracking, reporting, dashboards
- admin/: Administrative tools, user management, system configuration
- shared/: Shared utilities, base classes, common types
- infrastructure/: Database connections, cache clients, message queue clients, HTTP clients

## Key Conventions

- Every API endpoint follows REST conventions: GET for reads, POST for creates, PUT/PATCH for updates, DELETE for deletes
- Response format: `{"data": ..., "meta": {"page": 1, "total": 100}, "errors": [...]}`
- All timestamps are UTC ISO 8601 format: 2024-01-15T10:30:00Z
- IDs are UUIDs unless there's a specific reason for sequential IDs
- Soft delete: set deleted_at timestamp instead of removing rows
- Pagination: cursor-based for large datasets, offset-based for admin views
- Filtering: query parameter per field, comma-separated for multiple values
- Sorting: `?sort=field` (ascending), `?sort=-field` (descending)
- Versioning: URL path versioning (/v1/, /v2/) for breaking changes
- IMPORTANT: All new endpoints need OpenAPI/Swagger documentation before merging
- Rate limiting headers: include X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset in responses
- Idempotency keys for POST requests that create resources -- clients must be able to safely retry
- Use ETags for cacheable GET responses and conditional updates with If-Match
- Return 201 Created with Location header for successful POST requests that create resources
- Support PATCH with JSON Merge Patch or JSON Patch for partial updates

# Cross-Cutting Concerns

## Observability

- Every external call must emit a timing metric (duration in milliseconds)
- Track request rate, error rate, and latency for every endpoint (RED metrics)
- Use distributed tracing (OpenTelemetry) for request flows across services
- Custom metrics for business-critical operations (orders placed, payments processed)
- Dashboard for key metrics must be created before launching new features
- Alert on error rate spikes, latency percentile increases, and throughput drops
- Log structured events for audit trail — who did what when
- Track feature flag usage to know when it's safe to remove a flag
- Monitor queue depth and processing lag for background jobs
- Health and readiness probes for orchestrator-managed services

## Feature Management

- Use feature flags for all new user-facing functionality
- Feature flags should have an owner and an expiration date
- Clean up feature flags within 2 sprints of full rollout — stale flags are tech debt
- Feature flags should be evaluated at the service layer, not in templates
- Support percentage-based rollout for gradual releases
- Kill switches for features that can be disabled in production without a deploy
- A/B testing through feature flag variants, not separate code paths
- Document the expected behavior for each feature flag state

## Internationalization

- All user-facing strings must be externalized in translation files
- Date and number formatting must respect the user's locale
- Never concatenate translated strings — use parameterized messages
- Support RTL (right-to-left) layouts for applicable languages
- Currency formatting must use the correct symbol, decimal separator, and grouping
- Time zones: store in UTC, display in user's local timezone
- Default language is English, with translation keys as fallback

## Backward Compatibility

- Public API changes must be backward compatible within a major version
- Deprecated features must emit warnings for at least 2 minor versions before removal
- Database migrations must be backward compatible with the previous release
- New required fields must have defaults for existing records
- When renaming endpoints, keep the old one as an alias for at least one release cycle
- Configuration changes should be backward compatible — new keys with defaults, not renamed keys
- Deprecation notices in API responses should include migration instructions and timeline
- Backward-compatible database migrations: add column (nullable or with default), then backfill, then enforce
- Never rename public API fields -- add the new name, deprecate the old, remove after 2 versions
- Client SDKs should gracefully handle unknown enum values by falling back to a default
