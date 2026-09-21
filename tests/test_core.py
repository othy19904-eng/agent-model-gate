import unittest

from agent_model_gate.core import GateConfig, ReplayResult, evaluate


def row(i, ok=True, baseline=4.0, candidate=0.8, escalation=4.0, rework=0.0):
    return ReplayResult(
        task_id=str(i),
        category="unit-tests",
        baseline_model="frontier",
        candidate_model="mid",
        baseline_cost_usd=baseline,
        candidate_cost_usd=candidate,
        candidate_verified=ok,
        escalation_cost_usd=escalation,
        rework_cost_usd=rework,
    )


class GateTests(unittest.TestCase):
    def test_unknown_when_sample_is_small(self):
        report = evaluate([row(i) for i in range(5)])
        self.assertEqual(report.decision, "UNKNOWN")

    def test_safe_when_success_and_savings_are_strong(self):
        rows = [row(i, ok=True) for i in range(100)]
        report = evaluate(rows)
        self.assertEqual(report.decision, "SAFE_TO_DOWNGRADE")
        self.assertGreater(report.savings_pct, 0.7)

    def test_keep_frontier_when_failures_destroy_economics(self):
        rows = [row(i, ok=(i < 10), candidate=1.0, escalation=4.0, rework=1.0) for i in range(40)]
        report = evaluate(rows)
        self.assertEqual(report.decision, "KEEP_FRONTIER")
        self.assertLessEqual(report.savings_pct, 0)

    def test_unknown_when_quality_is_promising_but_not_proven(self):
        rows = [row(i, ok=(i < 19), candidate=0.8) for i in range(20)]
        cfg = GateConfig(min_success_rate=0.80, min_savings_pct=0.20)
        report = evaluate(rows, cfg)
        self.assertEqual(report.decision, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
