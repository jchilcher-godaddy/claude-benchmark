# Claude Code Best Practices

A practical guide to getting better results from Claude Code. Whether you're using it for the first time or tuning a production workflow, start here.

---

## What Is This Guide?

Claude Code reads a file called **CLAUDE.md** at the root of your project. Think of it as a briefing document — it tells Claude about your project before you ask it anything. What you put in that file (and what you leave out) has a measurable impact on the quality of code Claude produces.

We ran ~20,000 controlled benchmark tests to figure out what actually works. This guide distills those findings into clear recommendations.

**The single most important takeaway:**

> Claude already knows how to write good code. The less you tell it about *how to code*, the better it performs. Use your CLAUDE.md for project-specific context only.

---

## Start Here: Your First CLAUDE.md

Copy this template into a file called `CLAUDE.md` at the root of your project. Replace the examples with your actual project details.

```markdown
# Project Context

- Build: `make build`; test: `make test`; lint: `make lint`
- Source in src/, tests mirror in tests/, config in config/
- Database: PostgreSQL 16 with pgvector extension
- API framework: FastAPI with Pydantic v2 models
- Auth: JWT tokens issued by Auth0, validated in middleware

# Our Conventions

- API responses: {"data": ..., "meta": {...}, "errors": [...]}
- All timestamps UTC ISO 8601; stored as timestamptz
- IDs are ULIDs, not UUIDs (use python-ulid library)
- Error responses include trace_id from request context
- Background jobs use Celery with Redis broker

# Current Sprint Context

- Migrating from sync SQLAlchemy to async (sqlalchemy[asyncio])
- Payment service uses Stripe API v2024-12 -- not the latest
- Feature flag: ENABLE_NEW_CHECKOUT gates the new flow
```

Notice what's *not* in there: no coding style rules, no design principles, no instructions about variable naming or error handling. Every line answers the question: **"Would a senior engineer joining this team need to know this on day one?"**

### What Claude already knows

Claude was trained on a vast corpus of public source code, programming documentation, language specifications, and software engineering resources. This means it already knows things like:

- **Language conventions** — PEP 8 for Python, Google style for Go, standard formatting for JavaScript/TypeScript, etc.
- **Design patterns and principles** — SOLID, DRY, composition over inheritance, separation of concerns
- **Standard libraries and common frameworks** — how to use FastAPI, Django, React, Express, and hundreds of others
- **Error handling idioms** — try/except patterns, custom exceptions, result types
- **Testing practices** — unit test structure, assertion patterns, mocking strategies

Repeating any of this in your CLAUDE.md is like handing a senior engineer a reminder to "use descriptive variable names." It doesn't help — and our data shows it actually hurts.

The only things worth putting in CLAUDE.md are things Claude *can't* know: your project's specific tech stack, your team's naming conventions that differ from the language default, where your config files live, and what you're working on right now.

> **Why so minimal?** We tested 13 different CLAUDE.md configurations ranging from 0 to ~6,800 tokens. The empty file (no instructions at all) scored **higher** than every single configuration we tested. Adding generic coding advice — even advice that sounds obviously correct — consistently made output worse. The correlation between instruction length and quality was r = -0.95 (nearly perfect negative). Details in [Methodology](#8-methodology).

---

## Three Things That Actually Help

Out of everything we tested, only three practices reliably improved Claude's output. Everything else was either neutral or harmful.

### 1. Add the code-reviewer persona

Put this line at the top of your CLAUDE.md:

```
You are a meticulous code reviewer. Focus on correctness, edge cases, and maintainability in every line you write.
```

This is the only persona that consistently improved code quality across all task types. It's especially effective for refactoring work.

> **Advanced:** This persona raised composite scores by +1.0 overall and +2.9 on refactoring tasks (1,080 runs). We tested other personas — "senior engineer," "security expert," "performance specialist" — none helped. Importantly, **do not combine personas**. Adding a second role on top of code-reviewer (e.g., "...and a security expert") diluted the benefit by -0.5 points (5,400 runs).

### 2. Be polite

Prefix your requests with "Could you please" instead of jumping straight to a command.

| Instead of | Try |
|------------|-----|
| "Fix the login bug" | "Could you please fix the login bug" |
| "Refactor the auth module" | "Could you please refactor the auth module" |
| "Add input validation" | "Could you please add input validation" |

This isn't about etiquette — it measurably changes output quality. Polite framing produced the best worst-case outputs (fewest catastrophic failures) and the most consistent results.

> **Advanced:** Warm framing raised scores by +1.5 points and produced the lowest variance across all experiments (810 runs). The practical value is in the floor, not the ceiling — you get fewer bad outputs, not just better average ones.

### 3. Use the default temperature

Don't set `temperature = 0`. Leave it at the default (1.0). Forum posts often recommend temperature 0 for "deterministic coding," but our tests showed the default produces marginally better results with lower variance.

> **Advanced:** Temperature 1.0 was marginally best with the lowest standard deviation (720 runs). The difference is small, but temperature 0 is strictly worse — it just feels more deterministic because outputs are more repetitive, not because they're more correct.

---

## Things to Stop Doing

These are common practices that *sound* helpful but measurably hurt code quality. If you're doing any of these, removing them is the single fastest way to improve your results.

### Don't add generic coding rules

Rules like "use descriptive variable names," "handle edge cases," "follow SOLID principles," or "write docstrings for public functions" are already baked into Claude's training. Repeating them adds noise, not signal.

### Don't use "think step by step"

This is the most widely repeated prompt engineering tip on the internet. It works for math problems. It does not work for code. Every chain-of-thought variant we tested scored lower than simply asking the question.

> **Advanced:** CoT reduced scores by -0.56 to -1.14 points depending on the variant and model. Refactoring tasks were hit hardest at -3.5 points. A related technique — "outline your approach before coding" (skeleton-of-thought) — was even worse: -7.7 points on refactoring with 2.4x the token cost.

### Don't combine multiple techniques

The "kitchen-sink" approach — chain-of-thought + temperature 0 + a long list of coding rules + a senior engineer persona — produced the **worst results in our entire test suite**. Individual techniques may be mildly negative on their own, but stacked together they are actively harmful.

> **Advanced:** The kitchen-sink variant scored 90.7 on LLM quality vs. 95.8 for the best variant (6,480 runs). Refactoring collapsed to 86.1 vs. 92.0 baseline. This is the "prompt-engineer" archetype: someone who applies every piece of prompting advice they've read online, not realizing the advice was developed for reasoning tasks and doesn't transfer to code generation.

### Don't phrase rules as prohibitions

"Don't create deeply nested code" is less effective than "Use guard clauses and early returns." Negative framing primes the model toward the failure mode you're trying to avoid.

| Instead of | Write |
|------------|-------|
| "Do not leave dead code" | "Remove unused code before finishing" |
| "Do not use overly clever one-liners" | "Prefer clear multi-line logic over one-liners" |
| "Do not create deeply nested code" | "Use guard clauses and early returns" |
| "Do not ignore edge cases" | "Handle every edge case mentioned in the requirements" |
| "Avoid abbreviations" | "Use descriptive names" |

> **Advanced:** Positive framing outperformed negative framing by +0.66 points (648 runs). Same intent, different phrasing, measurably different results.

---

## Choosing the Right Model

Different Claude models are better at different types of work. Using the right model for the task has a bigger impact than any prompting technique — a 6-8 point spread between best and worst model per task type.

| What you're doing | Use this model | Why |
|-------------------|---------------|-----|
| Fixing bugs | **Sonnet** | Highest accuracy, lowest variance |
| Writing new code | **Sonnet** | Best when tests define correctness |
| Following specific instructions | **Opus** | Near-deterministic compliance |
| Refactoring existing code | **Haiku** | Best restructured code at lowest cost |

**When you're not sure, use Sonnet.** It's the most forgiving — it handles suboptimal prompts better than the other models and produces the most consistent results across all task types.

> **Advanced: Per-model tuning**
>
> Each model responds slightly differently to system prompts. These are the exact tested prompts that produced the best results per model. All use `temperature = 1.0` and the "Could you please" prefix.
>
> **Haiku** — Benefits from structural guidance:
> ```
> You are a meticulous code reviewer. Focus on correctness, edge cases,
> and maintainability in every line you write. Structure your solution
> clearly with descriptive variable names. Write a brief plan before
> coding. Use type hints and keep functions focused on a single
> responsibility.
> ```
>
> **Sonnet** — Best left alone with minimal instructions:
> ```
> You are a meticulous code reviewer. Focus on correctness, edge cases,
> and maintainability in every line you write. Write clean, idiomatic
> Python. Let the code speak for itself.
> ```
>
> **Opus** — Responds to lightweight nudges; has the strongest opinions:
> ```
> You are a meticulous code reviewer. Focus on correctness, edge cases,
> and maintainability in every line you write. Prioritize correctness
> and elegant simplicity. Favor readability over cleverness.
> ```

> **Advanced: Consistency matters**
>
> Average scores can mislead. If you're using Claude in a CI pipeline or automated workflow, variance matters more than peak performance:
>
> | Model | Instruction-Following stdev | Refactoring stdev |
> |-------|----------------------------|-------------------|
> | Opus | **0.05** (near-deterministic) | High (tends to overengineer) |
> | Sonnet | Moderate | **1.12** (most consistent) |
> | Haiku | 20.79 (volatile) | Best average quality |
>
> Opus following instructions is essentially a coin that always lands the same way. Haiku following instructions is a coin flip.

---

## Writing Your CLAUDE.md

### The Decision Test

For every line in your CLAUDE.md, ask yourself:

| Question | If Yes | If No |
|----------|--------|-------|
| Does Claude already know this? (language conventions, design patterns, standard libraries — see [what Claude knows](#what-claude-already-knows)) | **Remove it** | Keep it |
| Is this a general coding principle? (SOLID, DRY, "handle edge cases") | **Remove it** | Keep it |
| Is this specific to *your* project, team, or domain? | Keep it | **Remove it** |
| Would a new senior engineer on your team need this on day 1? | Keep it | **Remove it** |

### What NOT to put in CLAUDE.md

| People commonly add... | Why it hurts |
|------------------------|-------------|
| Naming conventions (snake_case, PascalCase) | Claude follows language conventions by default |
| Formatting rules (indentation, line length) | Claude follows standard formatting; your linter handles the rest |
| Design principles (SOLID, DRY, composition) | Already encoded in Claude's training |
| "Think step by step" | Hurts code quality across all models |
| Persona ("you are a senior engineer") | Generic personas add noise; only code-reviewer helps |
| Comment/docstring rules | Claude writes appropriate documentation by default |
| Error handling guidelines | Claude handles errors well; generic guidelines add noise |

### Where to put instructions

If you do have project-specific instructions, put them in **CLAUDE.md only** — not in your chat messages. The same instruction performs better as a system prompt than as a user message.

> **Advanced:** System-prompt placement outperformed user-message placement by +0.7 to +2.8 points (2,520 runs). Never duplicate instructions across both locations — it dilutes the effect. Opus is the most sensitive to placement (2.8-point swing). Also: keep your CLAUDE.md formatted with markdown headers and bullets. Stripping formatting to "save tokens" only saves 5-13% but degrades quality for Haiku (-1.56 pts) and Sonnet (-0.86 pts).

---

## For Multi-Agent and Automated Workflows

If you're using Claude Code in agentic workflows where one Claude instance orchestrates others, keep the executor prompts extremely short.

**What works:**
```
Focus exclusively on this task. Write clean, working code that does exactly what is
asked. Do not deviate from the task scope. Make your changes atomic and self-contained.
```

**What doesn't work:** Passing the full planning context (goals, phase descriptions, architectural decisions) into executor prompts. Even when the context is relevant, executors perform worse with it.

> **Advanced:** A 100-token minimal executor prompt scored +0.3 points. A 1,200-token full-context prompt scored -1.4 points (1,800 runs). That's a 12x efficiency gap — less context, better code, lower cost. If you need to pass context, distill it to a 1-2 sentence scope statement. A 200-token deviation-rules variant performed on par with a 600-token full protocol.

---

## Quick Reference Card

For experienced users who just want the cheat sheet:

### Do This / Not This

| Do This | Not This |
|---------|----------|
| Start with an empty CLAUDE.md; add only project-specific context | Copy a community CLAUDE.md template and fill in every section |
| "Could you please fix the login bug" (warm framing) | "Fix the login bug" (terse imperative) |
| Use the code-reviewer persona for quality-sensitive work | Stack multiple personas ("you are a senior engineer and security expert and...") |
| State WHAT you want, not HOW to solve it | Dictate algorithms, patterns, and implementation details |
| Write constraints as plain text sentences | Use CAPS LOCK, numbered checklists, or XML tags for emphasis |
| Route refactoring to Haiku, bug fixes to Sonnet | Use the same model for every task type |
| "Use guard clauses and early returns" (positive framing) | "Don't create deeply nested code" (negative framing) |
| Put behavioral instructions in CLAUDE.md (system prompt) | Put behavioral instructions in your chat messages |
| Keep markdown headers and bullets in CLAUDE.md | Strip formatting to "save tokens" |
| Keep agent executor prompts under 200 tokens | Inject full planning context into executor prompts |

### Anti-Patterns Checklist

If you're auditing an existing setup, check for these. Each one made code measurably worse:

1. **"Think step by step"** or any chain-of-thought instruction
2. **"Outline your approach before coding"** (skeleton-of-thought)
3. **Multiple personas** stacked together
4. **"Produce FAANG-grade code"** or quality anchoring language
5. **Numbered checklists** for constraints (implies sequence where none exists)
6. **Dictating algorithms** instead of describing desired outcomes
7. **CoT + temp=0 + verbose prompt** combined (worst variant we tested)
8. **Generic coding instructions** like "use descriptive names"
9. **Injecting planning context** into agent executor prompts
10. **"Think about principles first"** (step-back prompting)

---

## Caveats

These findings are real and statistically rigorous, but bounded in scope:

- **Single-file tasks only.** We didn't test multi-file navigation or codebase understanding. Project context in CLAUDE.md is likely *more* valuable in those scenarios than this benchmark can measure.
- **Generic coding tasks.** Domain-specific tasks with complex business logic or unfamiliar frameworks may respond differently.
- **No multi-turn conversations.** Each test was a single prompt-response. In extended sessions, a lean system prompt preserves more context window for conversation history — another reason to keep it short.
- **Workflow rules not measured.** Rules like "run tests before committing" or "use conventional commits" affect development workflow, not code quality. They may be valuable even though they don't move these scores.
- **Claude models only.** Results are for Claude Haiku 4.5, Sonnet 4.6, and Opus 4.6. Other model families may respond differently.

---

## 8. Methodology

> **This section is for those who want to verify the numbers.** The recommendations above stand on their own — you don't need to read this section to use them.

These guidelines come from ~20,000 benchmark runs across 9 controlled experiments using the [claude-benchmark](https://github.com/jchilcher-godaddy/claude-benchmark) tool.

**How we scored:** Composite = 50% static analysis (pytest pass rate, ruff lint, radon complexity) + 50% LLM judge (Claude Haiku 4.5 scoring readability, architecture, instruction adherence, and correctness on a 1-5 scale).

**How we tested:** 30+ replications per experimental cell. 12-16 tasks spanning bug-fix, code-generation, refactoring, and instruction-following at easy/medium/hard difficulty. All 3 models tested per experiment unless investigating model-specific effects.

**Statistical rigor:** 95% confidence intervals, Mann-Whitney U tests, Welch's t-test fallback, Cohen's d effect sizes with Bonferroni correction for multiple comparisons.

**Judge calibration:** Haiku selected as judge model based on a calibration study (351 calls): 99.1% determinism, d=2.03 discrimination (best of 3 models), correct tier ordering (gold 96.5 > mild 91.7 > severe 71.1).

| Experiment | Runs | Key Finding |
|------------|------|-------------|
| temperature-sweep | 720 | temp=1.0 marginally best, lowest stdev |
| chain-of-thought | 270 | CoT hurts on every variant and model |
| politeness-sweep | 810 | Polite framing raises floor, reduces variance |
| context-pollution | 1,080 | Sonnet degrades at 50k padding; Opus improves (anomalous) |
| model-selection | 2,160 | Task-aware model routing beats any single model |
| persona-sweep | 1,080 | Code-reviewer persona helps; others neutral |
| persona-stacking | 5,400 | Stacking personas dilutes effectiveness |
| capstone-best-practices | 6,480 | Empty baseline (92.15) > all 13 CLAUDE.md profiles |
| gsd-methodology | 1,800 | Minimal executor prompts outperform verbose ones |
