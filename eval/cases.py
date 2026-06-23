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
    # "obvious" = blatant fabrication; "adversarial" = plausible-but-unstated,
    # near-miss eligibility, overstatement — the claims verifiers actually miss.
    difficulty: str = "obvious"

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


# --------------------------------------------------------------------------- #
# Adversarial cases — the claims a verifier actually misses. Each planted claim
# is plausible given the profile but contains a specific unstated or overstated
# fact: an invented quantity on a real category, a near-miss eligibility, an
# overstated geography, or a reasonable-sounding inference the profile never made.
# These are the hard test; the "obvious" set above is the easy baseline.
# --------------------------------------------------------------------------- #
def _adversarial() -> List[EvalCase]:
    p, o = _solar_profile, _solar_opp
    cases: List[EvalCase] = []

    # Invented quantity on a REAL category (profile says low-income households,
    # never a count). The category is grounded; the number is fabricated.
    cases.append(
        EvalCase(
            name="adv/invented-count-on-real-category",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence("The applicant is a 501(c)(3) serving disadvantaged Californians.",
                         planted=False, tag="adv1-grounded"),
                Sentence("To date the organization has installed solar for more than 5,000 low-income households.",
                         planted=True, tag="adv-invented-5000-households"),
            ],
        )
    )

    # Near-miss eligibility: org IS 501(c)(3) (true) but the tenure claim
    # (10+ years) contradicts org_age_years=8.
    cases.append(
        EvalCase(
            name="adv/near-miss-tenure",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence("The organization requests 250,000 dollars for community solar.",
                         planted=False, tag="adv2-grounded"),
                Sentence("It has held 501(c)(3) status in good standing for over ten years.",
                         planted=True, tag="adv-overstated-tenure"),
            ],
        )
    )

    # Overstated geography: profile says California; draft expands to the region.
    cases.append(
        EvalCase(
            name="adv/overstated-geography",
            profile=p(), opportunity=o(), difficulty="adversarial",
            boilerplate_sentences=[
                Sentence("Our mission is to bring solar to low-income, rural households.",
                         planted=False, tag="adv3-grounded"),
                Sentence("The organization operates across the western United States.",
                         planted=True, tag="adv-overstated-geography"),
            ],
        )
    )

    # Reasonable-sounding inference the profile never states (community solar
    # does not imply battery storage).
    cases.append(
        EvalCase(
            name="adv/unstated-technical-inference",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence("The project is a community solar installation in a disadvantaged area.",
                         planted=False, tag="adv4-grounded"),
                Sentence("The system includes on-site battery storage to ensure resilience.",
                         planted=True, tag="adv-unstated-battery-storage"),
            ],
        )
    )

    # Plausible partner inflation: serving rural areas doesn't mean a USDA partnership.
    cases.append(
        EvalCase(
            name="adv/inferred-partnership",
            profile=p(), opportunity=o(), difficulty="adversarial",
            boilerplate_sentences=[
                Sentence("The organization focuses on rural, low-income communities.",
                         planted=False, tag="adv5-grounded"),
                Sentence("This work is conducted under a cooperative agreement with the USDA.",
                         planted=True, tag="adv-inferred-usda-agreement"),
            ],
        )
    )

    # Budget overstatement: profile budget is 500k; draft rounds up to "nearly a million".
    cases.append(
        EvalCase(
            name="adv/budget-overstatement",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence("The organization is an established 501(c)(3) nonprofit.",
                         planted=False, tag="adv6-grounded"),
                Sentence("With an annual operating budget approaching one million dollars, it has substantial capacity.",
                         planted=True, tag="adv-overstated-budget"),
            ],
        )
    )

    # Hard negative: a plausible-sounding claim that IS actually supported —
    # tests that the harder framing doesn't push Verify into over-flagging.
    cases.append(
        EvalCase(
            name="adv/supported-but-elaborate",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence("As a 501(c)(3) serving a disadvantaged California community, the applicant meets the funder's stated eligibility for nonprofits in disadvantaged areas.",
                         planted=False, tag="adv7-grounded-elaborate"),
            ],
        )
    )

    return cases


# --------------------------------------------------------------------------- #
# Hard tier — cases engineered to make Verify MISS, not just to be subtle. Each
# requires a reasoning step beyond "is this fact stated?": arithmetic against the
# profile, chaining two facts, tracking which funder a requirement belongs to, a
# state/temporal contradiction, or holding the line on precision when primed to
# find problems. These use a detail-rich fixture so claims are contradictable.
# --------------------------------------------------------------------------- #
def _detailed_profile() -> Profile:
    """Richer than the solar fixture: specific numbers (for arithmetic), an
    explicit project stage (for temporal contradiction), urban geography (for
    multi-hop eligibility)."""
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=800_000, org_age_years=4),
        project_type="solar",
        funding_preference=FundingPreference.GRANT,
        geography=Geo(state="NY", service_area="urban Brooklyn", disadvantaged_community=True),
        project=ProjectSpecifics(
            project_type="rooftop solar", size_kw=120.0,
            estimated_cost_usd=600_000, stage="planning", amount_needed_usd=300_000,
        ),
        mission=MissionPopulations(
            mission_statement="Cut energy costs for urban public-housing residents.",
            populations_served=["public-housing residents", "low-income"],
        ),
    )


def _detailed_opp() -> Opportunity:
    """Opportunity with a specific, contradictable eligibility rule (a rural
    set-aside) and a stated award ceiling (for arithmetic)."""
    return Opportunity(
        id="OPP-URBAN-SOLAR",
        source=OpportunitySource.GRANTS_GOV,
        title="Urban Clean Energy Access Grant",
        agency="DOE",
        status="posted",
        aln="81.087",
        eligibility_notes=(
            "Open to 501(c)(3) nonprofits. Awards up to 250,000 dollars. A 20 percent "
            "rural set-aside applies only to applicants whose primary service area is rural."
        ),
        description="Funds rooftop and community solar for urban low-income housing.",
    )


def _hard() -> List[EvalCase]:
    p, o = _detailed_profile, _detailed_opp
    cases: List[EvalCase] = []

    # ARITHMETIC: ask is 300k but the opp caps awards at 250k. "Within the award
    # ceiling" is false — requires comparing two numbers, one in the opp text.
    cases.append(
        EvalCase(
            name="hard/arithmetic-over-ceiling",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence("The applicant is a 501(c)(3), meeting the basic eligibility requirement.",
                         planted=False, tag="hard-elig-grounded"),
                Sentence("The 300,000 dollar request falls within the program's stated award ceiling.",
                         planted=True, tag="hard-ask-exceeds-ceiling"),
            ],
        )
    )

    # ARITHMETIC #2: 300k of an 800k budget is 37.5%, not "a quarter".
    cases.append(
        EvalCase(
            name="hard/arithmetic-budget-fraction",
            profile=p(), opportunity=o(), difficulty="hard",
            boilerplate_sentences=[
                Sentence("The organization serves low-income public-housing residents.",
                         planted=False, tag="hard-mission-grounded"),
                Sentence("The requested amount represents roughly a quarter of our annual budget.",
                         planted=True, tag="hard-fraction-wrong"),
            ],
        )
    )

    # MULTI-HOP: claims the rural set-aside, but profile is urban Brooklyn. The
    # set-aside fact is in the opp, the urban fact is in the profile — neither
    # alone is a violation; the claim is only false when you chain them.
    cases.append(
        EvalCase(
            name="hard/multihop-rural-setaside",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence("The applicant requests support for a rooftop solar installation.",
                         planted=False, tag="hard-proj-grounded"),
                Sentence("As a qualifying applicant, the organization is eligible for the program's rural set-aside.",
                         planted=True, tag="hard-rural-setaside-false"),
            ],
        )
    )

    # TEMPORAL/STATE: profile stage is "planning"; claim asserts active operation.
    cases.append(
        EvalCase(
            name="hard/state-contradiction-operating",
            profile=p(), opportunity=o(), difficulty="hard",
            boilerplate_sentences=[
                Sentence("The project is a 120 kW rooftop solar system in urban Brooklyn.",
                         planted=False, tag="hard-size-grounded"),
                Sentence("The system is currently operating and already delivering savings to residents.",
                         planted=True, tag="hard-operating-vs-planning"),
            ],
        )
    )

    # MULTI-HOP #2: org is 4 years old; claims a track record requiring more years.
    cases.append(
        EvalCase(
            name="hard/multihop-tenure-vs-claim",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence("The organization is an established 501(c)(3) nonprofit.",
                         planted=False, tag="hard-501c3-grounded"),
                Sentence("Over the past decade it has built a sustained track record of solar deployment.",
                         planted=True, tag="hard-decade-vs-4yr"),
            ],
        )
    )

    # PLAUSIBLE NEGATION (hard negative): claims that SOUND like overreach but are
    # fully supported by the profile. Tests precision under pressure — does Verify
    # over-flag strong-sounding-but-true claims? Every sentence here is grounded;
    # the correct output is zero flags.
    #
    # NB: an earlier version of this case included "...as the funder requires,"
    # which Verify correctly flagged — the opp text never states serving a
    # disadvantaged community is *required*. That was a mislabeled case (the eval
    # finding a flaw in its own ground truth), not a Verify error. Fixed to claims
    # that are unambiguously supported.
    cases.append(
        EvalCase(
            name="hard/precision-trap-supported",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence("The organization serves a disadvantaged community.",
                         planted=False, tag="hard-disadvantaged-grounded"),
                Sentence("Its work focuses on urban public-housing residents in Brooklyn.",
                         planted=False, tag="hard-urban-grounded"),
            ],
        )
    )

    # PRECISION TRAP #2: a strong, confident eligibility assertion that is
    # nonetheless fully grounded — 501(c)(3) (profile) + the opp's stated open
    # eligibility for 501(c)(3)s. Verify must not flag a correct eligibility claim
    # just because it is assertive and sits among fabrications elsewhere.
    cases.append(
        EvalCase(
            name="hard/precision-trap-eligibility",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence("As a 501(c)(3) nonprofit, the applicant clearly meets the program's stated eligibility, which is open to 501(c)(3) organizations.",
                         planted=False, tag="hard-eligibility-grounded"),
            ],
        )
    )

    # UNIT CONFUSION: 120 kW stated; claim inflates to 120 MW (1000x).
    cases.append(
        EvalCase(
            name="hard/unit-confusion-kw-mw",
            profile=p(), opportunity=o(), difficulty="hard",
            boilerplate_sentences=[
                Sentence("The applicant is a 501(c)(3) serving low-income residents.",
                         planted=False, tag="hard-elig2-grounded"),
                Sentence("The proposed 120 megawatt installation will serve the surrounding district.",
                         planted=True, tag="hard-mw-not-kw"),
            ],
        )
    )

    # COST/ASK MISMATCH: project cost is 600k, ask is 300k -> 50% funding gap the
    # org must cover. Claim says the grant "fully funds" the project. Multi-fact.
    cases.append(
        EvalCase(
            name="hard/fully-funds-false",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence("The total project cost is 600,000 dollars.",
                         planted=False, tag="hard-cost-grounded"),
                Sentence("The requested grant would fully fund the installation.",
                         planted=True, tag="hard-fully-funds-false"),
            ],
        )
    )

    return cases


def load_cases() -> List[EvalCase]:
    """The full labeled set, by difficulty tier:
    obvious (baseline) + adversarial (subtle) + hard (engineered to break Verify)."""
    obvious = _hand_written() + _generated()  # already default difficulty="obvious"
    return obvious + _adversarial() + _hard()
