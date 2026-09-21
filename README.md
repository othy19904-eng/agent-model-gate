# Agent Model Gate

**Evidence before model downgrade.**

Agent Model Gate is an open-source decision layer for AI coding agents. It does **not** route live requests and it does **not** claim that the cheapest model is the best model.

It answers a narrower, auditable question:

> Can this class of coding tasks move from an expensive frontier model to a cheaper model **without losing verified task success after retries, escalation, and rework are counted**?

The output is deliberately small:

- `SAFE_TO_DOWNGRADE`
- `KEEP_FRONTIER`
- `UNKNOWN`

## Why

Token-price comparisons can be misleading. A cheaper model that fails more often may trigger retries, frontier escalation, developer interruption, or rework. The real unit is the **completed verified task**, not the input token.

Agent Model Gate evaluates replay evidence and includes failure/escalation cost before recommending a downgrade.

## v0.1 scope

This first version is intentionally offline and local:

1. Run or collect candidate-model replays outside production.
2. Verify outcomes with deterministic checks such as tests/build/lint/typecheck.
3. Export one JSONL row per replay.
4. Let Agent Model Gate calculate the quality confidence interval and adjusted economics.

No proxy. No SaaS. No source-code upload.

## Install

```bash
python -m pip install -e .
```

## Try it

```bash
agent-model-gate verify examples/sample_results.jsonl
```

Example output from the included sample:

```text
UNKNOWN
category: test-generation
models: frontier-model -> mid-tier-model
samples: 50
verified success: 49/50 (98.0%, 95% CI 89.5%-99.6%)
baseline avg cost: $2.8400/task
candidate adjusted avg cost: $0.9698/task
adjusted savings: 65.9%
reason: evidence is promising, but the confidence lower bound does not yet clear the 95% quality floor.
```

Machine-readable output:

```bash
agent-model-gate verify examples/sample_results.jsonl --json
```

Audit multiple task categories/model pairs:

```bash
agent-model-gate audit my-replays.jsonl
```

## Capture one replay

The `replay` command runs a candidate command inside a **temporary copy** of the repository, then runs an executable verifier and appends the evidence as JSONL:

```bash
agent-model-gate replay \
  --repo . \
  --task-id test-001 \
  --category test-generation \
  --baseline-model frontier-model \
  --candidate-model mid-tier-model \
  --baseline-cost-usd 2.84 \
  --candidate-cost-usd 0.91 \
  --candidate-command 'your-agent-command --prompt task.txt' \
  --verify-command 'python -m pytest -q' \
  --escalation-cost-usd 2.84 \
  --output replays.jsonl
```

The temporary copy protects the original working tree from candidate edits. It is **not a security sandbox**: the candidate process still has the permissions and network access of the user running it. Only run commands you trust.

## JSONL schema

Required fields:

```json
{
  "task_id": "task-001",
  "category": "test-generation",
  "baseline_model": "frontier-model",
  "candidate_model": "mid-tier-model",
  "baseline_cost_usd": 2.84,
  "candidate_cost_usd": 0.91,
  "candidate_verified": true
}
```

Optional failure-cost fields:

```json
{
  "escalation_cost_usd": 2.84,
  "rework_cost_usd": 0.15
}
```

When `candidate_verified` is false, the adjusted candidate cost includes candidate cost + escalation cost + rework cost.

## Decision model

Defaults:

- minimum samples: `20`
- minimum verified success rate: `95%`
- minimum adjusted savings: `20%`
- confidence: Wilson 95% interval

A downgrade is considered safe only when the **lower bound** of the success confidence interval clears the configured quality floor and adjusted savings clear the configured savings floor.

Otherwise the tool returns `KEEP_FRONTIER` when evidence clearly rejects the candidate, or `UNKNOWN` when the evidence is insufficient.

Thresholds are configurable:

```bash
agent-model-gate verify results.jsonl \
  --min-samples 50 \
  --min-success-rate 0.98 \
  --min-savings-pct 0.25
```

## What this is not

Agent Model Gate is not a replacement for Cursor Router, Portkey, LiteLLM, Not Diamond, or another request router. A future version may export routing policies **after** replay evidence proves them.

The design principle is:

```text
expensive task
    ↓
shadow replay
    ↓
executable verification
    ↓
economics after failure/escalation
    ↓
SAFE_TO_DOWNGRADE / KEEP_FRONTIER / UNKNOWN
```

## Roadmap

The next experiments are evidence-driven:

- adapters for Claude Code / Codex trace formats
- sandbox replay runner
- verifier adapters (`pytest`, `npm test`, build, lint, typecheck)
- cost extraction from provider usage metadata
- task clustering/category inference
- GitHub Action report
- routing-policy export only after offline evidence exists

## Security posture

The core is local-first. Repositories, traces, and source code should not need to leave the developer's machine for the decision engine to work.

## Status

`0.1.0` is an experimental research/MVP release. The goal is to falsify the product hypothesis quickly with real coding-agent replays.

## License

MIT
