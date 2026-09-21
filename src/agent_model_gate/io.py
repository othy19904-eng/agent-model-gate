from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .core import ReplayResult

_REQUIRED = {
    "task_id",
    "category",
    "baseline_model",
    "candidate_model",
    "baseline_cost_usd",
    "candidate_cost_usd",
    "candidate_verified",
}


def load_jsonl(path: str | Path) -> list[ReplayResult]:
    path = Path(path)
    rows: list[ReplayResult] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            data = json.loads(raw)
            missing = _REQUIRED - data.keys()
            if missing:
                raise ValueError(f"{path}:{line_no}: missing fields: {', '.join(sorted(missing))}")
            rows.append(
                ReplayResult(
                    task_id=str(data["task_id"]),
                    category=str(data["category"]),
                    baseline_model=str(data["baseline_model"]),
                    candidate_model=str(data["candidate_model"]),
                    baseline_cost_usd=float(data["baseline_cost_usd"]),
                    candidate_cost_usd=float(data["candidate_cost_usd"]),
                    candidate_verified=bool(data["candidate_verified"]),
                    escalation_cost_usd=float(data.get("escalation_cost_usd", 0.0)),
                    rework_cost_usd=float(data.get("rework_cost_usd", 0.0)),
                    baseline_verified=bool(data.get("baseline_verified", True)),
                )
            )
    return rows


def group_by_category(rows: Iterable[ReplayResult]) -> dict[tuple[str, str, str], list[ReplayResult]]:
    grouped: dict[tuple[str, str, str], list[ReplayResult]] = {}
    for row in rows:
        key = (row.category, row.baseline_model, row.candidate_model)
        grouped.setdefault(key, []).append(row)
    return grouped
