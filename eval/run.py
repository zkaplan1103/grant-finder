"""Run the Verify-agent eval and print/write a report.

  python -m eval.run                 # live API (needs ANTHROPIC_API_KEY)
  python -m eval.run --json out.json # also write a machine-readable report

Exit code is non-zero if recall falls below --min-recall (default 0.0, i.e. report
only), so this can gate CI once you trust the numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from app.agents import VerifyAgent
from app.agents.client import LLMClient, build_default_client
from app.models import UnsupportedClaim
from eval.cases import load_cases
from eval.scorer import Report, score_case


def run(client: LLMClient) -> Report:
    agent = VerifyAgent(client)
    report = Report()
    for case in load_cases():
        draft = case.to_draft()
        try:
            result = agent.verify(case.profile, case.opportunity, draft)
            flags: List[UnsupportedClaim] = result.failures
            cs = score_case(case, flags)
        except Exception as exc:  # a crashed case is a real failure mode — record it
            cs = score_case(case, [])
            cs.errored = True
            cs.false_alarms.append(f"ERROR: {type(exc).__name__}: {exc}")
        report.cases.append(cs)
    return report


def print_report(report: Report) -> None:
    print("\n=== Verify Agent — Hallucination Detection Eval ===\n")
    print(f"{'case':<40} {'TP':>3} {'FP':>3} {'FN':>3} {'TN':>3}")
    print("-" * 56)
    for c in report.cases:
        flag = " !" if (c.fn or c.errored) else ""
        print(f"{c.name:<40} {c.tp:>3} {c.fp:>3} {c.fn:>3} {c.tn:>3}{flag}")
    print("-" * 56)
    print(f"{'TOTAL':<40} {report.tp:>3} {report.fp:>3} {report.fn:>3} {report.tn:>3}")
    print()
    print(f"  Precision: {report.precision:.2%}   (of flags raised, how many were real)")
    print(f"  Recall:    {report.recall:.2%}   (of planted claims, how many were caught)")
    print(f"  F1:        {report.f1:.2%}")
    misses = [t for c in report.cases for t in c.missed_tags]
    if misses:
        print(f"\n  Hallucinations that slipped through ({len(misses)}):")
        for t in misses:
            print(f"    - {t}")
    print()


def to_dict(report: Report) -> dict:
    return {
        "totals": {
            "tp": report.tp, "fp": report.fp, "fn": report.fn, "tn": report.tn,
            "precision": report.precision, "recall": report.recall, "f1": report.f1,
        },
        "cases": [
            {
                "name": c.name, "tp": c.tp, "fp": c.fp, "fn": c.fn, "tn": c.tn,
                "missed": c.missed_tags, "false_alarms": c.false_alarms,
                "errored": c.errored,
            }
            for c in report.cases
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify-agent hallucination eval.")
    parser.add_argument("--json", metavar="PATH", help="Write a JSON report to PATH.")
    parser.add_argument("--min-recall", type=float, default=0.0,
                        help="Exit non-zero if recall is below this (for CI gating).")
    args = parser.parse_args(argv)

    client = build_default_client()
    if client is None:
        print("ANTHROPIC_API_KEY not set — cannot run the live eval.", file=sys.stderr)
        return 2

    report = run(client)
    print_report(report)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(to_dict(report), f, indent=2)
        print(f"Wrote {args.json}")

    if report.recall < args.min_recall:
        print(f"FAIL: recall {report.recall:.2%} < required {args.min_recall:.2%}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
