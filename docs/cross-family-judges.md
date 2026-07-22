# Cross-Family LLM Judges

> Status: scaffolding implemented, not yet validated. The maintainer must
> run a cross-judge pass and compare scores before any of the findings in
> [`experiments.md`](experiments.md) can be defended against in-family-bias
> challenges.

## Why This Matters

The default LLM judge in this benchmark is **Claude Haiku 4.5** — a Claude
model judging the output of Sonnet, Opus, and Haiku itself. Reviewers of any
external publication will challenge this as in-family bias: a sibling model
may share architectural priors, prompt-format preferences, or reasoning
patterns with the models it scores, inflating or deflating scores in ways
that don't generalize.

Building support for cross-family judges (OpenAI, Google) lets the
maintainer run a validation pass and compare each variant's score
distributions across providers. If the cross-judge correlation is high,
the existing findings stand. If it diverges, that itself is a publishable
result.

## Supported Providers

| Provider  | Default Model           | Spec examples                                      | API key env var    |
|-----------|-------------------------|----------------------------------------------------|--------------------|
| Anthropic | `claude-haiku-4-5`      | `haiku`, `sonnet`, `opus`, `claude-haiku-4-5-...`  | (worker creds reused) |
| OpenAI    | `gpt-4o-2024-11-20`     | `gpt-4o`, `gpt-4-turbo`, `openai:<model-id>`       | `OPENAI_API_KEY`   |
| Google    | `gemini-2.5-pro`        | `gemini-2.5-pro`, `gemini-1.5-pro`, `gemini:<id>`  | `GOOGLE_API_KEY`   |

The default Haiku path is unchanged. Cross-family providers are opt-in via
`--judge-model`.

## Setup

### OpenAI

```bash
export OPENAI_API_KEY=sk-...
```

The `openai` SDK is already in base dependencies — no extra install step.

### Google Gemini

```bash
pip install 'claude-benchmark[gemini]'
export GOOGLE_API_KEY=...
```

The `google-generativeai` package is an **optional** dependency. The base
install does not pull it in, so users on the default Haiku path see no
extra weight.

### Anthropic (default)

No extra setup. Uses the same credentials as the benchmark workers
(AWS Bedrock by default; direct API or proxy if configured).

## Usage

### Run an experiment with a cross-family judge

```bash
claude-benchmark experiment experiments/capstone-v2.toml \
  --judge-model gpt-4o --direct-api -c 50 -y
```

```bash
claude-benchmark experiment experiments/capstone-v2.toml \
  --judge-model gemini-2.5-pro --direct-api -c 50 -y
```

### Rescore an existing results directory

This is the typical validation workflow: run the experiment once with the
default Haiku judge, then rescore the same outputs with a cross-family judge
and compare.

```bash
# 1. Original experiment (default Haiku judge)
claude-benchmark experiment experiments/capstone-v2.toml --direct-api -c 50 -y
# -> results/experiment-capstone-v2-20260513-120000

# 2. Rescore with OpenAI
claude-benchmark rescore results/experiment-capstone-v2-20260513-120000 \
  --judge-model gpt-4o --force --direct-api

# 3. Rescore with Gemini
claude-benchmark rescore results/experiment-capstone-v2-20260513-120000 \
  --judge-model gemini-2.5-pro --force --direct-api
```

The `--force` flag tells `rescore` to re-run the judge even on already-scored
runs. Each scored run JSON now records `judge_provider` and `judge_model_id`
in the LLM score block, so downstream comparison can distinguish runs scored
by different judges.

> **Note:** today's `rescore` command overwrites the previous LLM score for
> each run. If you want to preserve the original Haiku scores while adding
> a second judge's verdict, snapshot the results directory first
> (`cp -r results/exp-foo results/exp-foo-haiku`).

## How the Abstraction Works

The cross-family layer lives in `src/claude_benchmark/scoring/judges/`:

```
judges/
  __init__.py          # public API: get_judge, JudgeProvider, JudgeError
  base.py              # JudgeProvider ABC
  anthropic_judge.py   # delegates to LLMJudgeScorer's existing call path
  openai_judge.py      # OpenAI chat completions + json_schema response_format
  gemini_judge.py      # google.generativeai with response_schema (lazy import)
  registry.py          # spec -> provider class
```

The legacy `LLMJudgeScorer` continues to handle Anthropic specs through its
existing proxy > direct-API > CLI fallback chain. Non-Anthropic specs route
through `JudgeProvider.score()`. The same `JUDGE_SYSTEM_PROMPT` and
`JUDGE_OUTPUT_SCHEMA` are shared — each provider has a small shim that
translates the JSON schema into its native structured-output format
(`response_format` for OpenAI, `generation_config.response_schema` for
Gemini).

Each successfully scored run JSON now contains:

```json
{
  "scores": {
    "llm": {
      "criteria": [...],
      "average": 4.0,
      "normalized": 75.0,
      "model_used": "gpt-4o",
      "judge_provider": "openai",
      "judge_model_id": "gpt-4o-2024-11-20"
    }
  }
}
```

Downstream comparison and aggregation tooling can group by
`judge_provider` to compute per-judge score distributions.

## API Surface

```python
from claude_benchmark.scoring.judges import get_judge, JudgeProvider, JudgeError

judge: JudgeProvider = get_judge("gpt-4o")
evaluations: list[dict] = judge.score(
    prompt=user_prompt,
    system=system_prompt,
    schema=JUDGE_OUTPUT_SCHEMA,
)
```

`evaluations` is the parsed value of the `evaluations` array — each entry has
`{"criterion": str, "score": int, "reasoning": str}`. The wrapper
`LLMJudgeScorer(judge_model=...)` performs the same retry-with-explicit-prompt
logic for all providers and returns a normalized `LLMScore`.

## Validation Status

This scaffolding is implemented but **not yet validated**:

- [ ] Run the capstone experiment with `--judge-model gpt-4o`
- [ ] Run the capstone experiment with `--judge-model gemini-2.5-pro`
- [ ] Compute per-task per-variant correlation between Haiku, GPT-4o,
  and Gemini scores
- [ ] Document any systematic disagreements in `docs/experiments.md`

Until the cross-judge pass is run, every published finding carries an
implicit "Haiku-judged" caveat.
