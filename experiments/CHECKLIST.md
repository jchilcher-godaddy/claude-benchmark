# Experiment Run Checklist

## Capstone v2 — Comprehensive Cross-Language (21,600 runs)
- [x] **capstone-v2** — 10 variants × 48 tasks × 3 models × 15 reps. 20,499 clean scored. Kitchen-sink rescues JS (+7.25); WHAT/HOW flips by language; framing direction is noise; verification redundant with persona; persona+CoT dilutive in JS.

## Tier 0 — Presentation Gaps (blocks claims in talk)
- [x] **outcome-vs-implementation** — ⚡ CLOSED by capstone-v2. WHAT/HOW flips: JS wants HOW (+5.72), C# wants WHAT (+7.94), Python/Go neutral.
- [x] **positive-vs-negative-framing** — ⚡ CLOSED by capstone-v2. Framing direction is noise (no sig. difference in 20,499 runs). Original +0.66 was confounded.
- [x] **optimal-stack-cross-language** — ⚡ CLOSED by capstone-v2. go-cs-stack +0.36 (n.s.); python-js-stack +1.22 (p=0.016).
- [x] **front-load-vs-iterate** — PARTIALLY CLOSED. Kitchen-sink (front-loading proxy) is +0.77 Python but +7.25 JS — language-dependent, not universal anti-pattern.
- [x] **targeted-constraints** — CLOSED. Completed as standalone experiment (brief docstrings -0.33 n.s., -19% cost).
- [x] **interaction-persona-politeness** — ⚡ CLOSED by capstone-v2. Persona+CoT dilutive in JS (-2.40), synergistic in Go/C#.

## Tier 1 — High Impact (closes gaps in best-practices doc)
- [x] **language-kitchen-sink** (12,960 runs) — CLOSED. Universal kitchen-sink (79.22) beats all language-specific variants. C#-specific rules also hurt C# (-1.68). Sonnet+C# collapses 17-18 pts.
- [x] **verification-instructions** (10,800 runs) — CLOSED. Helps JS (+3.2, p=0.0002) but not Python; redundant with persona (capstone-v2).
- [ ] **instruction-position-in-claudemd** (10,800 runs) — READY. Primacy vs recency vs reinforcement. Updated to 48 cross-language tasks, 15 reps, language-agnostic critical instruction.
- [x] **multi-turn-conversation** (12,960 runs) — CLOSED. Unconditional self-review degrades quality (-0.38 two-turn, -5.09 three-turn). Front-loaded instructions beat iteration at half the tokens. **Caveat:** blind self-review, not closed-loop with test feedback. v2 planned.
- [ ] **multi-turn-conversation-v2** (10,800 runs) — NEW. Closed-loop iteration: run tests between turns, inject results into follow-up. Conditional (skip follow-up if tests pass). Tests whether evidence-based iteration beats single-turn. **Requires framework support: `run_tests_between_turns` flag in worker.**
- [ ] **architecture-decision-records** (10,800 runs) — NEW. Project facts vs ADR rationale vs generic instructions at matched token counts. Tests an undocumented recommendation.
- [ ] **static-vs-dynamic-context** (12,960 runs) — READY. Task-relevant vs generic context. Updated to 48 cross-language tasks, 15 reps.

## Tier 2 — Medium Impact
- [ ] **instruction-topic-density** (12,960+ runs) — READY. Single-topic focus vs multi-topic at same token count. Updated to 48 tasks, 15 reps.
- [ ] **skeleton-of-thought** (8,640 runs) — READY. Architecture outlining before coding. Updated to 48 tasks, 15 reps, language-agnostic prompts. Original Python-only showed -7.7 on refactoring.
- [ ] **step-back** (8,640+ runs) — READY. Principle abstraction (DeepMind 2023). Updated to 48 tasks, 15 reps.
- [ ] **emotional-stakes** (10,800 runs) — READY. Consequence framing, tip incentives, accountability. Updated to 48 tasks, 15 reps.
- [ ] **anchoring** (8,640 runs) — READY. Quality expectation anchors ("FAANG-grade code"). Updated to 48 tasks, 15 reps. Backs anti-pattern #4.
- [ ] **output-compression** (15,120 runs) — NEW. Caveman-style output compression: bare → terse → structured → ultra. Plus instruction compression (verbose vs compressed rules) and code-adapted hybrid. Tests cheapest cost-per-token at optimal quality gate.
- [ ] **specificity-level** (4,320 runs) — concrete vs vague instructions
- [ ] **claudemd-length-curve** (6,480 runs) — instruction length degradation curve
- [ ] **planning-before-action** (5,400 runs) — task decomposition vs CoT
- [ ] **overspecification-cascade** (4,320 runs) — specification rigidity vs quantity

## Tier 3 — Low Impact / Validation
- [ ] **constraint-formatting** (4,680 runs) — XML vs markdown formatting *(needs control clarified)*
- [ ] **factorial-cot-temperature** (720 runs) — CoT x temperature interaction
- [ ] **scoring-sensitivity** (360 runs) — pipeline validation

## Not Ready
- [ ] **instruction-ordering** (2,520 runs) — needs redesign: only 7 tasks, vague hypothesis, unclear control

## Modernization Status
All Tier 1-2 experiments have been updated to the current standard:
- 48 cross-language tasks (12 each: Python, Go, JS, C#)
- 15 reps per cell
- 3 models (haiku, sonnet, opus)
- `profiles = ["empty"]`
- Language-agnostic prompt text (no Python-specific references in cross-language experiments)
