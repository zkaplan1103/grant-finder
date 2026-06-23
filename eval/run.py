"""Run the Verify-agent eval and print/write a report.

  python -m eval.run                 # live API (needs ANTHROPIC_API_KEY)
  python -m eval.run --json out.json # also write a machine-readable report
  python -m eval.run --judge         # score with the LLM-judge matcher (costs more)

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
from eval.scorer import Matcher, Report, score_case, token_matcher


def run(client: LLMClient, matcher: Matcher = token_matcher) -> Report:
    agent = VerifyAgent(client)
    report = Report()
    for case in load_cases():
        draft = case.to_draft()
        try:
            result = agent.verify(case.profile, case.opportunity, draft)
            flags: List[UnsupportedClaim] = result.failures
            cs = score_case(case, flags, matcher)
        except Exception as exc:  # a crashed case is a real failure mode — record it
            cs = score_case(case, [], matcher)
            cs.errored = True
            cs.false_alarms.append(f"ERROR: {type(exc).__name__}: {exc}")
        report.cases.append(cs)
    return report


# Difficulty tiers, easiest first. Cases tagged with any of these are reported
# as their own row; the order here is the print order.
_TIER_ORDER = ["obvious", "adversarial", "hard"]


def _metrics_block(label: str, r: Report) -> None:
    print(f"  [{label}]  P {r.precision:.0%}  R {r.recall:.0%}  F1 {r.f1:.0%}"
          f"   (TP {r.tp} FP {r.fp} FN {r.fn} TN {r.tn})")


def print_report(report: Report) -> None:
    print("\n=== Verify Agent — Hallucination Detection Eval ===\n")
    print(f"{'case':<42} {'TP':>3} {'FP':>3} {'FN':>3} {'TN':>3}")
    print("-" * 58)
    for c in report.cases:
        flag = " !" if (c.fn or c.errored) else ""
        print(f"{c.name:<42} {c.tp:>3} {c.fp:>3} {c.fn:>3} {c.tn:>3}{flag}")
    print("-" * 58)
    # Per-tier split is the headline: "obvious" is the easy baseline, "hard" is
    # where the verifier is meant to break. Report every tier present, in order.
    width = max((len(t) for t in _TIER_ORDER), default=7)
    for tier in _TIER_ORDER:
        sub = report.subset(tier)
        if sub.cases:
            _metrics_block(f"{tier:<{width}}", sub)
    _metrics_block(f"{'OVERALL':<{width}}", report)
    print()
    print("  P = precision (of flags raised, how many were real)")
    print("  R = recall    (of planted hallucinations, how many were caught)")
    misses = [(c.difficulty, t) for c in report.cases for t in c.missed_tags]
    if misses:
        print(f"\n  Hallucinations that slipped through ({len(misses)}):")
        for diff, t in misses:
            print(f"    - [{diff}] {t}")
    print()


def _tier_dict(r: Report) -> dict:
    return {
        "tp": r.tp, "fp": r.fp, "fn": r.fn, "tn": r.tn,
        "precision": r.precision, "recall": r.recall, "f1": r.f1,
    }


def to_dict(report: Report) -> dict:
    return {
        "overall": _tier_dict(report),
        "by_difficulty": {
            tier: _tier_dict(report.subset(tier))
            for tier in _TIER_ORDER
            if report.subset(tier).cases
        },
        "cases": [
            {
                "name": c.name, "difficulty": c.difficulty,
                "tp": c.tp, "fp": c.fp, "fn": c.fn, "tn": c.tn,
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
    parser.add_argument("--judge", action="store_true",
                        help="Score with the LLM-judge matcher (meaning, not tokens; costs more).")
    args = parser.parse_args(argv)

    client = build_default_client()
    if client is None:
        print("ANTHROPIC_API_KEY not set — cannot run the live eval.", file=sys.stderr)
        return 2

    matcher = token_matcher
    if args.judge:
        from eval.judge import make_judge_matcher
        matcher = make_judge_matcher(client)
        print("(scoring with LLM-judge matcher)")

    report = run(client, matcher)
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
