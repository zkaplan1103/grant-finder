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
import math
import statistics
import sys
from fnmatch import fnmatch
from typing import List, Optional

from app.agents import VerifyAgent
from app.agents.client import LLMClient, build_default_client
from app.models import UnsupportedClaim
from eval.cases import load_cases
from eval.scorer import Matcher, Report, score_case, token_matcher


def run(
    client: LLMClient,
    matcher: Matcher = token_matcher,
    case_filter: Optional[str] = None,
    cases: Optional[List] = None,
) -> Report:
    agent = VerifyAgent(client)
    report = Report()
    case_list = cases if cases is not None else load_cases()
    if case_filter:
        case_list = [c for c in case_list if fnmatch(c.name, case_filter)]
    for case in case_list:
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


def _smoke_cases() -> list[str]:
    """Pick up to 5 representative case names (1 per tier if possible)."""
    cases = load_cases()
    seen_tiers: dict[str, str] = {}
    for c in cases:
        if c.difficulty not in seen_tiers:
            seen_tiers[c.difficulty] = c.name
    names = list(seen_tiers.values())
    # Fill to 5 from remaining cases
    for c in cases:
        if len(names) >= 5:
            break
        if c.name not in names:
            names.append(c.name)
    return names


def _ci95(values: list[float]) -> tuple[float, float, float]:
    """Return (mean, ci_low, ci_high) for a list of values using t-distribution."""
    n = len(values)
    mu = statistics.mean(values)
    if n < 2:
        return mu, mu, mu
    sd = statistics.stdev(values)
    # t critical value for 95% CI, two-tailed, df=n-1
    # Using a lookup table for small n; for larger n, approximate with 1.96.
    _T_TABLE = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042,
    }
    df = n - 1
    t_crit = _T_TABLE.get(df, 1.96)
    if df not in _T_TABLE and df < 30:
        # Interpolate from nearest lower key
        keys = sorted(k for k in _T_TABLE if k <= df)
        t_crit = _T_TABLE[keys[-1]] if keys else 1.96
    margin = t_crit * sd / math.sqrt(n)
    return mu, mu - margin, mu + margin


def _run_smoke(client: LLMClient, matcher: Matcher = token_matcher) -> Report:
    """Run only the smoke-test subset (5 representative cases)."""
    # ponytail: duplicates run()'s loop body; deduplicating requires changing run()'s
    # signature for a name-set filter, which is more complexity than the duplication.
    smoke_names = set(_smoke_cases())
    agent = VerifyAgent(client)
    report = Report()
    for case in load_cases():
        if case.name not in smoke_names:
            continue
        draft = case.to_draft()
        try:
            result = agent.verify(case.profile, case.opportunity, draft)
            flags: List[UnsupportedClaim] = result.failures
            cs = score_case(case, flags, matcher)
        except Exception as exc:
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


def _print_multi_run(runs: list[Report]) -> None:
    """Print mean P/R/F1 with 95% CI across multiple runs."""
    ps = [r.precision for r in runs]
    rs = [r.recall for r in runs]
    f1s = [r.f1 for r in runs]
    n = len(runs)
    print(f"\n=== Multi-run summary ({n} runs) ===\n")
    for label, vals in [("Precision", ps), ("Recall", rs), ("F1", f1s)]:
        mu, lo, hi = _ci95(vals)
        print(f"  {label:<10} {mu:.3f}  [{lo:.3f}, {hi:.3f}]  (95% CI)")
    print()


def _multi_run_dict(reports: list[Report]) -> dict:
    """Build a JSON-serializable multi-run summary."""
    ps = [r.precision for r in reports]
    rs = [r.recall for r in reports]
    f1s = [r.f1 for r in reports]
    p_mu, p_lo, p_hi = _ci95(ps)
    r_mu, r_lo, r_hi = _ci95(rs)
    f_mu, f_lo, f_hi = _ci95(f1s)
    return {
        "runs": len(reports),
        "precision": {"mean": p_mu, "ci_low": p_lo, "ci_high": p_hi},
        "recall": {"mean": r_mu, "ci_low": r_lo, "ci_high": r_hi},
        "f1": {"mean": f_mu, "ci_low": f_lo, "ci_high": f_hi},
        "per_run": [to_dict(r) for r in reports],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify-agent hallucination eval.")
    parser.add_argument("--json", metavar="PATH", help="Write a JSON report to PATH.")
    parser.add_argument("--min-recall", type=float, default=0.0,
                        help="Exit non-zero if recall is below this (for CI gating).")
    parser.add_argument("--judge", action="store_true",
                        help="Score with the LLM-judge matcher (meaning, not tokens; costs more).")
    parser.add_argument("--cases", metavar="GLOB",
                        help="Only run cases whose name matches this glob (e.g. 'hard/*').")
    parser.add_argument("--runs", type=int, default=1,
                        help="Repeat the eval N times and report mean with 95%% CI.")
    parser.add_argument("--smoke", action="store_true",
                        help="Run only 5 representative cases (1 per tier if possible).")
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

    case_filter = args.cases

    reports: list[Report] = []
    for i in range(args.runs):
        if args.smoke and not case_filter:
            report = _run_smoke(client, matcher)
        else:
            report = run(client, matcher, case_filter=case_filter)
        reports.append(report)
        if args.runs > 1:
            print(f"--- run {i + 1}/{args.runs}: "
                  f"P={report.precision:.2%} R={report.recall:.2%} F1={report.f1:.2%}")

    report = reports[-1]  # last run for detailed output
    print_report(report)

    if args.runs > 1:
        _print_multi_run(reports)

    if args.json:
        data = _multi_run_dict(reports) if args.runs > 1 else to_dict(report)
        with open(args.json, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Wrote {args.json}")

    if report.recall < args.min_recall:
        print(f"FAIL: recall {report.recall:.2%} < required {args.min_recall:.2%}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
