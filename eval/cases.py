"""Labeled eval cases for the Verify agent.

A case is (profile, opportunity, draft, ground-truth labels). Each draft is built
from labeled sentences: some grounded in the profile/opportunity, some planted
(unsupported). The harness checks whether Verify flags the planted ones (recall)
without flagging the grounded ones (precision).

Matching predicted->planted is keyword-based (each planted claim carries a unique
`tag` keyword that appears verbatim in its sentence). This is deterministic and
needs no judge model; an LLM judge can be layered on later if string overlap
proves too blunt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.models import (
    Draft,
    DraftStatus,
    FundingPreference,
    MissionPopulations,
    Opportunity,
    OpportunitySource,
    OrgBasics,
    Profile,
    ProjectSpecifics,
)
from app.models import Geography as Geo


@dataclass
class Sentence:
    """One sentence in a draft, with its ground-truth label.

    `tag` is a unique token present in the text so a flagged claim can be matched
    back to the planted sentence it refers to without fuzzy string alignment.
    """

    text: str
    planted: bool  # True = unsupported claim Verify SHOULD flag
    tag: str  # unique keyword appearing in `text`, used for matching


@dataclass
class EvalCase:
    name: str
    profile: Profile
    opportunity: Opportunity
    eligibility_sentences: List[Sentence] = field(default_factory=list)
    boilerplate_sentences: List[Sentence] = field(default_factory=list)

    def all_sentences(self) -> List[Sentence]:
        return self.eligibility_sentences + self.boilerplate_sentences

    def planted_tags(self) -> List[str]:
        return [s.tag for s in self.all_sentences() if s.planted]

    def to_draft(self) -> Draft:
        return Draft(
            opportunity_id=self.opportunity.id,
            eligibility_summary=" ".join(s.text for s in self.eligibility_sentences),
            boilerplate=" ".join(s.text for s in self.boilerplate_sentences),
            status=DraftStatus.DRAFT,
            revision=0,
        )


# --------------------------------------------------------------------------- #
# Shared fixtures reused across cases.
# --------------------------------------------------------------------------- #
def _solar_profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=500_000, org_age_years=8),
        project_type="solar",
        funding_preference=FundingPreference.GRANT,
        geography=Geo(state="CA", disadvantaged_community=True),
        project=ProjectSpecifics(project_type="community solar", amount_needed_usd=250_000),
        mission=MissionPopulations(
            mission_statement="Bring solar to low-income households.",
            populations_served=["low-income", "rural"],
        ),
    )


def _solar_opp() -> Opportunity:
    return Opportunity(
        id="OPP-SOLAR",
        source=OpportunitySource.GRANTS_GOV,
        title="Solar Energy Innovation Grant",
        agency="DOE",
        status="posted",
        aln="81.087",
        eligibility_notes="Open to 501(c)(3) nonprofits serving disadvantaged communities.",
        description="Funds community solar in low-income areas.",
    )


# --------------------------------------------------------------------------- #
# Hand-written cases — realistic drafts with deliberately planted claims.
# These carry the interview story; keep them legible.
# --------------------------------------------------------------------------- #
def _hand_written() -> List[EvalCase]:
    cases: List[EvalCase] = []

    # Case 1: invented award amount + invented geography among grounded text.
    cases.append(
        EvalCase(
            name="hand/invented-award-and-geo",
            profile=_solar_profile(),
            opportunity=_solar_opp(),
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit, satisfying the core eligibility gate.",
                    planted=False, tag="501c3-grounded",
                ),
                Sentence(
                    "The organization serves a designated disadvantaged community in California.",
                    planted=False, tag="ca-disadvantaged-grounded",
                ),
                Sentence(
                    "The organization has already been awarded a 1.4 million dollar federal match for this project.",
                    planted=True, tag="invented-1point4-million-award",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "We bring solar to low-income households across rural areas.",
                    planted=False, tag="mission-grounded",
                ),
                Sentence(
                    "Our headquarters in Phoenix, Arizona coordinates installations statewide.",
                    planted=True, tag="invented-phoenix-arizona-hq",
                ),
            ],
        )
    )

    # Case 2: invented eligibility the org does not meet (the dangerous kind).
    cases.append(
        EvalCase(
            name="hand/invented-eligibility",
            profile=_solar_profile(),
            opportunity=_solar_opp(),
            eligibility_sentences=[
                Sentence(
                    "The applicant requests 250,000 dollars for a community solar project.",
                    planted=False, tag="amount-grounded",
                ),
                Sentence(
                    "The organization is a federally recognized tribal government entity.",
                    planted=True, tag="invented-tribal-government-status",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Founded eight years ago, the organization operates on a 500,000 dollar annual budget.",
                    planted=False, tag="budget-age-grounded",
                ),
            ],
        )
    )

    # Case 3: clean draft — NOTHING planted. Tests precision (false positives).
    cases.append(
        EvalCase(
            name="hand/clean-no-planted",
            profile=_solar_profile(),
            opportunity=_solar_opp(),
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) serving a disadvantaged California community.",
                    planted=False, tag="clean-elig-1",
                ),
                Sentence(
                    "The requested amount is 250,000 dollars for community solar.",
                    planted=False, tag="clean-elig-2",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Our mission is to bring solar to low-income households in rural areas.",
                    planted=False, tag="clean-boiler-1",
                ),
                Sentence(
                    "The organization has operated for eight years on a 500,000 dollar budget.",
                    planted=False, tag="clean-boiler-2",
                ),
            ],
        )
    )

    # Case 4: invented population served + invented partner; one grounded claim.
    cases.append(
        EvalCase(
            name="hand/invented-population-and-partner",
            profile=_solar_profile(),
            opportunity=_solar_opp(),
            eligibility_sentences=[
                Sentence(
                    "The project targets low-income and rural households, matching the funder's priorities.",
                    planted=False, tag="populations-grounded",
                ),
                Sentence(
                    "The program has served over 40,000 veterans since its founding.",
                    planted=True, tag="invented-40000-veterans",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Our work is delivered in formal partnership with the United States Department of Defense.",
                    planted=True, tag="invented-dod-partnership",
                ),
            ],
        )
    )

    return cases


# --------------------------------------------------------------------------- #
# Generated cases — programmatic volume with ground truth by construction.
# A bank of grounded and unsupported sentence templates is combined so each
# generated draft has a known set of planted claims.
# --------------------------------------------------------------------------- #
_GROUNDED_BANK = [
    Sentence("The applicant holds 501(c)(3) status.", planted=False, tag="g-501c3"),
    Sentence("The organization serves a disadvantaged community in California.", planted=False, tag="g-ca"),
    Sentence("The request is for 250,000 dollars toward community solar.", planted=False, tag="g-amount"),
    Sentence("The mission is to bring solar to low-income, rural households.", planted=False, tag="g-mission"),
    Sentence("The organization has operated for eight years.", planted=False, tag="g-age"),
    Sentence("Its annual operating budget is 500,000 dollars.", planted=False, tag="g-budget"),
]

_UNSUPPORTED_BANK = [
    Sentence("The organization was awarded a 2 million dollar prize last year.", planted=True, tag="u-2m-prize"),
    Sentence("It operates a fleet of 30 electric vehicles for outreach.", planted=True, tag="u-30-evs"),
    Sentence("The applicant is headquartered in Denver, Colorado.", planted=True, tag="u-denver"),
    Sentence("The program has trained 12,000 certified solar installers.", planted=True, tag="u-12000-installers"),
    Sentence("The organization is a registered religious institution.", planted=True, tag="u-religious"),
    Sentence("It holds an exclusive contract with the state utility commission.", planted=True, tag="u-utility-contract"),
]


def _generated(n: int = 12) -> List[EvalCase]:
    """Build `n` cases by rotating through the banks, varying how many planted
    claims each draft carries (0..2) so the set isn't degenerate."""
    cases: List[EvalCase] = []
    for i in range(n):
        g = _GROUNDED_BANK[i % len(_GROUNDED_BANK)]
        g2 = _GROUNDED_BANK[(i + 2) % len(_GROUNDED_BANK)]
        n_planted = i % 3  # 0, 1, or 2 planted claims
        planted = [
            _UNSUPPORTED_BANK[(i + k) % len(_UNSUPPORTED_BANK)] for k in range(n_planted)
        ]
        cases.append(
            EvalCase(
                name=f"gen/{i:02d}-planted{n_planted}",
                profile=_solar_profile(),
                opportunity=_solar_opp(),
                eligibility_sentences=[g, *planted],
                boilerplate_sentences=[g2],
            )
        )
    return cases


def load_cases() -> List[EvalCase]:
    """The full labeled set: hand-written (realism) + generated (volume)."""
    return _hand_written() + _generated()
