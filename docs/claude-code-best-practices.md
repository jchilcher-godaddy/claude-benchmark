# Claude Code Best Practices

A practical guide to getting better results from Claude Code. Whether you're using it for the first time or tuning a production workflow, start here.

---

## What Is This Guide?

Claude Code reads a file called **CLAUDE.md** at the root of your project. Think of it as a briefing document — it tells Claude about your project before you ask it anything. What you put in that file (and what you leave out) has a measurable impact on the quality of code Claude produces.

We ran ~231,000+ controlled benchmark tests across Python, Go, JavaScript, and C# to figure out what actually works. This guide distills those findings into clear recommendations.

> **Cross-language status (75,400+ runs including regression analysis):** Tested across Python, Go, JavaScript, and C#. Core findings (empty baselines win for Python, code-reviewer persona helps) hold. Key divergences: **CoT helps Go (+5.3) and C# (+7.7)** instead of hurting; **polite framing only helps JS (+2.8)** and hurts Go/C#; **kitchen-sink helps most where baselines are low** (+7.25 JS, where bare is only 67.40; also Haiku+Go, Haiku+C#, and hard Python tasks); **"state WHAT not HOW" flips by language** (HOW wins JS by +5.7, WHAT wins C# by +7.9); **positive vs negative framing is noise** (+0.07 in Python, n.s. everywhere); **C# kitchen-sink underperformance is prompt contamination AND over-specificity** — language-specific C# rules also hurt (-1.68 vs bare), but language-agnostic phrasing helps (+5.51); **for multi-language repos, use universal phrasing** ("follow the target language's conventions") rather than language-specific rules (12,960 runs). A regression analysis (21,600 runs) found that bare baseline score predicts kitchen-sink lift at -0.647 pts per +1 bare point -- low baselines respond to prompting regardless of language. **New (18,720 runs):** Verbosity r=-0.95 was Python-specific content, not verbosity per se — language-neutral instructions show flat/positive correlations (JS r=+0.15, 8,640 runs). Doc brevity confirmed cross-language: 15-32% token reduction, quality neutral/positive (6,480 runs). Haiku+persona is Python-only: Go -31.5, C# -32.6 vs Opus (3,600 runs). See individual sections for language-specific guidance.

**The single most important takeaway:**

> Claude already knows how to write good code. The less you tell it about *how to code*, the better it performs. Use your CLAUDE.md for project-specific context only.

> **How to read the numbers in this guide.** We scored Claude's code output on a **0-100 scale** (higher is better). Scores around 85-90 represent high-quality code needing minor edits; scores in the 60-70 range mean the code works but needs meaningful cleanup. A **+2 point** improvement is noticeable in practice; **+5 or more** is substantial. Most optimizations move the needle by 1-3 points — which is why the recommendations in this guide are selective.

### If you're struggling to get good results

If you've seen others build entire projects with Claude and wondered what you're doing wrong — the answer is probably "too much." Our most counterintuitive finding is that the people getting the *worst* results tend to be the ones trying the hardest to engineer their prompts.

Here's what the data actually says:

- **You don't need a special prompt.** An empty CLAUDE.md scored higher (88.0) than every verbose configuration we tested. In Python, the correlation between instruction length and quality was nearly perfect and negative (r=-0.95) — but cross-language validation (8,640 runs) revealed this was driven by Python-specific instruction content, not verbosity per se. With language-neutral instructions, the correlation disappears in Python (r=+0.03) and actually reverses in JavaScript (r=+0.15, where more instructions help).
- **Start with one small, clear ask.** A 100-token prompt produced noticeably better code than a 1,200-token prompt (+1.7 points, 1,800 runs). "Could you please fix the login validation" beats a paragraph of context about your architecture, coding standards, and design philosophy.
- **The "advanced" techniques hurt in Python.** Chain-of-thought ("think step by step"), skeleton-of-thought ("outline your approach first"), and step-back prompting all reduced Python code quality. The prompting advice circulating online was developed for math and reasoning tasks — it doesn't transfer to Python code generation. (It *does* transfer to Go, C#, and JS — see language-specific guidance.)
- **Be specific about your project, not about how to code.** Telling Claude your build commands, file layout, and tech stack (project context) is neutral-to-positive. Telling Claude to "use descriptive variable names" or "follow SOLID principles" (generic coding advice) actively hurts. Claude already knows how to code — it needs to know about *your* project.
- **Don't pressure Claude with threats, tips, or consequences.** "This is life or death" drops quality by -3.33 points; Sonnet collapses -9.2 points. "I'll tip you $10,000" costs -3.16 points. The only emotional framing that helps is growth-mindset encouragement (+1.88 points, 15,120 runs). Consequence framing also inflates output tokens by 69%.
- **Don't ask Claude to review its own code (unless you have test results to share).** Unconditional "review and fix" follow-ups degrade quality (-0.38 to -5.09 points, 12,960 runs). But when Claude can see specific test failures, iteration helps — especially for Haiku on low-baseline languages (+14-19 points, 10,800 runs). Front-loading good instructions is still more cost-effective than iterating.
- **The gap is iteration, not prompting skill.** People shipping full projects aren't writing one perfect prompt. They're having long conversations with many follow-ups and corrections. The skill is knowing when to course-correct, not knowing a secret incantation.
- **Manage your context window.** `/clear` between unrelated tasks; `/compact` when continuing the same task. Irrelevant context degrades Sonnet's output (1,080 runs), and blind follow-ups in polluted context compound the damage. Put persistent rules in CLAUDE.md, not in conversation messages that will drift into the middle of context and get ignored.

The practical upshot: if you're new to Claude Code, you're closer to optimal than you think. Follow the three recommendations in this guide (code-reviewer persona, polite framing for JS, default temperature), skip everything else you've read online, and focus on clearly describing what you want. When Claude's baseline is low for a given language/model/task combination, prescriptive instructions and technique stacking can help substantially -- this is most common in JavaScript (lowest average baseline at 67.40), but also applies to Haiku+Go, Haiku+C#, and hard Python tasks.

### Where are you? Three stages of AI-native development

Most people land in one of three stages. Identify yours and jump to the relevant section — you don't need to read the whole guide linearly.

**Stage 1: Over-Prompting** *(most common starting state)*

You might be here if: your CLAUDE.md has more than 500 tokens of generic instructions (naming conventions, design principles, "handle edge cases"), you use "think step by step" in Python, you stack multiple personas, or you dictate implementation details.

What it costs you: In Python, there's a near-perfect negative correlation between instruction length and quality (r=-0.95, 6,480 runs) — though cross-language validation (8,640 runs) found this is content-driven (Python-specific rules like PEP 8), not length-driven. With language-neutral instructions, JS actually improves with more instructions (r=+0.15). Stacking personas dilutes effectiveness (-0.5 pts, 5,400 runs). **Exception:** When Claude's baseline is low (JS on average, Haiku+Go, Haiku+C#, hard Python tasks), the kitchen-sink approach helps substantially — JS shows +7.25 over bare (21,600 runs) because its bare baseline is only 67.40. But use language-agnostic phrasing ("follow the language's standard conventions"), not language-specific rules — even correctly-targeted C# rules hurt C# by -1.68 (12,960 runs).

What to do: Jump to the [Decision Test](#the-decision-test) and audit your CLAUDE.md. Remove every line that fails. Your milestone: fewer than 200 tokens of generic content remaining.

**Stage 2: Effective Minimalist** *(target state for most users)*

You might be here if: your CLAUDE.md contains only project context, you use the code-reviewer persona, you apply language-appropriate practices (polite framing for JS, verbose instructions for JS, CoT for Go/C#), and you leave temperature at the default.

What you're getting: The `/init` + persona combination is the strongest configuration we measured — your outputs need minor edits rather than rewrites (scored 89.66, +1.64 over bare, p=0.0001, 4,320 runs).

What to do: Follow the [recommended `/init` workflow](#the-recommended-workflow), apply the [language-specific model routing](#outside-python-language-changes-everything). Your milestone: consistently getting results you'd merge with minor edits.

**Stage 3: Workflow Integrator** *(advanced)*

You might be here if: you route models per task type (Haiku for Python refactoring, Sonnet for Go, Opus for C#), you keep executor prompts under 200 tokens in multi-agent workflows, and you iterate through conversation rather than front-loading instructions.

What you're getting: the 12x efficiency gap — a short executor prompt slightly helped while a long one actively hurt (+0.3 vs -1.4 points, 1,800 runs). Language-appropriate model routing matters even more: choosing the right model for Go or C# can mean the difference between production-quality and barely functional code (27-29 point spread).

What to do: Read [Keeping Your Setup Effective Over Time](#keeping-your-setup-effective-over-time) to prevent your setup from drifting as your project evolves. Your milestone: CLAUDE.md stays accurate across sprints without a dedicated maintenance effort.

> **The counterintuitive part.** Moving from Stage 1 to Stage 2 feels like giving up a skill, not gaining one. If you've invested time crafting elaborate prompts, removing most of that work triggers a sunk-cost reflex. But here's the reframe: you're not unlearning a skill — you're learning that the task is different from what the internet told you it was. The prompting advice online was developed for math and reasoning tasks (where chain-of-thought genuinely helps). Code generation responds differently — often oppositely. In this domain, **restraint is the skill**. Knowing what to leave out is harder and more valuable than knowing what to add.

---

## Start Here: Your First CLAUDE.md

The fastest way to start: run `/init` in Claude Code. It analyzes your codebase and generates a CLAUDE.md with build commands, architecture notes, and configuration details. Then add the code-reviewer persona line at the top (see [Should You Use `/init`?](#should-you-use-init) for the data behind this).

**If you already have a project, `/init` is the recommended path** — it takes under a minute and produced the strongest results we measured when combined with the code-reviewer persona. The template below is for understanding what a good CLAUDE.md looks like, or for writing one by hand if you prefer.

*(This example uses a Python stack. Substitute your own tools — the structure is what matters.)*

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

> **Why so minimal?** We tested 8 CLAUDE.md configurations ranging from 0 to ~6,800 tokens. The empty file (88.0) scored higher than all verbose profiles. The only thing that beat it was a minimal model-tuned prompt (96.3) — confirming that less is more. The correlation between instruction length and quality remains strongly negative. Details in [Methodology](#8-methodology).

---

## Should You Use `/init`?

Claude Code has a built-in `/init` command that auto-generates a CLAUDE.md by analyzing your codebase. It produces build commands, architecture descriptions, data model summaries, and configuration notes. The question is: does that output actually help?

**Short answer: yes, but only when combined with the best practices below.**

We tested four variants of `/init` output against the bare baseline and the best-practices stack (4,320 runs):

| Approach | Score | vs Bare | Significant? |
|----------|-------|---------|-------------|
| `/init` raw output (verbatim) | 88.03 | +0.02 | No (p=0.23) |
| `/init` trimmed (build commands + file locations only) | 87.21 | -0.80 | No (p=0.76) |
| **`/init` + best practices** (persona + polite framing) | **89.66** | **+1.64** | **Yes (p=0.0001)** |
| Trimmed `/init` + best practices | 88.95 | +0.93 | Yes (p=0.003) |
| Best practices alone (no project context) | 89.16 | +1.15 | Yes (p=0.03) |

The `/init` output alone is a wash — it neither helps nor hurts. But `/init` combined with the code-reviewer persona is the **strongest variant we've measured**, outperforming best practices alone by a small margin (+0.50 points, p=0.08) and bare-default by a meaningful margin (+1.64, strongly significant).

**Counterintuitively, trimming doesn't help.** Stripping the architecture descriptions to keep only build commands made the output slightly *worse*. The full project context seems to provide marginal value rather than consuming attention budget — at least when combined with the right persona.

### The recommended workflow

1. Run `/init` to generate your CLAUDE.md
2. Add the code-reviewer persona line at the top: `You are a meticulous code reviewer. Focus on correctness, edge cases, and maintainability in every line you write.`
3. Don't trim the generated content — the architecture context doesn't hurt and may help
4. Remove any generic coding rules if `/init` adds them (style guides, design principles) — those are the instructions that hurt

> **Advanced:** The lift from `/init` + practices came primarily from the LLM quality sub-score (94.92 vs 92.02 for bare), not from test pass rate (flat at ~73-74% across all variants). The code-reviewer persona drives the quality improvement, and project context doesn't interfere with it. On refactoring tasks specifically, `/init` + practices scored +2.30 over bare (p=0.001), matching the best-practices-alone effect (+2.47). Opus benefits most from the added project context (+1.44 over best-practices alone), while Haiku and Sonnet are indifferent (+0.01, +0.04).

---

## Three Things That Actually Help (Plus a Baseline Rule)

Out of everything we tested, only three practices reliably improved Claude's output across languages. When Claude's baseline competence is low -- which happens most often in JavaScript (bare score 67.40) but also in Haiku+Go, Haiku+C#, and hard Python tasks -- verbose instructions and technique stacking can help. Everything else was either neutral or harmful.

### 1. Add the code-reviewer persona

Put this line at the top of your CLAUDE.md:

```
You are a meticulous code reviewer. Focus on correctness, edge cases, and maintainability in every line you write.
```

This is the only persona that consistently improved code quality in Python and JavaScript. It's especially effective for refactoring work.

> **Advanced:** This persona raised composite scores by +1.0 overall and +2.9 on refactoring tasks (1,080 runs). We tested other personas — "senior engineer," "security expert," "performance specialist" — none helped. Importantly, **do not combine personas**. Adding a second role on top of code-reviewer (e.g., "...and a security expert") diluted the benefit by -0.5 points (5,400 runs).
>
> **Cross-language (5,760 runs):** Helps JS (+3.5) and Python (+1.5), neutral in C# (+0.6), harmful in Go (-1.1). For Go projects, omit the persona — especially on Haiku where it causes a -4.1 drop.

### 2. Be polite

Prefix your requests with "Could you please" instead of jumping straight to a command.

| Instead of | Try |
|------------|-----|
| "Fix the login bug" | "Could you please fix the login bug" |
| "Refactor the auth module" | "Could you please refactor the auth module" |
| "Add input validation" | "Could you please add input validation" |

This isn't about etiquette — it measurably changes output quality, particularly in JavaScript. An initial Python-only experiment (810 runs) showed a modest improvement (+1.5 points), but a larger cross-language replication (2,880 runs) found the Python effect was near zero. The robust benefit is in JavaScript, where polite framing reduces catastrophic failures and produces the most consistent results.

> **Advanced:** The original Python-only experiment (810 runs) showed +1.5 points with the lowest variance. However, the larger cross-language replication (2,880 runs) did not reproduce the Python benefit — the effect was -0.3 (not significant). The JavaScript benefit (+2.8) is robust across replications.
>
> **Cross-language (2,880 runs): Politeness only helps JavaScript.** Unlike the code-reviewer persona, polite framing does not transfer broadly:
>
> | Language | Bare | Polite | Delta |
> |----------|------|--------|-------|
> | Python | 84.7 | 84.4 | **-0.3** |
> | Go | 75.7 | 73.3 | **-2.4** |
> | JavaScript | 71.5 | 74.2 | **+2.8** |
> | C# | 61.9 | 60.2 | **-1.8** |
>
> JavaScript benefits substantially (Sonnet +5.2, Opus +3.5). But politeness *hurts* Go (Haiku -8.0) and C# (Haiku -4.0). Python is neutral. **Recommendation:** Use polite framing for JavaScript. Python is neutral — use it or skip it. Skip it for Go and C#.

### 3. Add verification instructions (JavaScript and C#) — but not on top of persona

For JavaScript and C# tasks *without* the code-reviewer persona, ask Claude to verify its work with concrete examples:

```
After writing your code, trace through at least 3 concrete input/output
examples including one edge case. If any example produces wrong output,
fix your code before finalizing.
```

This is the strongest verification variant we tested. Like CoT and politeness, it helps where Claude's baseline competence is lower — and is dead weight in Python.

> **Advanced (10,800 runs):** We tested five verification strategies: vague ("verify that it is correct"), test-oriented ("mentally run through test cases"), example-tracing ("trace 3 input/output examples"), and iterative self-correction ("review, fix, repeat").
>
> | Variant | Python | JS | C# |
> |---------|--------|------|------|
> | verify-vague | -0.5 | **+2.0** (p=0.01) | +0.6 |
> | verify-run-tests | +0.5 | +1.7 (p=0.06) | +1.5 |
> | **verify-with-examples** | **-0.7** | **+3.2** (p=0.0002) | **+1.8** |
> | verify-fix-loop | +0.1 | **+2.1** (p=0.01) | +0.1 |
>
> Python is unresponsive to all variants — Claude already self-verifies well there. JavaScript shows significant improvement across all variants. C# trends positive but doesn't reach significance.
>
> **Model interaction:** Opus responds most strongly in JS (verify-with-examples +4.6, p=0.004; verify-fix-loop +5.7, p=0.0003). Sonnet is largely unresponsive. Bug-fix tasks benefit most (+2.6 for verify-with-examples); refactoring barely responds.
>
> **Redundant with persona (21,600 runs, capstone-v2):** When verification is layered on the persona stack (persona + polite + verification), it adds **zero marginal value**:
>
> | Language | Persona stack | Persona + verify | Delta | p-value |
> |----------|--------------|-----------------|-------|---------|
> | Python | 88.28 | 88.27 | -0.01 | n.s. |
> | Go | 79.26 | 79.90 | +0.64 | n.s. |
> | JS | 71.02 | 70.85 | -0.17 | n.s. |
> | C# | 74.51 | 73.98 | -0.53 | n.s. |
>
> The persona already captures whatever benefit verification provides. **Recommendation:** Use verification instructions *only* if you're not using the code-reviewer persona (e.g., in Go/C# where persona is neutral/harmful). If you're using persona, skip verification — it's redundant.

### 4. Use the default temperature

Don't set `temperature = 0`. Leave it at the default (1.0). Forum posts often recommend temperature 0 for "deterministic coding," but our tests showed the default produces marginally better results with lower variance.

> **Advanced:** Temperature 1.0 was marginally best with the lowest standard deviation (720 runs). The difference is small, but temperature 0 is strictly worse — it just feels more deterministic because outputs are more repetitive, not because they're more correct.

---

## Things to Stop Doing

These are common practices that *sound* helpful but measurably hurt code quality. If you're doing any of these, removing them is the single fastest way to improve your results.

### Don't add generic coding rules

Rules like "use descriptive variable names," "handle edge cases," "follow SOLID principles," or "write docstrings for public functions" are already baked into Claude's training. Repeating them adds noise, not signal.

### Don't use "think step by step" (in Python)

This is the most widely repeated prompt engineering tip on the internet. It works for math problems. It does not work for Python code. Every chain-of-thought variant we tested scored lower than simply asking the question — in Python.

> **Advanced:** In Python, CoT reduced scores by -0.53 to -1.14 points depending on the variant and model. Refactoring tasks were hit hardest at -3.5 points. A related technique — "outline your approach before coding" (skeleton-of-thought) — was even worse: -7.7 points on refactoring with 2.4x the token cost.
>
> **Cross-language (2,880 runs): CoT helps where Claude is weaker.** Outside Python, "Think step by step" improves quality — substantially in some cases:
>
> | Language | Bare | CoT | Delta |
> |----------|------|-----|-------|
> | Python | 84.6 | 84.1 | **-0.5** |
> | Go | 74.8 | 80.1 | **+5.3** |
> | JavaScript | 71.7 | 73.5 | **+1.7** |
> | C# | 62.2 | 69.9 | **+7.7** |
>
> The effect is strongest on Haiku where baseline competence is lowest: Go +12.4, C# +13.9. Opus shows the same pattern (Go +3.3, C# neutral). **Recommendation:** Use CoT for Go and C# tasks, especially on Haiku. Skip it for Python.
>
> **Persona + CoT interaction (21,600 runs, capstone-v2):** Combining the code-reviewer persona with CoT is **dilutive in JavaScript** (-2.40 interaction effect — combined gives less than persona alone) but **slightly synergistic in Go (+0.78) and C# (+0.90)**. The two techniques compete for attention in JS. For Go/C#, they complement each other. **Recommendation:** Never combine persona + CoT for JS. For Go/C# where persona is already neutral/harmful, CoT alone or CoT + persona are both fine.

### Don't combine multiple techniques (when baselines are high)

The "kitchen-sink" approach — chain-of-thought + temperature 0 + a long list of coding rules + a senior engineer persona — barely beats an empty CLAUDE.md in Python despite 6x the prompt tokens. But when Claude's baseline competence is low, these same instructions act as a compensatory scaffold.

> **Advanced:** The kitchen-sink variant tells a baseline-dependent story (21,600 runs, capstone-v2):
>
> | Language | Kitchen-sink | Bare | Delta | p-value |
> |----------|-------------|------|-------|---------|
> | Python | 89.09 | 88.32 | +0.77 | 0.021 |
> | Go | 79.40 | 79.24 | +0.16 | n.s. |
> | **JS** | **74.65** | **67.40** | **+7.25** | **<0.000001** |
> | C# | 73.77 | 73.52 | +0.25 | n.s. |
>
> Kitchen-sink is the **#1 overall variant** (+2.17, p=0.000011), with the largest lift in JS where the bare baseline is lowest (67.40). A regression analysis reveals this is a **baseline competence effect, not a JS-specific property**: each +1 point in bare baseline predicts -0.647 kitchen-sink lift (OLS, 21,600 runs). Low baselines respond to prompting regardless of language.
>
> **Residualized kitchen-sink lift** (after removing bare-score effect via OLS):
>
> | Language | Residualized lift | Interpretation |
> |----------|------------------|---------------|
> | Python | +6.56 +/- 1.06 | Overperforms -- responds better than baseline predicts |
> | Go | +0.70 +/- 1.91 | Right on the trendline |
> | JS | -0.49 +/- 1.02 | Right on the trendline |
> | C# | -6.76 +/- 2.35 | Underperforms -- responds worse than baseline predicts |
>
> **Tight band test (bare 68-73):** Python +2.28, JS +4.37, Go -1.35, C# -10.51 -- overlapping CIs for Python/JS/Go. C# is the outlier, not JS.
>
> **C# underperformance explained (confirmed, 12,960 runs):** The original hypothesis was that our Python-flavored kitchen-sink (snake_case, list comprehensions, PEP 8 references) was contaminating C# generation. A follow-up experiment (12,960 runs) tested language-specific kitchen-sink variants for each language plus a language-agnostic universal variant. Results:
>
> | Kitchen-sink variant | Python | Go | JS | C# |
> |---------------------|--------|------|------|------|
> | Python-flavored (original) | 88.74 | 78.27 | 74.45 | 65.95 |
> | Language-matched | 88.74 | **83.38** | **75.64** | 63.48 |
> | **Universal** | **89.54** | 81.58 | 75.07 | **70.67** |
> | Bare | 88.04 | 69.00 | 67.07 | 65.16 |
>
> The C#-specific kitchen-sink *also* hurt C# (-1.68 vs bare) — it's not purely about Python contamination. Even correctly-targeted C# rules (PascalCase, XML doc comments, constructor injection) interfere with the model's C# priors. The fix is **less specificity, not different specificity**: the universal variant ("follow the target language's standard conventions") gave C# its best score (+5.51 over bare). Language-matched variants won for Go (+14.37) and JS (+8.57) only.
>
> **Sonnet + C# collapse:** Sonnet on C# drops from 70.66 (bare) to 53.64 (kitchen-sink-cs) — a 17-point collapse replicated across both capstone-v2 (-17.82) and this experiment (-18.35). Every kitchen-sink variant degrades Sonnet C# quality. Meanwhile, Haiku C# lifts +22-30 points with kitchen-sink. Verbose prompting helps weak models but actively confuses strong ones on C#.
>
> **Recommendation:** Stack techniques when Claude's baseline is low (JS on average, Haiku+Go, Haiku+C#, hard Python tasks). For high-baseline combinations (Sonnet/Opus+Python), keep it minimal. **For multi-language repos, use universal phrasing** ("follow the target language's standard conventions") rather than language-specific rules — it matches or beats language-specific variants for Python and C#, and comes within ~2 points for Go and JS. Only Go benefits enough from language-specific rules (+14.37 vs +12.57 universal) to justify the maintenance cost. **Never use verbose prompts for Sonnet + C#** — quality collapses 17-18 points.

### Positive vs negative framing doesn't matter

An earlier experiment (648 runs, Python-only) suggested positive framing ("Use guard clauses") slightly outperformed negative framing ("Don't create deeply nested code") (+0.66 points). **A much larger replication (21,600 runs, cross-language) debunked this.** The original finding was confounded — the positive and negative profiles differed in content, not just valence.

When we controlled for content (same 5 rules, matched token count, only phrasing direction changed):

| Language | Positive | Negative | Delta | p-value |
|----------|----------|----------|-------|---------|
| Python | 88.26 | 88.20 | +0.07 | n.s. |
| Go | 80.87 | 80.15 | +0.71 | n.s. |
| JS | 67.01 | 67.28 | -0.27 | n.s. |
| C# | 77.11 | 74.74 | +2.36 | 0.038 (borderline) |

No significant difference in any language except a borderline C# effect. Positive framing is fine as a stylistic preference, but it's not a measurable lever. **Don't spend time rewriting "don't" rules into "do" rules — it doesn't move the needle.**

> **Advanced:** The original +0.66 came from comparing profiles that differed in both framing direction *and* rule content. Capstone-v2 isolated the variable by writing matched pairs: "Use guard clauses and early returns to keep functions flat" vs "Do not create deeply nested code when guard clauses would work." Same semantic content, same token count, only valence changed. Result: noise across 20,499 clean scored runs.

### Don't threaten, tip, or pressure Claude

Emotional framing — consequence language ("this is life or death"), financial incentives ("I'll tip you $10,000"), and career threats ("your job depends on this") — consistently degrades code quality. The only emotional framing that helps is **growth-mindset encouragement** ("I know you can do this, and I'd love to see your best work") at +1.88 points.

| Framing | Score | vs Bare | Token Δ |
|---------|-------|---------|---------|
| Growth-mindset | **+1.88** | Positive | +4% |
| Neutral (bare) | — | Baseline | — |
| Low-stakes ("just a quick draft") | -1.22 | Slightly worse | **-20%** |
| Accountability | -1.67 | Hurts | +12% |
| Tip incentive ("$10,000 tip") | **-3.16** | Hurts substantially | +31% |
| Life-or-death | **-3.33** | Hurts substantially | **+69%** |
| Career threat | -2.88 | Hurts substantially | +45% |

> **Advanced (15,120 runs):** Emotional stakes interact strongly with model and language. Sonnet is catastrophically vulnerable to life-or-death framing — it collapses to 65.96 (-9.2 points vs bare), the largest single-variant degradation we've measured. Haiku and Opus are more resilient (~-1 point each). By language, consequence framing hurts C# worst (-5.1) and Python least (-1.4). The token inflation is the hidden cost: life-or-death framing produces 69% more output tokens — Claude generates verbose defensive code, excessive error handling, and redundant validation that reads as anxious overengineering. The quality drops *and* you pay more for it.
>
> Growth-mindset's +1.88 is driven by Opus (+3.4) and Haiku (+2.1); Sonnet is characteristically resistant (+0.2). The effect is strongest on code-generation tasks (+2.7) and weakest on bug-fix (+0.8).
>
> **Low-stakes as a cost lever:** "Just a quick draft, don't overthink it" produces slightly worse code (-1.22) but 20% fewer output tokens. If you're running high-volume automated workflows where cost matters more than marginal quality, low-stakes framing is a deliberate trade-off — not an anti-pattern, just a tool with known costs.
>
> **Recommendation:** Never use consequence framing, career threats, or tip incentives. If you want to use emotional framing at all, use growth-mindset encouragement — it's the only variant that helps. Otherwise, neutral framing is fine.

### Don't ask Claude to review its own code (without test results)

Unconditional "review and fix your solution" follow-ups degrade code quality. The model rewrites already-correct code without evidence of problems, introducing new bugs and overengineering.

| Turn strategy | Score | vs Single-turn | Token cost |
|--------------|-------|---------------|------------|
| Single-turn bare | 72.31 | Baseline | 1x |
| Single-turn kitchen-sink | 76.77 | **+4.47** | ~1.2x |
| Two-turn blind review | 72.92 | +0.61 | ~2x |
| Two-turn with test feedback | 73.92 | **+1.62** | ~2x |
| Two-turn test feedback + kitchen-sink | 75.19 | **+2.88** | ~2.4x |

The key insight: **iteration only helps when Claude can see what failed.** Blind self-review is net-neutral at best and actively harmful at three turns (-5.09 in v1). But when test results are injected between turns, Claude fixes specific failures rather than rewriting speculatively.

> **Advanced (multi-turn v1: 12,960 runs; v2: 10,748 scored):** v1 tested blind follow-ups at 2 and 3 turns. Two-turn was near-zero (-0.38); three-turn collapsed (-5.09), with Sonnet dropping -8 to -11 points. The model doesn't degrade gracefully — quality falls off a cliff at three turns of undirected review.
>
> v2 introduced test-feedback iteration: the framework runs the task's test suite after turn 1 and injects pass/fail output into the follow-up. Results by model × language:
>
> | Model | Language | Single-turn | Test-feedback | Lift |
> |-------|----------|------------|--------------|------|
> | Haiku | C# | 47.84 | **66.88** | **+19.04** |
> | Haiku | Go | 60.80 | **75.51** | **+14.71** |
> | Haiku | JS | 62.04 | 67.34 | +5.30 |
> | Opus | C# | 82.27 | 82.05 | -0.22 |
> | Sonnet | Python | 89.41 | 89.78 | +0.37 |
>
> The pattern is clear: **test-feedback iteration is a low-baseline rescue mechanism.** Haiku on weak languages (C#, Go) gets massive lifts because the initial code often has clear test failures that Claude can fix when shown. Sonnet and Opus on high-baseline combinations barely benefit — their initial code usually passes.
>
> **Front-loading still wins on cost-efficiency.** Single-turn kitchen-sink (76.77) beats two-turn test-feedback (73.92) at fewer tokens. If you have a fixed token budget, spend it on better instructions rather than an extra turn. Test-feedback iteration is most valuable when you've already front-loaded and still have failures.
>
> **Recommendation:** Don't use blind "review your code" follow-ups — they hurt or waste tokens. If you iterate, share specific test failures. Best strategy: front-load good instructions (kitchen-sink for low-baseline combos), then iterate only if tests fail.

---

## Choosing the Right Model

Different Claude models are better at different types of work. In Python, models perform almost identically (less than 1 point apart). **Outside Python, model choice is the biggest lever** — the gap between models can be enormous, up to 29 points in Go and C#.

### Python task routing

| What you're doing | Use this model | Why |
|-------------------|---------------|-----|
| Fixing bugs | **Sonnet** | Highest accuracy, lowest variance |
| Writing new code | **Sonnet** | Best when tests define correctness |
| Following specific instructions | **Opus** | Near-deterministic compliance |
| Refactoring existing code | **Haiku** | Best restructured code at lowest cost |

**When you're not sure, use Sonnet.** It's the most forgiving — it handles suboptimal prompts better than the other models and produces the most consistent results across all task types. A large-scale test (21,600 runs) confirms: Sonnet barely responds to prompt optimization (max +1.13 over bare), while Haiku and Opus are much more prompt-sensitive (+3.15 and +3.67 respectively).

### Outside Python: Language changes everything

Cross-language testing (5,760 runs) revealed that model choice matters far more outside Python:

| Language | Avg Score | Best Model | Haiku Score | Spread |
|----------|-----------|------------|-------------|--------|
| Python | 83.9 | Any (~equal) | 83.6 | 0.9 |
| JavaScript | 71.7 | Sonnet (76.4) | 66.5 | 9.9 |
| Go | 73.6 | Sonnet (83.3) | 56.2 | 27.1 |
| C# | 65.3 | Opus (78.9) | 49.5 | 29.4 |

**For Go and C#, never use Haiku** — quality drops dramatically — code often needs substantial rework (scores in the 49-56 range, 28-32 points below Sonnet/Opus). Use Sonnet for Go, Opus for C#. For JavaScript, Sonnet leads but all models are competitive.

> **Advanced: Per-model tuning (Python)**
>
> Each model responds slightly differently to system prompts. These prompts were tuned on Python tasks — adapt the language-specific references to your stack. All use `temperature = 1.0` and the "Could you please" prefix.
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
> code. Let the code speak for itself.
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
| Naming conventions (snake_case, PascalCase) | Claude follows language conventions by default. Language-specific rules scored equal or worse than "follow the target language's conventions" for all 4 languages tested (12,960 runs) |
| Formatting rules (indentation, line length) | Claude follows standard formatting; your linter handles the rest |
| Design principles (SOLID, DRY, composition) | Already encoded in Claude's training |
| "Think step by step" | Hurts Python code quality; helps Go/C# (see [CoT section](#dont-use-think-step-by-step-in-python)) |
| Persona ("you are a senior engineer") | Generic personas add noise; only code-reviewer helps |
| Comment/docstring rules | Claude writes appropriate documentation by default. "Keep docstrings brief" is the exception — see below |
| Error handling guidelines | Claude handles errors well; generic guidelines add noise |

> **Exception: "Keep docstrings brief" is the one rule that pays for itself.** We tested docstring variants across 10,800 runs (4 languages). "Keep docstrings brief — one line for simple functions, at most 3 lines for complex ones" is quality-neutral or positive while reducing output tokens by ~21% on average across languages: Python 31.63%, JS 19.92%, C# 18.39%, Go 15.32%. C# actually improved +2.36% with the rule. This works because it constrains a *specific observed behavior* (Claude's tendency toward verbose docstrings) rather than restating training data. Haiku sees the largest reductions (16-43%); Sonnet the smallest (11-25%).
>
> "Do not write docstrings" went too far: -2.3 points overall, with Opus dropping -4.3 points. Opus appears to use docstrings as a reasoning aid — suppressing them degrades its code quality, especially on refactoring tasks. "Write comprehensive Google-style docstrings" was quality-neutral (+0.36) but cost 43% more per run due to a 63% increase in output tokens.
>
> **Recommendation:** If verbose docstrings bother you, add "Keep docstrings brief" to your CLAUDE.md. Don't go further than that — "no docstrings" hurts, and "verbose docstrings" wastes tokens for no quality gain.

### Multi-language repos

If your project uses multiple languages, **do not write language-specific sections** in your CLAUDE.md. Use language-agnostic phrasing instead.

We tested six kitchen-sink variants (12,960 runs) — one tailored to each language (Python, Go, JS, C#), one universal, and one bare control. The universal variant ("follow the target language's standard naming conventions consistently") matched or beat every language-specific variant for Python and C#, and came within ~2 points for Go and JS.

| What to write | What not to write |
|---|---|
| "Follow the target language's standard conventions" | "Use snake_case for functions, PascalCase for classes" |
| "Use the language's idiomatic error handling" | "Return errors as the last value; never panic" |
| "Every public function must have a documentation comment" | "Write JSDoc comments for all exports" / "Use XML doc comments (///)" |

Language-specific rules create two failure modes: (1) rules that fight the model's training distribution (C#-specific rules hurt C# by -1.68 vs bare), and (2) cross-language contamination when the wrong variant's rules bleed into another language's tasks (JS rules on C# tasks: -5.82 vs bare).

The one exception: **Go benefits meaningfully from Go-specific rules** (+14.37 vs +12.57 for universal). If your repo is primarily Go, language-specific rules may be worth the maintenance cost.

> **Advanced (12,960 runs):** Languages with strong, uniform conventions (Go's gofmt, JS's eslint/prettier ecosystem) benefit from specific prompting because the rules align with the model's training data. Languages with more variation in idiomatic style (C# has multiple valid patterns for DI, naming, async) get confused by opinionated rules that may not match the model's priors. Prescriptive rules that match the model's priors amplify quality; rules that fight them create interference.

### Where to put instructions

If you do have project-specific instructions, put them in **CLAUDE.md only** — not in your chat messages. The same instruction performs better as a system prompt than as a user message.

> **Advanced:** System-prompt placement outperformed user-message placement by +0.7 to +2.8 points (2,520 runs). Never duplicate instructions across both locations — it dilutes the effect. Opus is the most sensitive to placement (2.8-point swing). Also: keep your CLAUDE.md formatted with markdown headers and bullets. Stripping formatting to "save tokens" only saves 5-13% but degrades quality for Haiku (-1.56 pts) and Sonnet (-0.86 pts).

---

## Keeping Your Setup Effective Over Time

A CLAUDE.md that described your project accurately three months ago may be actively misleading today. Stale build commands, outdated architecture descriptions, and references to removed services don't just fail to help — they consume attention budget with wrong information. The same principle that makes generic instructions harmful (they add noise) applies to *outdated* project context.

### When to update CLAUDE.md

Not every project change requires a CLAUDE.md update. Apply the same test you used to write it: **"Would a senior engineer joining today be confused without this?"**

| Change type | Update CLAUDE.md? | Example |
|---|---|---|
| Architecture change | **Yes** | Added a new service, changed the data model, migrated frameworks |
| Build system change | **Yes** | New commands, changed test runner, new CI pipeline |
| Convention change | **Yes** | Switched from UUIDs to ULIDs, new API response format |
| Sprint context | **Yes** | New feature flags, deprecated endpoints, in-progress migrations |
| Style guide change | No | Claude follows language conventions by default |
| New library adoption | No | Claude already knows common libraries from training |
| Team member change | No | Not project-specific technical context |

The decision rule: if Claude already knows it from training data, skip it. If it's specific to your project and has changed, update it. This is the [Decision Test](#the-decision-test) applied to maintenance, not just initial authoring.

### Detecting drift: a 5-minute audit

Run these four checks at the start of each sprint, or whenever the architecture section of your README changes:

1. **Build commands**: Copy-paste every build/test/lint command from your CLAUDE.md into a terminal. Do they all succeed? If any fail, the file is stale.
2. **File layout**: Does the directory structure described in CLAUDE.md match what's actually in `src/`? Do the listed services, modules, and config paths still exist?
3. **Conventions**: Look at the last 5 merged PRs. Are the conventions described in CLAUDE.md the conventions the team is actually following?
4. **Sprint context**: Is the "current work" section describing work that was completed weeks or months ago? If so, update or remove it.

This is not a heavy process. If your CLAUDE.md is minimal (as it should be), the audit takes less than five minutes. The more bloated the file, the more there is to drift — another reason to keep it lean.

### Update docs in the PR, not in a follow-up

The single most effective entropy prevention pattern: **update CLAUDE.md in the same pull request that changes reality.** If your PR migrates from REST to GraphQL, the CLAUDE.md update is part of that PR — not a separate ticket that gets deprioritized.

Add this to your PR review checklist: *"Does this PR change anything CLAUDE.md describes? If so, is CLAUDE.md updated in this PR?"*

This is the same discipline behind keeping tests next to the code they test. Separating the update from the change that caused it creates a window where the documentation is wrong — and that window tends to stay open indefinitely.

### Security considerations

CLAUDE.md is a checked-in file visible to anyone with repo access. Keep it useful for Claude without creating security exposure:

- **Never put secrets, API keys, or credentials in CLAUDE.md.** Use environment variables and reference them by name only ("Auth tokens are in `AUTH_SERVICE_KEY` env var").
- **Update auth descriptions when patterns change.** If you migrate from API keys to OAuth, or from session cookies to JWTs, update the auth line in CLAUDE.md. Stale auth descriptions lead Claude to generate code against the old pattern.
- **Note version constraints for external services.** If your payment integration uses Stripe API v2024-12 (not the latest), say so. Claude will default to the latest API otherwise.
- **Dependency security is outside CLAUDE.md scope.** Use standard tooling (Dependabot, `npm audit`, `pip-audit`) for vulnerability scanning. CLAUDE.md is for project context, not security automation.

### Architecture decision records

CLAUDE.md tells Claude *what* your project looks like now. For *why* you made the decisions you did, consider lightweight architecture decision records (ADRs) — short documents that capture the context, options considered, and rationale behind significant technical choices.

ADRs complement CLAUDE.md because the "state desired outcomes, not implementation details" principle applies to both: describe the decision and its rationale, not a prescriptive rulebook. When Claude encounters an ADR, it understands the intent behind the architecture — not just the current shape of it — and is less likely to propose changes that violate the original reasoning.

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

## Token Efficiency: Getting More for Less

Every token costs attention, not just money. Two rules cover most of the savings:

1. **If you must include instructions, keep them short.** A 12-token telegram ("Correct. Readable. Specific exceptions. Single responsibility.") scored identically to a 140-token verbose version of the same ideas. The model already knows what these words mean — elaborating adds nothing.

2. **In Python, a cheap model with a good prompt beats an expensive model with none.** Haiku with the code-reviewer persona and polite framing matched bare Opus on Python quality — at roughly 5-10x lower cost. **Outside Python, this does not hold.** Haiku+persona scores 31-33 points below Opus in Go and C# (3,600 runs). The "use Haiku for cost savings" recommendation is Python-only.

### Writing efficient prompts

For Python and Go, describe **WHAT** you want, not **HOW** to get there. For JavaScript and C#, it depends — see the caveat below.

| Instead of | Write |
|------------|-------|
| "Fix the SQL injection by converting to parameterized queries, validate columns with regex, change where() to accumulate in a list" | "Fix this QueryBuilder. SQL injection, where-clause overwrite, missing input validation." |
| "Create a base class with abstract methods for lint/test/complexity, refactor into a subclass, add a registry" | "Make the scorer support Go, JS, and C#. Keep backward compat." |
| "Use snake_case for variables, PascalCase for classes, UPPER_SNAKE_CASE for constants..." | "Follow PEP 8." |

The model already knows how to fix SQL injection, design class hierarchies, and follow PEP 8. Name the problems and goals — it will choose the right implementation.

> **Caveat: "WHAT not HOW" flips by language (21,600 runs).** We tested matched outcome-focused ("Produce code that is correct, handles edge cases, and is easy to read") vs implementation-focused ("Use early returns, extract helpers, add type hints, use comprehensions") prompts across all 4 languages:
>
> | Language | Outcome | Implementation | Delta (O-I) | p-value |
> |----------|---------|---------------|-------------|---------|
> | Python | 87.40 | 87.31 | +0.09 | n.s. |
> | Go | 80.88 | 80.08 | +0.81 | n.s. |
> | **JS** | 68.26 | **73.12** | **-4.87** | **<0.0001** |
> | **C#** | **77.09** | 69.16 | **+7.94** | **<0.0001** |
>
> JS wants prescriptive HOW instructions (+5.72 vs bare); C# wants declarative WHAT instructions (+3.57 vs bare). For Python and Go, it doesn't matter. The "state WHAT not HOW" advice is correct for C# and neutral for Python/Go, but actively wrong for JavaScript. Note: the JS preference for HOW may also be partially a baseline effect -- JS has the lowest bare score (67.40), and low baselines respond more to prescriptive scaffolding (see [kitchen-sink section](#dont-combine-multiple-techniques-when-baselines-are-high)). The C# preference for WHAT, however, is likely a prompt contamination artifact -- our implementation-focused prompt uses Python-specific rules (snake_case, list comprehensions) that actively misdirect C# code generation.

> **Advanced: Instruction compression (5,400 runs).** We held semantic content constant and varied expression density from 12 to 140 tokens. All variants scored within a 0.4-point range (92.59–92.99). Telegram vs verbose: p=0.56 — indistinguishable. Bullets edged out marginally (p=0.042, d=0.12). Bonus: telegram-style also reduced *output* tokens by 25-33%. The model mirrors your brevity.

### Compressed instructions outperform verbose ones

A dedicated output-compression experiment (15,120 runs) tested whether you can compress your CLAUDE.md instructions without losing quality. The answer: **compressed instructions are strictly better** — they score higher *and* cost less.

We held semantic content constant and compressed 148 words of project-specific rules into 47 words of telegram-style prose. For example, verbose: "Always use SQLAlchemy 2.0 query style with the new select() syntax. Database migrations should be created using Alembic. All API error responses must conform to RFC 7807 problem details format." Compressed: "SQLAlchemy 2.0 select() style. Alembic for migrations. API errors: RFC 7807." Same rules, fewer tokens.

| Instruction style | Score | vs Bare | Tokens/run | Score/kTok |
|-------------------|-------|---------|------------|------------|
| Compressed rules (47 words) | **73.72** | **+3.36** | 1,640 | 44.89 |
| Verbose rules (148 words) | 72.52 | +2.16 | 2,041 | 35.53 |
| Code-adapted (compress prose, preserve code markers) | 73.08 | +2.72 | 1,410 | **51.83** |
| Terse-generic ("Answer concisely") | 71.27 | +0.91 | 1,150 | 61.97 |
| Caveman-full (structured compression rules) | 70.56 | +0.20 | 1,055 | 66.88 |
| Caveman-ultra | 70.39 | +0.03 | **945** | **74.49** |
| Bare | 70.36 | — | 1,583 | 44.45 |

**The practical recommendation:** Write your CLAUDE.md rules in compressed, telegram-style prose. "SQLAlchemy 2.0 select() style. Alembic for migrations. API errors: RFC 7807. Auth via middleware, never inline." This outperforms the verbose version by +1.2 points while using 20% fewer tokens.

> **Advanced (15,120 runs):** The "caveman" compression format (drop articles, filler, pleasantries; use fragments and abbreviations) barely beats bare on quality (+0.20) but cuts output tokens by 34%. The structured rules that make caveman work for chat ("Pattern: [thing] [action] [reason]") don't transfer well to code generation — the model follows the compression format in its explanations but the code quality doesn't improve. A generic "Answer concisely" (2 tokens of instruction) outperforms the full caveman ruleset (89 tokens) at +0.91 vs +0.20.
>
> The **code-adapted** variant is the quality/cost sweet spot: it compresses all prose explanation but explicitly exempts code quality markers — descriptive identifiers, type hints, specific exceptions, docstrings, and full test names. This prevents the compression instinct from bleeding into the code itself. At 51.83 score/kTok, it's the best bang-for-buck variant after the bare minimum options.
>
> **Why compressed rules beat verbose:** The model already knows what "handle edge cases" means. Verbose elaboration ("Think carefully about boundary conditions, empty inputs, and invalid types, and address each one explicitly rather than relying on defaults") adds tokens that consume attention without adding information. The compressed version signals the same intent in fewer tokens, leaving more attention budget for the actual task.
>
> **Model interaction:** Haiku benefits most from compression (+4.1 compressed-rules vs bare); Opus benefits least (+1.2). Sonnet is characteristically flat across all variants (max +0.8). By language, compressed rules help JS most (+5.8) and Python least (+1.4) — consistent with the baseline-competence pattern.
>
> **Recommendation:** Compress your CLAUDE.md instructions into telegram-style prose. If you want maximum cost efficiency with acceptable quality, use the code-adapted approach: compress explanations, preserve code quality markers. For automated high-volume workflows where cost dominates, "Answer concisely" gives the best score/kTok ratio among variants that meaningfully beat bare.

> **Advanced: Model + prompt co-optimization (5,400 runs).** In Python, Haiku + persona + polite scored 93.42 vs Opus bare 92.67 — statistically indistinguishable but at 33.79 vs 19.12 points/1K tokens. **Cross-language validation (3,600 runs) showed this is Python-specific.** Haiku+persona vs Opus-bare: Python +0.76 (parity), JS -3.12 (close), Go -31.47 (catastrophic), C# -32.56 (catastrophic). Persona actually hurts Haiku in Go (-2.5) and C# (-4.2). Sonnet bare was the worst configuration tested in Python (91.11) — without guidance it over-generates verbose, lower-quality output. Adding persona + polite fixed it (+2.76 pts, -42% output tokens).

> **Advanced: Output verbosity is the main cost lever (10,800 runs).** The targeted-constraints and doc-brevity-cross-language experiments showed that a one-line docstring rule ("Keep docstrings brief") cut average cost per run by ~21% cross-language (15-32%) while maintaining or improving quality. The savings come entirely from output tokens — the model mirrors your brevity. Per-language: Python 31.63%, JS 19.92%, C# 18.39%, Go 15.32%. C# actually improved +2.36% with the rule. Conversely, "Write comprehensive Google-style docstrings" increased cost by 43% for a negligible +0.36 quality gain. See the [docstring caveat](#what-not-to-put-in-claudemd) for the full breakdown.

> **Advanced: The efficiency cheat sheet.**
>
> | Pattern | Savings | Evidence |
> |---------|---------|----------|
> | "Keep docstrings brief" instead of default verbosity | ~21% cost reduction (15-32% cross-language), same or better quality | 10,800 runs, confirmed across 4 languages |
> | Telegram keywords instead of prose | ~80% fewer input tokens, same quality | 5,400 runs, p=0.56 |
> | Compressed rules instead of verbose rules | ~20% fewer tokens, +1.2 quality | 15,120 runs, compressed > verbose |
> | Code-adapted compression (compress prose, preserve code markers) | Best score/kTok (51.83) | 15,120 runs, quality/cost sweet spot |
> | "Answer concisely" instead of structured compression rules | 2 tokens of instruction, +0.91 quality | 15,120 runs, beats 89-token caveman ruleset |
> | Goal + constraints instead of dictating architecture | ~70% fewer input tokens | Overspecification-cascade: minimal matches exhaustive |
> | "Follow PEP 8" instead of enumerating rules | ~95% fewer input tokens | r=-0.95 for Python-specific instructions (6,480 runs); language-neutral instructions show flat/positive correlations (15,120 runs) |
> | Goal + format instead of long agent briefings | ~60% fewer input tokens | gsd-methodology: 12x efficiency gap (1,800 runs) |
> | Haiku + persona + polite instead of bare Opus | ~5-10x cost reduction (Python only) | 5,400 runs, Python equivalent; Go/C# 30-pt gap |
> | Remove generic coding advice entirely (Python) | 100% savings, quality *improves* in Python; JS loses quality without instructions | Capstone: empty > all verbose profiles (15,120 runs cross-language) |

---

## Context Management: When to `/clear` vs `/compact`

Your CLAUDE.md is only half the picture. The other half is your *session context* — every file read, every command output, every message. This fills up fast, and performance degrades as it fills. Managing when to reset vs compress is a concrete skill that affects code quality.

**The decision is simple:** Is the prior context *relevant* to the next task?

### `/clear` — start fresh

Use `/clear` when switching to an unrelated task. Any context from the previous task is noise that consumes attention budget without adding value.

Also use `/clear` when:
- **You've corrected Claude more than twice on the same issue.** The context is polluted with failed approaches. A fresh prompt with what you've learned will outperform continuing. Our multi-turn data supports this: blind follow-ups degrade quality (-0.38 to -5.09 points, 12,960 runs), and the degradation compounds with each turn.
- **You're on a high-baseline combination** (Python + Sonnet/Opus). These combos perform best with minimal context — extra history is more likely to hurt than help.
- **The session has been compacted multiple times.** Each compaction is a lossy summarization. After 2-3 cycles, original intent fades and you're better off restarting with a clear prompt.

### `/compact` — compress and continue

Use `/compact` when continuing the same task and the conversation history contains decisions, constraints, or partial work that Claude needs to remember.

Also use `/compact` when:
- **You're on a low-baseline combination** (JS, Haiku+Go, Haiku+C#). Our multi-turn v2 data (10,748 runs) showed that relevant prior context lifts these combos substantially — Haiku+C# gained +19 points and Haiku+Go gained +14 points when given specific feedback from prior turns. Throwing that away with `/clear` means restarting from a weak baseline.
- **The session contains project-specific context** (architecture decisions, file locations, constraint discussions) that would take multiple turns to re-establish.
- **You can guide the compression** — `/compact Focus on the API changes` or `/compact keep only the plan and current file state` tells Claude what to preserve.

### Why this matters

Irrelevant context degrades quality. Our context-pollution experiment (1,080 runs) found that Sonnet's output quality drops when padded with 50k tokens of unrelated content. The "lost in the middle" effect is well-documented in the literature (Liu et al., 2023): LLMs attend most to the beginning and end of context, with a dead zone in the middle. As your session grows, instructions and decisions from the middle of the conversation are most likely to be ignored.

The practical implication: **put persistent rules in your CLAUDE.md** (which loads at the start of every context window), not in conversation messages that will drift into the middle and eventually get compacted away.

> **Advanced: Subagents are context-free side channels.** When you need to investigate something (grep a codebase, read multiple files, research a question), delegate to a subagent. It runs in its own isolated context window and returns only a summary, keeping your main session clean. This is the most underused context management technique — it lets you do research-heavy work without filling your primary context with tool output you only needed once.

---

## Effective Prompts by Task Type

The principles above are general — this section shows what they look like in practice. Each template is a standalone prompt for a specific task type, incorporating the findings that matter for that task. Copy, adapt to your project, and use as-is.

**How to read these templates:** The bolded preamble is the persona line from your CLAUDE.md (you don't repeat it in every message). The prompt itself is what you type. Notes below each template explain why it's structured that way.

### Bug fix

```
Could you please fix the TypeError in src/api/handlers.py where
process_webhook() crashes on payloads missing the "metadata" field.
The error is on line 47. Expected behavior: skip processing and
return 200 with an empty result.
```

**Why this works:** Names the file, line, root cause, and expected behavior. Doesn't prescribe *how* to fix it (no "add a try/except" or "use a guard clause") — just describes the desired outcome. The polite prefix helps in JavaScript; it's neutral in Python.

### New feature

```
Could you please add a /health endpoint to the FastAPI app that
returns {"status": "ok", "version": "<from pyproject.toml>"} and
responds within 50ms. No authentication required.
```

**Why this works:** Specifies the endpoint, response shape, performance constraint, and auth behavior — all project-specific decisions Claude can't infer. Doesn't say "use a GET handler" or "read the version with tomllib" — those are implementation details Claude will handle correctly.

### Refactoring

```
Could you please refactor OrderService.process() in
src/services/orders.py. It currently handles validation, pricing,
and notification in one 200-line method. Break it into focused
methods on the same class. Keep the public interface unchanged.
```

**Why this works:** States what's wrong (one method doing three things), what "done" looks like (separate methods, same interface), and the constraint (same class — don't over-abstract). Refactoring is the task type most sensitive to prompting strategy; keeping the prompt focused on *what to change* avoids the overengineering that verbose prompts encourage.

### Instruction-following (specific constraints)

```
Could you please add input validation to the create_user endpoint.
Requirements: email must be a valid format, password minimum 12
characters, username must be alphanumeric 3-30 characters. Return
422 with field-level error messages on failure.
```

**Why this works:** Lists exact constraints as acceptance criteria. Uses positive framing ("must be" not "must not contain"). Specifies the error response code and shape. Opus is near-deterministic on instruction-following tasks — if you use it, these constraints will be followed precisely.

### Go or C# tasks (where CoT helps)

```
Think step by step. Implement a concurrent-safe LRU cache in Go
with a maximum size of 1000 entries. It should support Get, Put,
and Delete operations. Use sync.RWMutex for read-heavy workloads.
```

**Why this works:** The "Think step by step" prefix — harmful in Python — substantially improves Go and C# quality (+5.3 and +7.7 points respectively). For languages where Claude's baseline competence is lower, the explicit reasoning step catches edge cases it would otherwise miss. Skip the polite prefix for Go and C# (it hurts in those languages).

### JavaScript tasks (where more instruction helps)

```
Could you please add retry logic with exponential backoff to the
API client in src/services/api.js. Max 3 retries, starting at
100ms. Use early returns for error cases, extract a helper for
delay calculation, and handle both network errors and HTTP 5xx
responses separately.
```

**Why this works:** JavaScript has the lowest average bare baseline (67.40), and low baselines respond well to prescriptive scaffolding. HOW-focused instructions significantly outperform outcome-focused ones in JS (+5.72 over bare, p<0.0001). Implementation details that hurt when baselines are high *help* when baselines are low. The kitchen-sink approach is the *best variant tested* for JS (+7.25 over bare, 21,600 runs). The same pattern applies to Haiku+Go and Haiku+C# -- when model competence is low, more instruction helps. If you're using the code-reviewer persona for JS, don't also add verification instructions -- they're redundant.

### Multi-agent executor task

```
Fix the off-by-one error in pagination logic in src/api/list.py.
The last page returns one duplicate record. Make your changes
atomic and self-contained.
```

**Why this works:** Under 50 tokens. No planning context, no architectural background. Executor prompts perform best under 200 tokens — this one states the bug, the file, the symptom, and the scope constraint. The orchestrator holds the bigger picture; the executor just needs to know what to change.

### Template structure

Every effective prompt above follows the same pattern:

1. **Preamble** — Polite prefix (for Python/JS) or CoT prefix (for Go/C#), not both
2. **Action** — What to do, in one sentence
3. **Location** — Where in the codebase (file, function, line)
4. **Outcome** — What "done" looks like (expected behavior, response shape, constraints)
5. **Verification** (JS/C# without persona only) — "Trace through 3 examples including one edge case." Skip if using the code-reviewer persona — it's redundant.
6. **Nothing else** — No coding advice, no design principles, no implementation details. **Exception: low-baseline combinations benefit from prescriptive instructions** -- especially JS, Haiku+Go, and Haiku+C# (see [kitchen-sink section](#dont-combine-multiple-techniques-when-baselines-are-high)).

If your prompt has more than these five elements, you're probably over-specifying -- unless Claude's baseline is low for your language/model combination (e.g., JS, Haiku+Go, Haiku+C#), where verbose instructions are the #1 variant.

---

## Quick Reference Card

For experienced users who just want the cheat sheet:

### Do This / Not This

| Do This | Not This |
|---------|----------|
| Start with an empty CLAUDE.md; add only project-specific context | Copy a community CLAUDE.md template and fill in every section |
| "Could you please fix the login bug" (warm framing, Python/JS) | "Fix the login bug" (terse imperative) |
| Use the code-reviewer persona for quality-sensitive work | Stack multiple personas ("you are a senior engineer and security expert and...") |
| State WHAT you want (Python/Go/C#) | Dictate algorithms and implementation details (except low-baseline combinations like JS, Haiku+Go -- HOW helps there) |
| Write constraints as plain text sentences | Use CAPS LOCK, numbered checklists, or XML tags for emphasis |
| Add "trace 3 examples" verification for JS/C# tasks *without* persona | Stack verification on top of persona (redundant — zero marginal lift) |
| Route refactoring to Haiku **(Python only)**; use Sonnet/Opus for Go, JS, C# | Use the same model for every task type |
| Either framing is fine — positive/negative is noise | Spending time rewriting "don't" rules into "do" rules |
| Put behavioral instructions in CLAUDE.md (system prompt) | Put behavioral instructions in your chat messages |
| Keep markdown headers and bullets in CLAUDE.md | Strip formatting to "save tokens" |
| Keep agent executor prompts under 200 tokens | Inject full planning context into executor prompts |
| `/clear` between unrelated tasks; `/compact` to continue the same task | Running a single session for hours across multiple unrelated tasks |

### Anti-Patterns Checklist

If you're auditing an existing setup, check for these. Each one made code measurably worse:

1. **"Think step by step"** for Python tasks (helps Go/C# — see above)
2. **"Outline your approach before coding"** (skeleton-of-thought)
3. **Multiple personas** stacked together
4. **"Produce FAANG-grade code"** or quality anchoring language
5. **Numbered checklists** for constraints (implies sequence where none exists)
6. **Dictating algorithms** instead of describing desired outcomes **(except when baselines are low -- JS, Haiku+Go, Haiku+C# -- where prescriptive HOW helps)**
7. **Stacking verification on persona** — verification is redundant with code-reviewer persona (21,600 runs)
8. **Generic coding instructions** like "use descriptive names" **(except when baselines are low -- verbose instructions lift JS by +7.25 and help other low-baseline combinations similarly)**
9. **Injecting planning context** into agent executor prompts
10. **"Think about principles first"** (step-back prompting)
11. **Using Haiku for Go or C# tasks** (quality collapses 28-32 points vs Sonnet/Opus)
12. **Persona + CoT in JavaScript** — dilutive interaction (-2.40), use one or the other
13. **Verbose prompting for Sonnet + C#** — quality collapses 17-18 points (replicated across 2 experiments, 34,560 runs). Sonnet has strong C# priors; kitchen-sink instructions create interference
14. **Language-specific coding rules in multi-language repos** — a universal "follow the language's conventions" outperforms language-specific variants for Python and C# (12,960 runs). Only Go benefits from specificity
15. **"This is life or death" / consequence framing** — life-or-death -3.33 pts, Sonnet collapses -9.2 pts; career-threat -2.88 pts. Consequence framing inflates tokens 69% with worse quality (15,120 runs)
16. **"I'll tip you $10,000"** or other financial incentives — -3.16 pts, tokens inflate 31%. The model over-generates defensive code without improving correctness
17. **"Review and fix your code" (blind self-review)** — unconditional follow-ups degrade quality: -0.38 at two turns, -5.09 at three turns (12,960 runs). Only iterate when you have specific test failures to share

---

## Caveats

These findings are real and statistically rigorous, but bounded in scope:

- **Cross-language validated.** Core findings tested across Python, Go, JavaScript, and C# (~129,000+ cross-language runs across 12 experiments including capstone-v2, language-kitchen-sink, multi-turn v1/v2, emotional-stakes, output-compression, verbosity-curve-cross-language, doc-brevity-cross-language, and cheap-model-rich-prompt-cross-language). A regression analysis (21,600 runs) found that kitchen-sink lift is predicted by bare baseline score (-0.647 pts per +1 bare point) -- low baselines respond to prompting regardless of language. JS shows the largest raw lift because it has the lowest bare baseline (67.40), not because it is uniquely receptive. C# kitchen-sink underperformance is confirmed as both prompt contamination AND over-specificity — even C#-tailored rules hurt (-1.68 vs bare), while language-agnostic phrasing helps (+5.51). Go and C# diverge on CoT (helps instead of hurting) and politeness (hurts instead of helping). Model choice matters 10-30x more outside Python. **Model substitution is Python-specific**: Haiku+persona matches Opus in Python (+0.76) but fails catastrophically in Go (-31.47) and C# (-32.56) (3,600 runs).
- **Score scales differ by language.** Python averages 83.9 (high quality) vs C# at 65.3 (needs more cleanup) under identical conditions. Compare effects within a language, not raw scores across languages.
- **Single-file tasks only.** We didn't test multi-file navigation or codebase understanding. Project context in CLAUDE.md is likely *more* valuable in those scenarios than this benchmark can measure.
- **Generic coding tasks.** Domain-specific tasks with complex business logic or unfamiliar frameworks may respond differently.
- **Limited multi-turn testing.** Blind self-review ("review and fix your code") degraded quality in v1 (12,960 runs: -0.38 at two turns, -5.09 at three turns). A follow-up experiment (v2, 10,748 scored) tested closed-loop iteration with test feedback between turns — this helped low-baseline combinations substantially (Haiku+C# +19.04, Haiku+Go +14.71) but front-loading good instructions still beats iteration for the same token budget. Extended multi-file conversations with tool use remain untested.
- **Workflow rules not measured.** Rules like "run tests before committing" or "use conventional commits" affect development workflow, not code quality. They may be valuable even though they don't move these scores.
- **Claude models only.** Results are for Claude Haiku 4.5, Sonnet 4.6, and Opus 4.6. Other model families may respond differently.

---

## 8. Methodology

> **This section is for those who want to verify the numbers.** The recommendations above stand on their own — you don't need to read this section to use them.

These guidelines come from ~231,000+ benchmark runs across 24 controlled experiments using the claude-benchmark tool.

**How we scored:** Composite = 50% static analysis + 50% LLM judge. Static analysis uses language-appropriate tooling: pytest/ruff/radon (Python), `go test`/`golangci-lint`/`gocyclo` (Go), Jest/ESLint (JavaScript), `dotnet test`/`dotnet format` (C#). LLM judge: Claude Haiku 4.5 scoring readability, architecture, instruction adherence, and correctness on a 1-5 scale.

**How we tested:** 10-30 replications per experimental cell. 12-16 tasks per language spanning bug-fix, code-generation, refactoring, and instruction-following at easy/medium/hard difficulty. All 3 models tested per experiment unless investigating model-specific effects.

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
| capstone-best-practices | 6,480 | Empty baseline (88.0) > all verbose profiles; tuned-sonnet (96.3) wins |
| cross-language | 5,760 | Model gap widens 10-30x outside Python; persona effect is language-dependent |
| cot-cross-language | 2,880 | CoT hurts Python (-0.5) but helps Go (+5.3), JS (+1.7), C# (+7.7) |
| politeness-cross-language | 2,880 | Polite framing helps JS (+2.8) only; hurts Go (-2.4) and C# (-1.8) |
| gsd-methodology | 1,800 | Minimal executor prompts outperform verbose ones |
| targeted-constraints | 4,320 | "Brief docstrings" is quality-neutral, 19% cheaper; "no docstrings" hurts Opus (-4.3) |
| init-vs-best-practices | 4,320 | /init alone neutral; /init + code-reviewer persona is strongest variant |
| verification-instructions | 10,800 | Verification helps JS (+3.2, p=0.0002) but not Python; "trace 3 examples" best |
| capstone-v2 | 21,600 | Kitchen-sink lift predicted by bare baseline (-0.647/pt); JS lift is a baseline effect, not JS-specific; C# underperformance is prompt contamination; WHAT/HOW flips by language; framing direction is noise; verification redundant with persona |
| language-kitchen-sink | 12,960 | Universal kitchen-sink (79.22) beats all language-specific variants; language-matched wins for Go (+14.37) and JS (+8.57) only; C#-specific rules also hurt C# (-1.68); Sonnet+C# collapses 17-18 pts with any verbose prompt; "follow the language's conventions" is the best multi-language default |
| multi-turn-conversation | 12,960 | Blind self-review hurts: -0.38 at two turns, -5.09 at three turns; Sonnet collapses -8 to -11 at three turns; single-turn kitchen-sink (80.20) beats two-turn kitchen-sink (79.44) at half the tokens |
| multi-turn-conversation-v2 | 10,748 | Test-feedback iteration helps low baselines (Haiku+C# +19.04, Haiku+Go +14.71); Sonnet resistant to iteration; front-loading still beats iteration for same token budget (kitchen-sink 76.77 > test-feedback 73.92) |
| emotional-stakes | 15,120 | Growth-mindset only positive framing (+1.88); life-or-death -3.33 (Sonnet -9.2); tip-incentive -3.16; consequence framing inflates tokens 69%; low-stakes -1.22 but 20% cheaper |
| output-compression | 15,120 | Compressed rules (+3.36) > verbose (+2.16) at 20% fewer tokens; caveman barely beats bare (+0.20) but -34% tokens; code-adapted is quality/cost sweet spot (51.83 score/kTok); "Answer concisely" beats structured caveman rules |
| verbosity-curve-cross-language | 8,640 | r=-0.95 is Python-specific content, not verbosity per se; language-neutral: Python r=+0.03, Go r=+0.04, JS r=+0.15 (positive, monotonic +5.11), C# r=+0.02 |
| doc-brevity-cross-language | 6,480 | "Keep docs brief" confirmed cross-language: 15-32% token reduction, quality neutral/positive (C# +2.36%); Haiku sees largest reductions (16-43%) |
| cheap-model-rich-prompt-cross-language | 3,600 | Haiku+persona = Opus in Python only (+0.76); Go -31.47, C# -32.56 (catastrophic); persona hurts Haiku in Go (-2.5) and C# (-4.2) |

### External validation

Our language-ordering and model-tier findings are corroborated by independent benchmarks:

| Finding | Our data | External evidence |
|---------|----------|-------------------|
| Python is the strongest language | 84-88 avg (all models) | Universal across SWE-bench Multilingual, Multi-SWE-bench, aider polyglot, HumanEvalPack |
| Smaller models collapse on non-Python | Haiku: C# 43, Go 50 vs Python 84 | Multi-SWE-bench: weaker models drop to 0-3% on most non-Python languages. Aider polyglot: Haiku 28% vs Sonnet 52% |
| Refactoring/optimization is the hardest task type | Refactoring scores 29-72 by model (lowest of all types) | Multi-SWE-bench: "bug fix > new feature > feature optimization" across all models and languages |
| Go performance below Python | 74-83 avg | SWE-bench Multilingual: Go 31% vs Python 63% |
| JS is a weak language for LLMs | 67-76 avg (lowest in our benchmark) | Multi-SWE-bench: JS 1-5% (worst across all models); SWE-bench Multilingual: JS/TS 35% vs Python 63% |

**Where our data is novel (no external comparison):**

- **Prompting effects vary by language** — CoT hurts Python but helps Go/C#; polite framing helps only JS; persona effects are language-dependent. No published benchmark tests prompting variations across languages.
- **C# performance data** — C# is omitted from SWE-bench Multilingual, Multi-SWE-bench, HumanEvalPack, and aider's polyglot benchmark. Our model-tier spread (Opus 79, Sonnet 68, Haiku 50) and the Sonnet+C# verbose-prompt collapse appear unique in the literature.
- **Instruction density vs quality** — the r=-0.95 correlation (now known to be content-driven, not length-driven — cross-language validation shows flat/positive correlations with language-neutral instructions), emotional framing effects, and instruction compression findings have no external parallel.
- **Model substitution fails outside Python** — Haiku+persona matches Opus in Python but collapses -31 to -33 points in Go and C# (3,600 runs). No published benchmark tests model substitution with prompt engineering across languages.
- **Model-specific prompting sensitivity** — Sonnet's resistance to prompting (max +1.13 lift) vs Haiku/Opus responsiveness is untested elsewhere.

Sources: [SWE-bench Multilingual](https://www.swebench.com/multilingual.html) (Amazon, 2025), [Multi-SWE-bench](https://arxiv.org/abs/2504.02605) (ByteDance, April 2025; 1,632 instances, 9 models, 7 languages), [aider polyglot leaderboard](https://aider.chat/docs/leaderboards/) (225 Exercism problems, 6 languages).
