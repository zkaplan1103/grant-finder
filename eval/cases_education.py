"""Cross-domain eval cases: education / after-school STEM.

Tests Verify agent generalization to DOE/NSF education grant content.
Uses Profile/Opportunity/Draft models with education-domain text.
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


def _education_profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=800_000, org_age_years=6),
        project_type="STEM education",
        funding_preference=FundingPreference.GRANT,
        geography=Geo(
            state="GA", service_area="Atlanta metro Title I schools",
            disadvantaged_community=True,
        ),
        project=ProjectSpecifics(
            project_type="after-school STEM enrichment",
            estimated_cost_usd=400_000,
            amount_needed_usd=200_000,
        ),
        mission=MissionPopulations(
            mission_statement=(
                "Close the STEM opportunity gap by providing free after-school "
                "robotics, coding, and math enrichment to students at Title I "
                "schools in metro Atlanta."
            ),
            populations_served=["Title I students", "underrepresented minorities in STEM"],
        ),
    )


def _education_opp() -> Opportunity:
    return Opportunity(
        id="OPP-NSF-EDU",
        source=OpportunitySource.GRANTS_GOV,
        title="NSF ITEST — Innovative Technology Experiences for Students and Teachers",
        agency="NSF",
        status="posted",
        aln="47.076",
        eligibility_notes=(
            "Eligible applicants include 501(c)(3) nonprofit organizations, institutions "
            "of higher education, and school districts. Projects must target students in "
            "grades K-12 who are underrepresented in STEM fields. Applicants must "
            "demonstrate partnerships with at least one school or school district. "
            "Prior NSF funding is not required. Maximum award is 400,000 dollars over "
            "three years."
        ),
        description=(
            "NSF ITEST supports projects that engage K-12 students in technology-rich "
            "experiences to build their capacity in STEM disciplines. Funded activities "
            "include after-school and summer programs, curriculum integration, teacher "
            "professional development, and research on effective STEM engagement "
            "strategies for underrepresented populations."
        ),
    )


def load_education_cases() -> List[EvalCase]:
    p, o = _education_profile, _education_opp
    cases: List[EvalCase] = []

    # 1. Entity fabrication: invented NSF prior award (obvious)
    cases.append(
        EvalCase(
            name="edu/invented-prior-nsf-award",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit serving students at Title I "
                    "schools in metro Atlanta.",
                    planted=False, tag="edu-501c3-grounded",
                ),
                Sentence(
                    "The organization previously received an NSF CAREER award of "
                    "1.2 million dollars for computational thinking research.",
                    planted=True, tag="edu-nsf-career-award",
                    hallucination_type="entity-fabrication",
                ),
            ],
        )
    )

    # 2. Quantity distortion: inflated student reach (adversarial)
    cases.append(
        EvalCase(
            name="edu/inflated-student-reach",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization targets students in grades K-12 who are "
                    "underrepresented in STEM fields.",
                    planted=False, tag="edu-k12-grounded",
                ),
                Sentence(
                    "The program partners with Title I schools in the Atlanta metro "
                    "area, satisfying the partnership requirement.",
                    planted=False, tag="edu-partnership-grounded",
                ),
                Sentence(
                    "Since its founding the program has served over 30,000 students "
                    "across 75 school sites.",
                    planted=True, tag="edu-30000-students",
                    hallucination_type="quantity-distortion",
                ),
            ],
        )
    )

    # 3. Scope inflation: claims teacher certification program (adversarial)
    cases.append(
        EvalCase(
            name="edu/scope-inflation-certification",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The project provides free after-school robotics, coding, and math "
                    "enrichment.",
                    planted=False, tag="edu-enrichment-grounded",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Our mission is to close the STEM opportunity gap for "
                    "underrepresented minorities.",
                    planted=False, tag="edu-mission-grounded",
                ),
                Sentence(
                    "The organization also operates a state-accredited teacher "
                    "certification program that has credentialed over 200 STEM "
                    "educators.",
                    planted=True, tag="edu-teacher-certification",
                    hallucination_type="scope-inflation",
                ),
            ],
        )
    )

    # 4. Negation flip: claims grades 9-16 / post-secondary (opp says K-12) (obvious)
    cases.append(
        EvalCase(
            name="edu/negation-flip-post-secondary",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    "The applicant requests 200,000 dollars for STEM enrichment "
                    "activities.",
                    planted=False, tag="edu-amount-grounded",
                ),
                Sentence(
                    "The program exclusively serves post-secondary students enrolled "
                    "in community college STEM tracks.",
                    planted=True, tag="edu-post-secondary-only",
                    hallucination_type="negation-flip",
                ),
            ],
        )
    )

    # 5. Attribution shift: claims partnership with wrong entity (adversarial)
    cases.append(
        EvalCase(
            name="edu/attribution-shift-nasa",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The program targets underrepresented minorities in STEM at "
                    "Title I schools.",
                    planted=False, tag="edu-urm-grounded",
                ),
                Sentence(
                    "Under a Space Act Agreement with NASA, the organization provides "
                    "students access to satellite data for classroom projects.",
                    planted=True, tag="edu-nasa-agreement",
                    hallucination_type="attribution-shift",
                ),
            ],
        )
    )

    # 6. Clean draft — no planted claims
    cases.append(
        EvalCase(
            name="edu/clean-no-planted",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) providing after-school STEM "
                    "enrichment to K-12 students at Title I schools.",
                    planted=False, tag="edu-clean-elig-1",
                ),
                Sentence(
                    "The organization has operated for six years in the Atlanta "
                    "metro area.",
                    planted=False, tag="edu-clean-elig-2",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Our programs in robotics, coding, and math target students "
                    "underrepresented in STEM fields.",
                    planted=False, tag="edu-clean-boiler-1",
                ),
            ],
        )
    )

    # 7. High claim density: 3 planted across eligibility and boilerplate (hard)
    cases.append(
        EvalCase(
            name="edu/high-density-three-planted",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) serving underrepresented K-12 "
                    "students.",
                    planted=False, tag="edu-hd-grounded",
                ),
                Sentence(
                    "The organization has been recognized by the White House as a "
                    "Champion of Change for STEM equity.",
                    planted=True, tag="edu-white-house-champion",
                    hallucination_type="entity-fabrication",
                ),
                Sentence(
                    "Independent evaluation shows a 45 percentage point increase in "
                    "AP STEM exam pass rates among program participants.",
                    planted=True, tag="edu-45-point-increase",
                    hallucination_type="quantity-distortion",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "The Georgia Department of Education has designated the "
                    "organization as the official STEM pipeline partner for all "
                    "Title I schools in the state.",
                    planted=True, tag="edu-state-designation",
                    hallucination_type="attribution-shift",
                ),
            ],
        )
    )

    # 8. Arithmetic: ask exceeds per-year ceiling when annualized (hard)
    # Opp says max 400k over 3 years = ~133k/yr; ask is 200k for enrichment.
    # Claim that the request "falls within annual limits" is false.
    cases.append(
        EvalCase(
            name="edu/arithmetic-annual-ceiling",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence(
                    "The organization serves Title I schools in metro Atlanta.",
                    planted=False, tag="edu-arith-grounded",
                ),
                Sentence(
                    "The 200,000 dollar annual request falls within the program's "
                    "per-year award limit.",
                    planted=True, tag="edu-annual-ceiling-wrong",
                    hallucination_type="quantity-distortion",
                ),
            ],
        )
    )

    # 9. Temporal misstatement: org is 6 years old, claims a decade (obvious)
    cases.append(
        EvalCase(
            name="edu/temporal-decade-claim",
            profile=p(), opportunity=o(), difficulty="obvious",
            boilerplate_sentences=[
                Sentence(
                    "The program provides robotics and coding enrichment to "
                    "underrepresented students.",
                    planted=False, tag="edu-robotics-grounded",
                ),
                Sentence(
                    "Over the past decade the organization has built deep relationships "
                    "with school administrators throughout Georgia.",
                    planted=True, tag="edu-decade-vs-6yr",
                    hallucination_type="temporal-state-error",
                ),
            ],
        )
    )

    # 10. Unstated inference: after-school STEM doesn't imply research (adversarial)
    cases.append(
        EvalCase(
            name="edu/unstated-research-arm",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization operates after-school STEM enrichment programs.",
                    planted=False, tag="edu-afterschool-grounded",
                ),
                Sentence(
                    "Its internal research division has published fourteen peer-reviewed "
                    "studies on STEM pedagogy in underserved communities.",
                    planted=True, tag="edu-research-division",
                    hallucination_type="unstated-technical",
                ),
            ],
        )
    )

    return cases
