# Experiment Run Checklist

## Tier 1 — High Impact
- [ ] **interaction-persona-politeness** (4,320 runs) — factorial of persona + politeness
- [ ] **verification-instructions** (5,400 runs) — "run tests and fix" vs vague verification
- [ ] **specificity-level** (4,320 runs) — concrete vs vague instructions
- [ ] **claudemd-length-curve** (6,480 runs) — instruction length degradation curve

## Tier 2 — Medium Impact
- [ ] **planning-before-action** (5,400 runs) — task decomposition vs CoT
- [ ] **skeleton-of-thought** (4,320 runs) — architecture outlining before coding
- [ ] **step-back** (3,510 runs) — principle abstraction (DeepMind 2023)
- [ ] **overspecification-cascade** (4,320 runs) — specification rigidity vs quantity
- [ ] **anchoring** (5,760 runs) — quality expectation anchors

## Tier 3 — Low Impact / Validation
- [ ] **constraint-formatting** (4,680 runs) — XML vs markdown formatting *(needs control clarified)*
- [ ] **emotional-stakes** (6,750 runs) — motivational framing
- [ ] **factorial-cot-temperature** (720 runs) — CoT x temperature interaction
- [ ] **scoring-sensitivity** (360 runs) — pipeline validation

## Not Ready
- [ ] **instruction-ordering** (2,520 runs) — needs redesign: only 7 tasks, vague hypothesis, unclear control
