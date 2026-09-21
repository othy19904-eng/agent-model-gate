import sys
import tempfile
import unittest
from pathlib import Path

from agent_model_gate.replay import append_jsonl, replay_once


class ReplayTests(unittest.TestCase):
    def test_candidate_is_run_in_copy_and_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "source"
            repo.mkdir()
            (repo / "value.txt").write_text("before", encoding="utf-8")

            candidate = f'{sys.executable} -c "from pathlib import Path; Path(\'value.txt\').write_text(\'after\')"'
            verify = f'{sys.executable} -c "from pathlib import Path; raise SystemExit(0 if Path(\'value.txt\').read_text() == \'after\' else 1)"'
            row = replay_once(
                repo=repo,
                task_id="t1",
                category="edit",
                baseline_model="frontier",
                candidate_model="cheap",
                baseline_cost_usd=2.0,
                candidate_cost_usd=0.5,
                candidate_command=candidate,
                verify_command=verify,
                timeout_seconds=30,
            )

            self.assertTrue(row["candidate_verified"])
            self.assertEqual((repo / "value.txt").read_text(encoding="utf-8"), "before")

    def test_failed_candidate_skips_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "source"
            repo.mkdir()
            candidate = f'{sys.executable} -c "raise SystemExit(3)"'
            verify = f'{sys.executable} -c "raise SystemExit(0)"'
            row = replay_once(
                repo=repo,
                task_id="t2",
                category="edit",
                baseline_model="frontier",
                candidate_model="cheap",
                baseline_cost_usd=2.0,
                candidate_cost_usd=0.5,
                candidate_command=candidate,
                verify_command=verify,
                timeout_seconds=30,
            )
            self.assertFalse(row["candidate_verified"])
            self.assertIsNone(row["verifier_command"])

    def test_append_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            append_jsonl(path, {"task_id": "t1"})
            self.assertIn('"task_id": "t1"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
