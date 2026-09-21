from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .core import GateConfig, evaluate
from .io import group_by_category, load_jsonl


def _report_dict(report):
    data = asdict(report)
    data["success_rate"] = round(data["success_rate"], 6)
    data["success_ci_low"] = round(data["success_ci_low"], 6)
    data["success_ci_high"] = round(data["success_ci_high"], 6)
    data["baseline_avg_cost_usd"] = round(data["baseline_avg_cost_usd"], 6)
    data["candidate_raw_avg_cost_usd"] = round(data["candidate_raw_avg_cost_usd"], 6)
    data["candidate_adjusted_avg_cost_usd"] = round(data["candidate_adjusted_avg_cost_usd"], 6)
    data["savings_pct"] = round(data["savings_pct"], 6)
    return data


def _print_human(report) -> None:
    print(report.decision)
    print(f"category: {report.category}")
    print(f"models: {report.baseline_model} -> {report.candidate_model}")
    print(f"samples: {report.samples}")
    print(
        f"verified success: {report.successes}/{report.samples} "
        f"({report.success_rate:.1%}, 95% CI {report.success_ci_low:.1%}-{report.success_ci_high:.1%})"
    )
    print(f"baseline avg cost: ${report.baseline_avg_cost_usd:.4f}/task")
    print(f"candidate raw avg cost: ${report.candidate_raw_avg_cost_usd:.4f}/task")
    print(f"candidate adjusted avg cost: ${report.candidate_adjusted_avg_cost_usd:.4f}/task")
    print(f"adjusted savings: {report.savings_pct:.1%}")
    print(f"reason: {report.reason}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-model-gate",
        description="Evidence-based model displacement decisions for coding agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="Evaluate replay results from a JSONL file")
    verify.add_argument("path")
    verify.add_argument("--min-samples", type=int, default=20)
    verify.add_argument("--min-success-rate", type=float, default=0.95)
    verify.add_argument("--min-savings-pct", type=float, default=0.20)
    verify.add_argument("--json", action="store_true", dest="as_json")

    audit = sub.add_parser("audit", help="Evaluate every category/model pair in a JSONL file")
    audit.add_argument("path")
    audit.add_argument("--min-samples", type=int, default=20)
    audit.add_argument("--min-success-rate", type=float, default=0.95)
    audit.add_argument("--min-savings-pct", type=float, default=0.20)
    audit.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = GateConfig(
        min_samples=args.min_samples,
        min_success_rate=args.min_success_rate,
        min_savings_pct=args.min_savings_pct,
    )
    rows = load_jsonl(args.path)

    if args.command == "verify":
        report = evaluate(rows, config)
        if args.as_json:
            print(json.dumps(_report_dict(report), indent=2, sort_keys=True))
        else:
            _print_human(report)
        return 0

    reports = [evaluate(group, config) for group in group_by_category(rows).values()]
    reports.sort(key=lambda r: (r.decision != "SAFE_TO_DOWNGRADE", -r.savings_pct, r.category))
    if args.as_json:
        print(json.dumps([_report_dict(r) for r in reports], indent=2, sort_keys=True))
    else:
        for i, report in enumerate(reports):
            if i:
                print("\n---\n")
            _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
