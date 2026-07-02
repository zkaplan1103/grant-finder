"""Failure analysis for eval reports.

Reads a JSON report (from eval/run.py --json) and categorizes every FN and FP
by domain and difficulty tier. Outputs a structured analysis.

Usage:
    python -m eval.analysis eval/reports/latest.json
    python -m eval.analysis --sample  # generate and analyze a sample report
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any, Dict, List, Optional


def _domain_from_name(name: str) -> str:
    """Infer domain from a case name prefix."""
    prefixes = {
        "legal": "legal",
        "med": "medical",
        "edu": "education",
    }
    lower = name.lower()
    for prefix, domain in prefixes.items():
        if prefix in lower:
            return domain
    return "solar"


def analyze(report_data: dict) -> dict:
    """Analyze a report dict and return structured findings."""
    cases_data = report_data.get("cases", [])
    if not cases_data:
        return {"error": "No cases in report."}

    fn_by_difficulty: Counter[str] = Counter()
    fp_by_difficulty: Counter[str] = Counter()
    fn_by_domain: Counter[str] = Counter()
    fp_by_domain: Counter[str] = Counter()
    total_by_difficulty: Counter[str] = Counter()
    total_by_domain: Counter[str] = Counter()

    fn_cases: List[Dict[str, Any]] = []
    fp_cases: List[Dict[str, Any]] = []

    for c in cases_data:
        name = c["name"]
        difficulty = c.get("difficulty", "unknown")
        domain = _domain_from_name(name)
        fn_count = c.get("fn", 0)
        fp_count = c.get("fp", 0)

        total_by_difficulty[difficulty] += 1
        total_by_domain[domain] += 1

        if fn_count > 0:
            fn_by_difficulty[difficulty] += fn_count
            fn_by_domain[domain] += fn_count
            fn_cases.append({
                "name": name, "difficulty": difficulty, "domain": domain,
                "fn": fn_count, "missed": c.get("missed", []),
            })

        if fp_count > 0:
            fp_by_difficulty[difficulty] += fp_count
            fp_by_domain[domain] += fp_count
            fp_cases.append({
                "name": name, "difficulty": difficulty, "domain": domain,
                "fp": fp_count, "false_alarms": c.get("false_alarms", []),
            })

    # Compute miss rates per difficulty tier.
    difficulty_miss_rates = {}
    for tier in sorted(total_by_difficulty):
        total = total_by_difficulty[tier]
        fns = fn_by_difficulty[tier]
        difficulty_miss_rates[tier] = {
            "cases": total, "fn": fns,
            "miss_rate": fns / total if total else 0.0,
        }

    # Compute false alarm rates per difficulty tier.
    difficulty_fp_rates = {}
    for tier in sorted(total_by_difficulty):
        total = total_by_difficulty[tier]
        fps = fp_by_difficulty[tier]
        difficulty_fp_rates[tier] = {
            "cases": total, "fp": fps,
            "fp_rate": fps / total if total else 0.0,
        }

    # Domain breakdown.
    domain_miss_rates = {}
    for domain in sorted(total_by_domain):
        total = total_by_domain[domain]
        fns = fn_by_domain[domain]
        domain_miss_rates[domain] = {
            "cases": total, "fn": fns,
            "miss_rate": fns / total if total else 0.0,
        }

    # Suggestions: domains/tiers with highest miss rates need more cases.
    suggestions = []
    for tier, info in sorted(difficulty_miss_rates.items(),
                             key=lambda x: x[1]["miss_rate"], reverse=True):
        if info["miss_rate"] > 0:
            suggestions.append(
                f"Write more {tier}-tier cases (miss rate: "
                f"{info['miss_rate']:.0%}, {info['fn']} FN across {info['cases']} cases)."
            )
    for domain, info in sorted(domain_miss_rates.items(),
                                key=lambda x: x[1]["miss_rate"], reverse=True):
        if info["miss_rate"] > 0:
            suggestions.append(
                f"Strengthen {domain} domain coverage (miss rate: "
                f"{info['miss_rate']:.0%}, {info['fn']} FN across {info['cases']} cases)."
            )

    return {
        "total_cases": len(cases_data),
        "total_fn": sum(fn_by_difficulty.values()),
        "total_fp": sum(fp_by_difficulty.values()),
        "miss_rate_by_difficulty": difficulty_miss_rates,
        "fp_rate_by_difficulty": difficulty_fp_rates,
        "miss_rate_by_domain": domain_miss_rates,
        "worst_fn_cases": sorted(fn_cases, key=lambda x: x["fn"], reverse=True)[:10],
        "worst_fp_cases": sorted(fp_cases, key=lambda x: x["fp"], reverse=True)[:10],
        "suggestions": suggestions,
    }


def print_analysis(result: dict) -> None:
    """Pretty-print the analysis."""
    print("\n=== Failure Analysis ===\n")
    print(f"Total cases: {result['total_cases']}")
    print(f"Total FN (missed hallucinations): {result['total_fn']}")
    print(f"Total FP (false alarms): {result['total_fp']}")

    print("\n--- Miss Rate by Difficulty ---")
    for tier, info in result["miss_rate_by_difficulty"].items():
        print(f"  {tier:<15} {info['fn']} FN / {info['cases']} cases "
              f"({info['miss_rate']:.0%})")

    print("\n--- FP Rate by Difficulty ---")
    for tier, info in result["fp_rate_by_difficulty"].items():
        print(f"  {tier:<15} {info['fp']} FP / {info['cases']} cases "
              f"({info['fp_rate']:.0%})")

    print("\n--- Miss Rate by Domain ---")
    for domain, info in result["miss_rate_by_domain"].items():
        print(f"  {domain:<15} {info['fn']} FN / {info['cases']} cases "
              f"({info['miss_rate']:.0%})")

    if result["worst_fn_cases"]:
        print("\n--- Worst FN Cases ---")
        for c in result["worst_fn_cases"][:5]:
            print(f"  {c['name']:<40} FN={c['fn']} [{c['difficulty']}] "
                  f"missed: {', '.join(c['missed'][:3])}")

    if result["suggestions"]:
        print("\n--- Suggestions ---")
        for s in result["suggestions"]:
            print(f"  - {s}")
    print()


def generate_sample_report() -> dict:
    """Generate a sample report using FakeLLMClient for offline analysis."""
    from eval.run import run, to_dict
    from tests.fakes import FakeLLMClient

    client = FakeLLMClient(json.dumps({"passed": True, "failures": []}))
    report = run(client)
    return to_dict(report)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Failure analysis for eval reports.")
    parser.add_argument("report", nargs="?", help="Path to a JSON report file.")
    parser.add_argument("--sample", action="store_true",
                        help="Generate and analyze a sample report (offline).")
    args = parser.parse_args(argv)

    if args.sample:
        report_data = generate_sample_report()
    elif args.report:
        with open(args.report) as f:
            report_data = json.load(f)
    else:
        parser.error("Provide a report path or use --sample.")
        return 2

    result = analyze(report_data)
    print_analysis(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
