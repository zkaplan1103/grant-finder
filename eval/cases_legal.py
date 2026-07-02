"""Cross-domain eval cases: legal aid.

Tests that the Verify agent generalizes beyond solar/grants to legal-services
content. Uses the same Profile/Opportunity/Draft models with legal-domain text.
"""

from __future__ import annotations

from typing import List

from app.models import (
    FundingPreference,
    MissionPopulations,
    Opportunity,
    OpportunitySource,
    OrgBasics,
    Profile,
    ProjectSpecifics,
)
from app.models import Geography as Geo
from eval.cases import EvalCase, Sentence


def _legal_aid_profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=1_200_000, org_age_years=15),
        project_type="legal services",
        funding_preference=FundingPreference.GRANT,
        geography=Geo(state="IL", service_area="Cook County", disadvantaged_community=True),
        project=ProjectSpecifics(
            project_type="immigration and housing legal aid",
            amount_needed_usd=350_000,
        ),
        mission=MissionPopulations(
            mission_statement=(
                "Provide free civil legal services to low-income immigrants and tenants "
                "facing eviction in Cook County, Illinois."
            ),
            populations_served=["low-income immigrants", "tenants facing eviction"],
        ),
    )


def _legal_aid_opp() -> Opportunity:
    return Opportunity(
        id="OPP-LSC-LEGAL",
        source=OpportunitySource.GRANTS_GOV,
        title="Legal Services Corporation Basic Field Grant",
        agency="LSC",
        status="posted",
        aln="09.001",
        eligibility_notes=(
            "Eligible applicants are 501(c)(3) nonprofit organizations that provide free "
            "civil legal assistance to low-income individuals. Applicants must demonstrate "
            "at least three years of continuous operation. Services must target populations "
            "at or below 125 percent of the federal poverty level. The grant covers legal "
            "representation in housing, family, and immigration matters. Maximum award is "
            "500,000 dollars per year."
        ),
        description=(
            "The LSC Basic Field Grant funds direct legal representation for low-income "
            "Americans in civil matters including eviction defense, immigration relief, "
            "domestic violence protection orders, and consumer disputes."
        ),
    )


def load_legal_cases() -> List[EvalCase]:
    p, o = _legal_aid_profile, _legal_aid_opp
    cases: List[EvalCase] = []

    # 1. Entity fabrication: invented bar admission (obvious)
    cases.append(
        EvalCase(
            name="legal/invented-bar-admission",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    "The organization provides free legal services to immigrants in "
                    "Cook County.",
                    planted=False, tag="legal-services-grounded",
                ),
                Sentence(
                    "All staff attorneys are admitted to practice before the Supreme "
                    "Court of the United States.",
                    planted=True, tag="legal-scotus-admission",
                    hallucination_type="entity-fabrication",
                ),
            ],
        )
    )

    # 2. Quantity distortion: inflated client count (adversarial)
    cases.append(
        EvalCase(
            name="legal/inflated-client-count",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit with 15 years of continuous "
                    "operation.",
                    planted=False, tag="legal-tenure-grounded",
                ),
                Sentence(
                    # Parrots the opp's 125% FPL threshold; the profile only says
                    # "low-income" — the specific threshold is never established.
                    "The organization serves populations at or below 125 percent of the "
                    "federal poverty level, consistent with funder requirements.",
                    planted=True, tag="legal-poverty-125fpl-claim",
                    hallucination_type="unsupported-eligibility",
                ),
                Sentence(
                    "Last year the program provided direct representation to over 25,000 "
                    "individual clients across Cook County.",
                    planted=True, tag="legal-25000-clients",
                    hallucination_type="quantity-distortion",
                ),
            ],
        )
    )

    # 3. Scope inflation: expanding beyond stated service area (adversarial)
    cases.append(
        EvalCase(
            name="legal/scope-inflation-statewide",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization holds 501(c)(3) status and has operated continuously "
                    "for fifteen years.",
                    planted=False, tag="legal-501c3-grounded",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Our mission is to provide free civil legal assistance to low-income "
                    "individuals.",
                    planted=False, tag="legal-mission-grounded",
                ),
                Sentence(
                    "The organization maintains offices throughout the state of Illinois, "
                    "delivering statewide coverage for immigration matters.",
                    planted=True, tag="legal-statewide-scope",
                    hallucination_type="scope-inflation",
                ),
            ],
        )
    )

    # 4. Negation flip: the opp covers civil matters; claim says criminal (obvious)
    cases.append(
        EvalCase(
            name="legal/negation-flip-criminal",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    "The applicant requests 350,000 dollars for legal aid services.",
                    planted=False, tag="legal-amount-grounded",
                ),
                Sentence(
                    "A core component of the program is criminal defense representation "
                    "for felony charges.",
                    planted=True, tag="legal-criminal-defense",
                    hallucination_type="negation-flip",
                ),
            ],
        )
    )

    # 5. Attribution shift: attributing accreditation to wrong body (adversarial)
    cases.append(
        EvalCase(
            name="legal/attribution-shift-aba",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization targets low-income immigrants and tenants facing "
                    "eviction.",
                    planted=False, tag="legal-populations-grounded",
                ),
                Sentence(
                    "The organization is formally accredited by the American Bar "
                    "Association as a recognized legal aid provider.",
                    planted=True, tag="legal-aba-accreditation",
                    hallucination_type="attribution-shift",
                ),
            ],
        )
    )

    # 6. Clean draft — no planted claims, tests precision
    cases.append(
        EvalCase(
            name="legal/clean-no-planted",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit providing free civil legal "
                    "services to low-income individuals.",
                    planted=False, tag="legal-clean-elig-1",
                ),
                Sentence(
                    "The organization has operated continuously for fifteen years in "
                    "Cook County, Illinois.",
                    planted=False, tag="legal-clean-elig-2",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Our services target low-income immigrants and tenants facing "
                    "eviction in Cook County, Illinois.",
                    planted=False, tag="legal-clean-boiler-1",
                ),
            ],
        )
    )

    # 7. High claim density: 3 planted in one draft (hard)
    cases.append(
        EvalCase(
            name="legal/high-density-three-planted",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) serving low-income populations in "
                    "Cook County.",
                    planted=False, tag="legal-hd-grounded",
                ),
                Sentence(
                    "The program has won the Congressional Award for Excellence in "
                    "Legal Services three years running.",
                    planted=True, tag="legal-congressional-award",
                    hallucination_type="entity-fabrication",
                ),
                Sentence(
                    "Last fiscal year the organization secured favorable outcomes in "
                    "ninety-eight percent of its immigration cases.",
                    planted=True, tag="legal-98-percent-win",
                    hallucination_type="quantity-distortion",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Through a formal memorandum of understanding with the Department "
                    "of Homeland Security, the organization receives priority case "
                    "referrals.",
                    planted=True, tag="legal-dhs-mou",
                    hallucination_type="attribution-shift",
                ),
            ],
        )
    )

    # 8. Multi-hop arithmetic: budget vs. ask vs. award ceiling (hard)
    cases.append(
        EvalCase(
            name="legal/arithmetic-budget-fraction",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence(
                    "The organization operates on an annual budget of 1.2 million dollars.",
                    planted=False, tag="legal-budget-grounded",
                ),
                Sentence(
                    "The requested amount of 350,000 dollars represents approximately "
                    "fifteen percent of the annual budget.",
                    planted=True, tag="legal-fraction-wrong",
                    hallucination_type="quantity-distortion",
                ),
            ],
        )
    )

    # 9. Temporal/state contradiction: 15 years old, claims recent founding (obvious)
    cases.append(
        EvalCase(
            name="legal/temporal-recent-founding",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    # Parrots the opp's 125% FPL threshold; the profile only says
                    # "low-income" — the specific threshold is never established.
                    "The organization serves populations at or below 125 percent of the "
                    "federal poverty level.",
                    planted=True, tag="legal-fpl-125-claim",
                    hallucination_type="unsupported-eligibility",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Founded just two years ago, the organization has rapidly scaled its "
                    "legal aid operations.",
                    planted=True, tag="legal-two-year-founding",
                    hallucination_type="temporal-state-error",
                ),
            ],
        )
    )

    # 10. Unstated inference: immigration services don't imply asylum expertise (adversarial)
    cases.append(
        EvalCase(
            name="legal/unstated-asylum-expertise",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The applicant provides immigration and housing legal aid in "
                    "Cook County.",
                    planted=False, tag="legal-imm-housing-grounded",
                ),
                Sentence(
                    "The organization maintains a dedicated asylum unit staffed by "
                    "twelve attorneys specializing in refugee claims.",
                    planted=True, tag="legal-asylum-unit",
                    hallucination_type="unstated-technical",
                ),
            ],
        )
    )

    return cases
