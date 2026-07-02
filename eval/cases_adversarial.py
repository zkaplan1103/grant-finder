"""Hand-written adversarial eval cases — the hardest cases for a verifier.

Each case is designed to exploit a specific weakness in hallucination detection:
partial truths, buried errors, precision traps, negation flips, close-but-wrong
numbers, and dense context that obscures a single fabricated detail.

These are FROZEN ground truth — edit only after human review.
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


def _detailed_profile() -> Profile:
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


def load_adversarial_cases() -> List[EvalCase]:
    """20 hand-written adversarial cases, each targeting a specific verifier weakness."""
    p, o = _solar_profile, _solar_opp
    dp, do = _detailed_profile, _detailed_opp
    cases: List[EvalCase] = []

    # 1. PARTIAL TRUTH: first clause grounded (501c3 = true), second fabricated
    # (national accreditation not in profile). Single sentence, mixed truth.
    cases.append(
        EvalCase(
            name="advx/partial-truth-accreditation",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "As a 501(c)(3) nonprofit with national environmental accreditation, "
                    "the applicant exceeds the program's eligibility threshold.",
                    planted=True, tag="advx-partial-accreditation",
                ),
                Sentence(
                    "The organization serves disadvantaged communities in California.",
                    planted=False, tag="advx01-grounded",
                ),
            ],
        )
    )

    # 2. PARTIAL TRUTH: real population (low-income) + fabricated count in one sentence.
    cases.append(
        EvalCase(
            name="advx/partial-truth-population-count",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization has provided solar installations to low-income "
                    "households, reaching 12,500 families since inception.",
                    planted=True, tag="advx-partial-12500-families",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Our mission is to bring solar to low-income households.",
                    planted=False, tag="advx02-grounded",
                ),
            ],
        )
    )

    # 3. BURIED ERROR: long grounded context, one wrong number deep in the text.
    cases.append(
        EvalCase(
            name="advx/buried-wrong-budget",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit that has operated for eight "
                    "years in California.",
                    planted=False, tag="advx03-grounded-1",
                ),
                Sentence(
                    "It serves disadvantaged communities with community solar projects.",
                    planted=False, tag="advx03-grounded-2",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "With an annual operating budget of 750,000 dollars, the organization "
                    "maintains robust fiscal management.",
                    planted=True, tag="advx-buried-750k-budget",
                ),
            ],
        )
    )

    # 4. PRECISION TRAP: sounds wrong ("8 consecutive years of federal grants") but
    # the profile says org_age=8 and is 501c3. The claim never says they GOT federal
    # grants, just that they operated for 8 years. Actually... it DOES say federal
    # grants, which IS fabricated.
    cases.append(
        EvalCase(
            name="advx/precision-trap-federal-grants",
            profile=p(), opportunity=o(), difficulty="adversarial",
            boilerplate_sentences=[
                Sentence(
                    "The organization has received federal grant funding for eight "
                    "consecutive years.",
                    planted=True, tag="advx-precision-federal-grants",
                ),
                Sentence(
                    "The applicant requests 250,000 dollars for a community solar project.",
                    planted=False, tag="advx04-grounded",
                ),
            ],
        )
    )

    # 5. NEGATION FLIP: "has never failed an audit" — sounds positive but asserts
    # audit history not in profile.
    cases.append(
        EvalCase(
            name="advx/negation-flip-audit",
            profile=p(), opportunity=o(), difficulty="adversarial",
            boilerplate_sentences=[
                Sentence(
                    "The organization has never failed a federal compliance audit.",
                    planted=True, tag="advx-negation-audit-history",
                ),
                Sentence(
                    "Its mission is to bring solar to low-income households in rural areas.",
                    planted=False, tag="advx05-grounded",
                ),
            ],
        )
    )

    # 6. CLOSE NUMBER: profile says 250k needed, claim says 245k.
    cases.append(
        EvalCase(
            name="advx/close-number-245k",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) serving a disadvantaged California community.",
                    planted=False, tag="advx06-grounded",
                ),
                Sentence(
                    "The requested amount of 245,000 dollars aligns with the program's "
                    "funding parameters.",
                    planted=True, tag="advx-close-245k-vs-250k",
                ),
            ],
        )
    )

    # 7. CLOSE NUMBER: profile says 8 years old, claim says "nearly a decade" (10).
    cases.append(
        EvalCase(
            name="advx/close-number-decade",
            profile=p(), opportunity=o(), difficulty="adversarial",
            boilerplate_sentences=[
                Sentence(
                    "With nearly a decade of continuous operations, the organization "
                    "brings deep expertise to this project.",
                    planted=True, tag="advx-close-decade-vs-8yr",
                ),
                Sentence(
                    "The applicant holds 501(c)(3) tax-exempt status.",
                    planted=False, tag="advx07-grounded",
                ),
            ],
        )
    )

    # 8. NEGATION FLIP in dense legal text: "no outstanding compliance issues" —
    # compliance history not stated anywhere.
    cases.append(
        EvalCase(
            name="advx/negation-compliance-dense",
            profile=dp(), opportunity=do(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit serving urban public-housing "
                    "residents in Brooklyn.",
                    planted=False, tag="advx08-grounded",
                ),
                Sentence(
                    "As of the date of application, the organization has no outstanding "
                    "federal compliance issues, debarments, or suspensions on record.",
                    planted=True, tag="advx-negation-compliance-record",
                ),
            ],
        )
    )

    # 9. BURIED ERROR: correct project type and location, wrong system size deep in.
    cases.append(
        EvalCase(
            name="advx/buried-wrong-size",
            profile=dp(), opportunity=do(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The proposed rooftop solar project is located in urban Brooklyn, "
                    "a disadvantaged community.",
                    planted=False, tag="advx09-grounded-1",
                ),
                Sentence(
                    "The organization is an established 501(c)(3) nonprofit.",
                    planted=False, tag="advx09-grounded-2",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "The 150 kilowatt system will serve the surrounding district and "
                    "reduce energy costs for public-housing residents.",
                    planted=True, tag="advx-buried-150kw-vs-120kw",
                ),
            ],
        )
    )

    # 10. PARTIAL TRUTH: real mission + fabricated outcome metric in one sentence.
    cases.append(
        EvalCase(
            name="advx/partial-truth-outcome-metric",
            profile=p(), opportunity=o(), difficulty="adversarial",
            boilerplate_sentences=[
                Sentence(
                    "Our mission to bring solar to low-income households has resulted in a "
                    "documented 40 percent reduction in energy costs for participants.",
                    planted=True, tag="advx-partial-40pct-reduction",
                ),
                Sentence(
                    "The organization serves disadvantaged communities in California.",
                    planted=False, tag="advx10-grounded",
                ),
            ],
        )
    )

    # 11. UNSTATED INFERENCE: community solar does not imply grid interconnection
    # agreements.
    cases.append(
        EvalCase(
            name="advx/unstated-grid-agreement",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The community solar project has secured grid interconnection "
                    "agreements with the local utility.",
                    planted=True, tag="advx-unstated-grid-interconnect",
                ),
                Sentence(
                    "The project targets low-income and rural households.",
                    planted=False, tag="advx11-grounded",
                ),
            ],
        )
    )

    # 12. OVERSTATED GEOGRAPHY: profile says CA, claim says "West Coast operations
    # spanning California, Oregon, and Washington."
    cases.append(
        EvalCase(
            name="advx/overstated-three-states",
            profile=p(), opportunity=o(), difficulty="adversarial",
            boilerplate_sentences=[
                Sentence(
                    "Our West Coast operations span California, Oregon, and Washington, "
                    "enabling broad regional impact.",
                    planted=True, tag="advx-overstated-three-states",
                ),
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit.",
                    planted=False, tag="advx12-grounded",
                ),
            ],
        )
    )

    # 13. INVENTED PARTNERSHIP buried in boilerplate: sounds credible but not in profile.
    cases.append(
        EvalCase(
            name="advx/invented-epa-partnership",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The applicant serves a disadvantaged community in California.",
                    planted=False, tag="advx13-grounded",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "The organization is an EPA Green Power Partner, demonstrating its "
                    "commitment to renewable energy standards.",
                    planted=True, tag="advx-invented-epa-partner",
                ),
            ],
        )
    )

    # 14. TEMPORAL CONTRADICTION: profile stage is "planning", claim says "completed
    # Phase 1 installation."
    cases.append(
        EvalCase(
            name="advx/temporal-phase1-complete",
            profile=dp(), opportunity=do(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization is a 501(c)(3) serving low-income residents.",
                    planted=False, tag="advx14-grounded",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Having completed Phase 1 of the installation, the organization "
                    "is now seeking funds for Phase 2 expansion.",
                    planted=True, tag="advx-temporal-phase1-done",
                ),
            ],
        )
    )

    # 15. CLOSE NUMBER: award ceiling is 250k, claim says "up to 260,000 dollars."
    cases.append(
        EvalCase(
            name="advx/close-number-award-ceiling",
            profile=dp(), opportunity=do(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The program provides awards of up to 260,000 dollars for qualifying "
                    "nonprofit applicants.",
                    planted=True, tag="advx-close-260k-ceiling",
                ),
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit.",
                    planted=False, tag="advx15-grounded",
                ),
            ],
        )
    )

    # 16. DENSE CONTEXT BURIAL: three grounded sentences, then one subtle fabrication
    # about staff count.
    cases.append(
        EvalCase(
            name="advx/dense-burial-staff-count",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit in California.",
                    planted=False, tag="advx16-grounded-1",
                ),
                Sentence(
                    "The organization has operated for eight years.",
                    planted=False, tag="advx16-grounded-2",
                ),
                Sentence(
                    "Its annual budget is 500,000 dollars.",
                    planted=False, tag="advx16-grounded-3",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "A team of 45 full-time staff members manages solar installations "
                    "across the service area.",
                    planted=True, tag="advx-buried-45-staff",
                ),
            ],
        )
    )

    # 17. PARTIAL TRUTH: real geography + fabricated certification in one clause.
    cases.append(
        EvalCase(
            name="advx/partial-truth-certification",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "Operating in a designated disadvantaged community in California and "
                    "holding NABCEP certification for solar installation, the applicant "
                    "is well positioned for this grant.",
                    planted=True, tag="advx-partial-nabcep-cert",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Our mission is to bring solar to low-income households.",
                    planted=False, tag="advx17-grounded",
                ),
            ],
        )
    )

    # 18. INVENTED ELIGIBILITY: claims tribal energy authority designation.
    cases.append(
        EvalCase(
            name="advx/invented-tribal-energy",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization qualifies under the DOE Tribal Energy Authority "
                    "designation for enhanced funding consideration.",
                    planted=True, tag="advx-invented-tribal-energy",
                ),
                Sentence(
                    "The applicant requests 250,000 dollars for community solar.",
                    planted=False, tag="advx18-grounded",
                ),
            ],
        )
    )

    # 19. PRECISION TRAP (hard negative): sounds aggressive but IS grounded.
    # Profile says 500k budget, 8 years, CA, disadvantaged, low-income + rural.
    # This sentence restates those facts assertively. Should NOT be flagged.
    cases.append(
        EvalCase(
            name="advx/precision-trap-assertive-grounded",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "With eight years of operations and a half-million dollar annual "
                    "budget, the organization has the institutional capacity to execute "
                    "this community solar project in a disadvantaged California community.",
                    planted=False, tag="advx19-precision-grounded",
                ),
            ],
        )
    )

    # 20. CLOSE NUMBER + PARTIAL TRUTH: project cost 600k (detailed profile), claim
    # says 580k — close but wrong, embedded in otherwise correct context.
    cases.append(
        EvalCase(
            name="advx/close-number-project-cost",
            profile=dp(), opportunity=do(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The rooftop solar project in urban Brooklyn has a total estimated "
                    "cost of 580,000 dollars.",
                    planted=True, tag="advx-close-580k-vs-600k",
                ),
                Sentence(
                    "The applicant is a 501(c)(3) serving public-housing residents.",
                    planted=False, tag="advx20-grounded",
                ),
            ],
        )
    )

    return cases
