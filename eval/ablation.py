"""Ablation study runner for the Verify agent.

Runs the eval suite across different configurations to quantify the impact of
model choice, thinking mode, and token budget on hallucination detection.

Usage:
    ANTHROPIC_API_KEY=sk-... python -m eval.ablation [--smoke] [--json PATH]
    python -m eval.ablation --dry-run  # show configs without running
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from app.agents.client import LLMClient, build_default_client
from eval.cases import EvalCase, load_cases
from eval.run import run, to_dict

CONFIGS: List[Dict[str, Any]] = [
    {
        "name": "opus-adaptive",
        "model": "claude-opus-4-8",
        "thinking": {"type": "adaptive"},
        "max_tokens": 16000,
    },
    {
        "name": "sonnet-adaptive",
        "model": "claude-sonnet-4-6",
        "thinking": {"type": "adaptive"},
        "max_tokens": 16000,
    },
    {
        "name": "haiku",
        "model": "claude-haiku-4-5",
        "thinking": None,
        "max_tokens": 8000,
    },
    {
        "name": "opus-no-thinking",
        "model": "claude-opus-4-8",
        "thinking": None,
        "max_tokens": 16000,
    },
    {
        "name": "opus-low-tokens",
        "model": "claude-opus-4-8",
        "thinking": {"type": "adaptive"},
        "max_tokens": 4000,
    },
]


def _run_with_config(
    config: Dict[str, Any],
    client: LLMClient,
    cases: Optional[List[EvalCase]] = None,
) -> dict:
    """Monkey-patch verify module globals, run the eval, restore originals."""
    import app.agents.verify as verify_mod

    orig_model = verify_mod.MODEL
    orig_thinking = verify_mod.THINKING
    orig_max_tokens = verify_mod.MAX_TOKENS

    try:
        verify_mod.MODEL = config["model"]
        verify_mod.THINKING = config["thinking"]
        verify_mod.MAX_TOKENS = config["max_tokens"]
        report = run(client, cases=cases)
    finally:
        verify_mod.MODEL = orig_model
        verify_mod.THINKING = orig_thinking
        verify_mod.MAX_TOKENS = orig_max_tokens

    return {
        "config": config["name"],
        "model": config["model"],
        "thinking": config["thinking"],
        "max_tokens": config["max_tokens"],
        "report": to_dict(report),
        "precision": report.precision,
        "recall": report.recall,
        "f1": report.f1,
    }


def dry_run_report() -> str:
    """Return a string describing the configurations that would be tested."""
    lines = ["[DRY RUN] Ablation configs:"]
    for i, c in enumerate(CONFIGS):
        thinking_str = c["thinking"]["type"] if c["thinking"] else "none"
        lines.append(
            f"  {i + 1}. {c['name']:<20} model={c['model']:<20} "
            f"thinking={thinking_str:<10} max_tokens={c['max_tokens']}"
        )
    lines.append(f"\nTotal: {len(CONFIGS)} configurations.")
    return "\n".join(lines)


def _print_comparison(results: List[dict]) -> None:
    """Print a side-by-side comparison table."""
    print("\n=== Ablation Study Results ===\n")
    print(f"{'Config':<22} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 55)
    for r in results:
        print(f"{r['config']:<22} {r['precision']:>9.0%} {r['recall']:>9.0%} {r['f1']:>9.0%}")
    print("-" * 55)
    print()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ablation study for the Verify agent.")
    parser.add_argument("--json", metavar="PATH", help="Write results to JSON.")
    parser.add_argument("--smoke", action="store_true", help="Run only smoke cases.")
    parser.add_argument("--dry-run", action="store_true", help="Show configs, don't run.")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(dry_run_report())
        return 0

    client = build_default_client()
    if client is None:
        print("ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 2

    cases = load_cases()
    if args.smoke:
        cases = cases[:5]

    results = []
    for config in CONFIGS:
        print(f"\n--- Running config: {config['name']} ---")
        result = _run_with_config(config, client, cases)
        results.append(result)

    _print_comparison(results)

    if args.json:
        with open(args.json, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Wrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
