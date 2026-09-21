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

## Install

```bash
python -m pip install -e .
```

## Try the decision engine

```bash
agent-model-gate verify examples/sample_results.jsonl
```

The included sample deliberately returns `UNKNOWN`: 49/50 replays pass and adjusted savings are large, but the 95% confidence lower bound is still below the default 95% quality floor.

## Run a real coding-agent replay

`replay-agent` supports Codex and Claude Code. It copies the target repository to a temporary directory, lets the coding agent edit that copy, then runs a deterministic verifier.

### Codex

Codex exposes token usage in `codex exec --json`. Pass current token prices explicitly so Agent Model Gate does not hard-code pricing that can go stale.

```bash
agent-model-gate replay-agent \
  --agent codex \
  --repo examples/real_replay_fixture \
  --task-id fixture-001 \
  --category bug-fix \
  --baseline-model '<frontier-model>' \
  --candidate-model '<candidate-model>' \
  --baseline-cost-usd 1.00 \
  --prompt-file examples/real_replay_fixture/task.txt \
  --verify-command 'python -m unittest -q' \
  --input-price-per-million '<current-input-price>' \
  --cached-input-price-per-million '<current-cached-input-price>' \
  --output-price-per-million '<current-output-price>' \
  --escalation-cost-usd 1.00 \
  --output replays.jsonl
```

### Claude Code

Claude Code's JSON output can include `total_cost_usd`, so an explicit candidate price is usually unnecessary:

```bash
agent-model-gate replay-agent \
  --agent claude \
  --repo examples/real_replay_fixture \
  --task-id fixture-001 \
  --category bug-fix \
  --baseline-model '<frontier-model>' \
  --candidate-model '<candidate-model>' \
  --baseline-cost-usd 1.00 \
  --prompt-file examples/real_replay_fixture/task.txt \
  --verify-command 'python -m unittest -q' \
  --escalation-cost-usd 1.00 \
  --output replays.jsonl
```

For the Claude adapter, Bash is explicitly disallowed during the agent step; tests run separately as the verifier. Codex is invoked with its `workspace-write` sandbox.

The temporary-copy mechanism protects the original working tree from edits, but it is not a substitute for OS/container isolation. Run coding agents only in environments you trust.

## Audit accumulated evidence

After collecting enough replays:

```bash
agent-model-gate verify replays.jsonl
```

or, for several categories/model pairs:

```bash
agent-model-gate audit replays.jsonl
```

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

When `candidate_verified` is false, adjusted economics include candidate cost plus escalation/rework costs.

## Decision model

Defaults:

- minimum samples: `20`
- minimum verified success rate: `95%`
- minimum adjusted savings: `20%`
- confidence: Wilson 95% interval

A downgrade is considered safe only when the **lower bound** of the success confidence interval clears the quality floor and adjusted savings clear the savings floor.

## What this is not

Agent Model Gate is not a replacement for a request router. A future version may export routing policies **after** replay evidence proves them.

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

- paired baseline/candidate agent replay
- adapters for historical Claude Code / Codex traces
- stronger verifier adapters (pytest, npm test, build, lint, typecheck)
- task clustering/category inference
- GitHub Action report
- routing-policy export only after offline evidence exists

## Status

`0.1.0` is an experimental research/MVP release. The goal is to falsify the product hypothesis quickly with real coding-agent replays.

## License

MIT
