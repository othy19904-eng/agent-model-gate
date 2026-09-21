# Contributing

Agent Model Gate is currently validating one core hypothesis: model downgrades for coding-agent tasks should be authorized by replay evidence and executable verification, not token price alone.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Keep pull requests small and tied to an observable failure mode or replay need.
