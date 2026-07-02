"""Adversarial case generator for the eval harness.

Uses an LLM (Sonnet, cheap) to generate planted claims that are designed to be
hard for the Verify agent to catch. Generated cases are printed as Python source
to be reviewed and frozen into eval/cases_adversarial.py.

Usage:
    ANTHROPIC_API_KEY=sk-... python -m eval.adversarial
    # or for offline testing:
    python -m eval.adversarial --dry-run
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from app.agents.client import LLMClient, build_default_client
from app.agents.parsing import extract_json_object

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048

# Taxonomy of hallucination types we want adversarial cases for.
TAXONOMY_TYPES = [
    "invented_quantity",
    "invented_eligibility",
    "invented_partnership",
    "overstated_geography",
    "overstated_budget",
    "near_miss_tenure",
    "unstated_inference",
    "negation_flip",
    "unit_confusion",
    "temporal_contradiction",
    "partial_truth",
    "close_number",
    "precision_trap",
    "dense_context_burial",
]

_SYSTEM = (
    "You are an adversarial test-case author for a hallucination-detection system. "
    "Given a nonprofit profile, a funding opportunity, and a hallucination taxonomy "
    "type, write a single planted claim that is HARD for a verifier to catch. "
    "The claim should be plausible, subtle, and blend naturally with grounded text.\n\n"
    "Reply with a single JSON object:\n"
    '{"planted_text": "<the claim>", "tag": "<short-unique-tag>", '
    '"grounded_text": "<a true sentence to pair it with>", "grounded_tag": "<tag>"}'
)


def generate_one(
    client: LLMClient,
    taxonomy_type: str,
    profile_desc: str,
    opp_desc: str,
) -> dict:
    """Ask the LLM to generate one adversarial planted claim."""
    messages = [
        {
            "role": "user",
            "content": (
                f"TAXONOMY TYPE: {taxonomy_type}\n\n"
                f"PROFILE:\n{profile_desc}\n\n"
                f"OPPORTUNITY:\n{opp_desc}\n\n"
                "Write a planted claim of this type that would be hard to catch."
            ),
        }
    ]
    resp = client.complete(
        model=MODEL,
        system=[{"type": "text", "text": _SYSTEM}],
        messages=messages,
        max_tokens=MAX_TOKENS,
    )
    return extract_json_object(resp.text, resp.stop_reason)


def dry_run_report(taxonomy_types: Optional[List[str]] = None) -> str:
    """Return a string describing what WOULD be generated, without calling an API."""
    types = taxonomy_types or TAXONOMY_TYPES
    lines = ["[DRY RUN] Would generate adversarial cases for:"]
    for i, t in enumerate(types):
        lines.append(f"  {i + 1}. {t}")
    lines.append(f"\nTotal: {len(types)} cases to generate.")
    lines.append("Pass without --dry-run and with ANTHROPIC_API_KEY to generate.")
    return "\n".join(lines)


def emit_python_source(taxonomy_type: str, data: dict, index: int) -> str:
    """Format a generated case as Python source code for review."""
    tag = data.get("tag", f"advgen-{index}")
    planted = data.get("planted_text", "")
    grounded = data.get("grounded_text", "")
    grounded_tag = data.get("grounded_tag", f"advgen-{index}-grounded")
    name = f"advgen/{taxonomy_type}-{index:02d}"

    return f"""    EvalCase(
        name="{name}",
        profile=_solar_profile(), opportunity=_solar_opp(), difficulty="adversarial",
        eligibility_sentences=[
            Sentence("{grounded}",
                     planted=False, tag="{grounded_tag}"),
            Sentence("{planted}",
                     planted=True, tag="{tag}"),
        ],
    ),"""


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate adversarial eval cases.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be generated without calling the API.")
    parser.add_argument("--types", nargs="*", help="Specific taxonomy types to generate.")
    args = parser.parse_args(argv)

    types = args.types or TAXONOMY_TYPES

    if args.dry_run:
        print(dry_run_report(types))
        return 0

    client = build_default_client()
    if client is None:
        print("ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 2

    profile_desc = (
        "501(c)(3) nonprofit, 500k budget, 8 years old, CA, disadvantaged community, "
        "community solar, serves low-income and rural populations, needs 250k."
    )
    opp_desc = (
        "DOE Solar Energy Innovation Grant. Open to 501(c)(3) nonprofits serving "
        "disadvantaged communities. Funds community solar in low-income areas."
    )

    print("# Generated adversarial cases — review before freezing.\n")
    print("_adversarial_generated = [")
    for i, t in enumerate(types):
        try:
            data = generate_one(client, t, profile_desc, opp_desc)
            print(emit_python_source(t, data, i))
        except Exception as exc:
            print(f"    # FAILED for {t}: {exc}", file=sys.stderr)
    print("]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
