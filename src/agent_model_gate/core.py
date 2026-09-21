from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Literal

Decision = Literal["SAFE_TO_DOWNGRADE", "KEEP_FRONTIER", "UNKNOWN"]


@dataclass(frozen=True)
class ReplayResult:
    task_id: str
    category: str
    baseline_model: str
    candidate_model: str
    baseline_cost_usd: float
    candidate_cost_usd: float
    candidate_verified: bool
    escalation_cost_usd: float = 0.0
    rework_cost_usd: float = 0.0
    baseline_verified: bool = True

    @property
    def adjusted_candidate_cost_usd(self) -> float:
        if self.candidate_verified:
            return self.candidate_cost_usd
        return (
            self.candidate_cost_usd
            + self.escalation_cost_usd
            + self.rework_cost_usd
        )


@dataclass(frozen=True)
class GateConfig:
    min_samples: int = 20
    min_success_rate: float = 0.95
    min_savings_pct: float = 0.20
    confidence_z: float = 1.96


@dataclass(frozen=True)
class GateReport:
    decision: Decision
    samples: int
    successes: int
    success_rate: float
    success_ci_low: float
    success_ci_high: float
    baseline_avg_cost_usd: float
    candidate_raw_avg_cost_usd: float
    candidate_adjusted_avg_cost_usd: float
    savings_pct: float
    baseline_model: str
    candidate_model: str
    category: str
    reason: str


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = z * sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def evaluate(results: Iterable[ReplayResult], config: GateConfig | None = None) -> GateReport:
    config = config or GateConfig()
    rows = list(results)
    if not rows:
        raise ValueError("No replay results supplied")

    category = rows[0].category
    baseline_model = rows[0].baseline_model
    candidate_model = rows[0].candidate_model

    for row in rows:
        if row.category != category:
            raise ValueError("All replay results must share one category")
        if row.baseline_model != baseline_model or row.candidate_model != candidate_model:
            raise ValueError("All replay results must share the same model pair")
        if min(row.baseline_cost_usd, row.candidate_cost_usd, row.escalation_cost_usd, row.rework_cost_usd) < 0:
            raise ValueError("Costs cannot be negative")

    n = len(rows)
    successes = sum(1 for row in rows if row.candidate_verified)
    success_rate = successes / n
    ci_low, ci_high = wilson_interval(successes, n, config.confidence_z)

    baseline_avg = sum(row.baseline_cost_usd for row in rows) / n
    candidate_raw_avg = sum(row.candidate_cost_usd for row in rows) / n
    candidate_adjusted_avg = sum(row.adjusted_candidate_cost_usd for row in rows) / n

    if baseline_avg <= 0:
        savings_pct = 0.0
    else:
        savings_pct = (baseline_avg - candidate_adjusted_avg) / baseline_avg

    if n < config.min_samples:
        decision: Decision = "UNKNOWN"
        reason = f"Need at least {config.min_samples} samples; only {n} supplied."
    elif ci_low >= config.min_success_rate and savings_pct >= config.min_savings_pct:
        decision = "SAFE_TO_DOWNGRADE"
        reason = (
            f"Verified success lower bound {ci_low:.1%} meets the {config.min_success_rate:.1%} floor "
            f"and adjusted savings {savings_pct:.1%} meet the {config.min_savings_pct:.1%} minimum."
        )
    elif ci_high < config.min_success_rate or savings_pct <= 0:
        decision = "KEEP_FRONTIER"
        problems: list[str] = []
        if ci_high < config.min_success_rate:
            problems.append(
                f"verified success upper bound {ci_high:.1%} is below the {config.min_success_rate:.1%} floor"
            )
        if savings_pct <= 0:
            problems.append(f"adjusted economics do not save money ({savings_pct:.1%})")
        reason = "; ".join(problems) + "."
    else:
        decision = "UNKNOWN"
        reason = (
            "Evidence is not strong enough for a safe downgrade and not strong enough to reject the candidate. "
            "Collect more replay samples or improve the verifier."
        )

    return GateReport(
        decision=decision,
        samples=n,
        successes=successes,
        success_rate=success_rate,
        success_ci_low=ci_low,
        success_ci_high=ci_high,
        baseline_avg_cost_usd=baseline_avg,
        candidate_raw_avg_cost_usd=candidate_raw_avg,
        candidate_adjusted_avg_cost_usd=candidate_adjusted_avg,
        savings_pct=savings_pct,
        baseline_model=baseline_model,
        candidate_model=candidate_model,
        category=category,
        reason=reason,
    )
