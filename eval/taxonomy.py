"""Hallucination taxonomy for the Verify eval harness.

Every planted claim in eval/cases.py maps to a taxonomy cell via its
``hallucination_type`` field. Gaps in coverage (taxonomy IDs with zero cases)
are what later work fills.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class HallucinationType:
    id: str
    category: str
    description: str


TAXONOMY: list[HallucinationType] = [
    # -- Fabrication (inventing facts) --
    HallucinationType(
        "entity-fabrication", "fabrication",
        "Invented organizations, people, awards, certifications",
    ),
    HallucinationType(
        "quantity-fabrication", "fabrication",
        "Invented specific numbers (dollar amounts, counts, percentages)",
    ),
    HallucinationType(
        "date-fabrication", "fabrication",
        "Invented dates, timelines, deadlines",
    ),
    HallucinationType(
        "unsupported-eligibility", "fabrication",
        "Asserts the org meets a specific funder requirement (designation, "
        "threshold, required policy) that the profile never establishes",
    ),
    # -- Distortion (twisting real facts) --
    HallucinationType(
        "quantity-distortion", "distortion",
        "Rounding, inflating, or deflating real numbers",
    ),
    HallucinationType(
        "scope-inflation", "distortion",
        "Expanding geography, audience, or mandate beyond what's stated",
    ),
    HallucinationType(
        "unit-confusion", "distortion",
        "Wrong units (kW vs MW, months vs years)",
    ),
    # -- Logical (reasoning errors) --
    HallucinationType(
        "negation-flip", "logical",
        "Claim asserts X when source says NOT X",
    ),
    HallucinationType(
        "conditional-as-absolute", "logical",
        "\"may be eligible\" becomes \"is eligible\"",
    ),
    HallucinationType(
        "multi-hop-contradiction", "logical",
        "Claim requires chaining 2+ facts to detect the error",
    ),
    HallucinationType(
        "temporal-state-error", "logical",
        "Wrong project stage, timeline, or temporal status",
    ),
    # -- Attribution (wrong source/cause) --
    HallucinationType(
        "attribution-shift", "attribution",
        "Attributes a fact to the wrong entity or source",
    ),
    HallucinationType(
        "inferred-relationship", "attribution",
        "Assumes a partnership, agreement, or affiliation not stated",
    ),
    # -- Omission-based (unstated inferences) --
    HallucinationType(
        "unstated-technical", "omission",
        "Assumes technical capability or feature not mentioned",
    ),
    HallucinationType(
        "unsupported-causal", "omission",
        "Asserts a causal relationship not in the source",
    ),
]

TAXONOMY_IDS: set[str] = {t.id for t in TAXONOMY}
TAXONOMY_CATEGORIES: set[str] = {t.category for t in TAXONOMY}


def coverage_report(cases: list) -> dict:
    """Return {taxonomy_id: count} of how many planted sentences use each type."""
    counts: Counter[str] = Counter()
    for case in cases:
        for s in case.all_sentences():
            if s.planted and s.hallucination_type:
                counts[s.hallucination_type] += 1
    uncovered = [t.id for t in TAXONOMY if t.id not in counts]
    return {"counts": dict(counts), "uncovered": uncovered}
