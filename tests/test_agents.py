import unittest

from agent_model_gate.agents import (
    AgentUsage,
    estimate_cost_usd,
    parse_claude_json,
    parse_codex_jsonl,
)


class AgentAdapterTests(unittest.TestCase):
    def test_parse_codex_jsonl_usage(self):
        payload = "\n".join(
            [
                '{"type":"thread.started","thread_id":"abc"}',
                '{"type":"turn.completed","usage":{"input_tokens":24763,"cached_input_tokens":24448,"output_tokens":122,"reasoning_output_tokens":7}}',
            ]
        )
        usage = parse_codex_jsonl(payload)
        self.assertEqual(usage.input_tokens, 24763)
        self.assertEqual(usage.cached_input_tokens, 24448)
        self.assertEqual(usage.output_tokens, 122)
        self.assertEqual(usage.reasoning_output_tokens, 7)

    def test_parse_claude_json_cost_and_usage(self):
        payload = '{"type":"result","total_cost_usd":0.003,"usage":{"input_tokens":1000,"output_tokens":200}}'
        usage, cost = parse_claude_json(payload)
        self.assertEqual(usage.input_tokens, 1000)
        self.assertEqual(usage.output_tokens, 200)
        self.assertEqual(cost, 0.003)

    def test_estimate_cost_respects_cached_input(self):
        usage = AgentUsage(input_tokens=1000, cached_input_tokens=800, output_tokens=100)
        cost = estimate_cost_usd(
            usage,
            input_price_per_million=10.0,
            cached_input_price_per_million=1.0,
            output_price_per_million=20.0,
        )
        self.assertAlmostEqual(cost, 0.0048)


if __name__ == "__main__":
    unittest.main()
