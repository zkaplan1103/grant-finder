"""Cross-domain eval cases: community health / medical.

Tests Verify agent generalization to HHS/HRSA-style health center funding.
Uses Profile/Opportunity/Draft models with medical-domain content.
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


def _health_center_profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=3_500_000, org_age_years=22),
        project_type="community health",
        funding_preference=FundingPreference.GRANT,
        geography=Geo(
            state="MS", service_area="rural Delta region",
            disadvantaged_community=True,
        ),
        project=ProjectSpecifics(
            project_type="federally qualified health center expansion",
            estimated_cost_usd=1_800_000,
            amount_needed_usd=750_000,
        ),
        mission=MissionPopulations(
            mission_statement=(
                "Deliver primary care, behavioral health, and dental services to "
                "uninsured and underinsured residents of the Mississippi Delta."
            ),
            populations_served=["uninsured", "underinsured", "rural"],
        ),
    )


def _health_center_opp() -> Opportunity:
    return Opportunity(
        id="OPP-HRSA-HC",
        source=OpportunitySource.GRANTS_GOV,
        title="HRSA Health Center Cluster — New Access Points",
        agency="HHS",
        status="posted",
        aln="93.224",
        eligibility_notes=(
            "Eligible applicants must be 501(c)(3) organizations or public entities "
            "that operate as Federally Qualified Health Centers or FQHC Look-Alikes. "
            "Applicants must serve a designated Medically Underserved Area or "
            "Medically Underserved Population. A sliding-fee schedule based on "
            "ability to pay is required. Organizations must have operated for at "
            "least five years. Maximum award is 650,000 dollars per year for three "
            "years."
        ),
        description=(
            "HRSA New Access Points funding supports the establishment of new health "
            "center service delivery sites in medically underserved communities. "
            "Funding covers primary medical, dental, behavioral health, and enabling "
            "services for uninsured and underinsured populations."
        ),
    )


def load_medical_cases() -> List[EvalCase]:
    p, o = _health_center_profile, _health_center_opp
    cases: List[EvalCase] = []

    # 1. Entity fabrication: invented FQHC designation (obvious)
    cases.append(
        EvalCase(
            name="med/invented-fqhc-designation",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit providing primary care in "
                    "the Mississippi Delta.",
                    planted=False, tag="med-501c3-grounded",
                ),
                Sentence(
                    "The organization holds full Federally Qualified Health Center "
                    "designation from HRSA.",
                    planted=True, tag="med-fqhc-designation",
                    hallucination_type="entity-fabrication",
                ),
            ],
        )
    )

    # 2. Quantity distortion: inflated patient volume (adversarial)
    cases.append(
        EvalCase(
            name="med/inflated-patient-volume",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization has operated continuously for twenty-two years.",
                    planted=False, tag="med-tenure-grounded",
                ),
                Sentence(
                    # Parrots the opp's MUA requirement; the profile says rural
                    # Delta / uninsured, never a federal MUA designation.
                    "The health center serves a designated Medically Underserved Area "
                    "in the rural Delta region.",
                    planted=True, tag="med-mua-designation-claim",
                    hallucination_type="unsupported-eligibility",
                ),
                Sentence(
                    # Parrots the opp's sliding-fee requirement; the profile never
                    # mentions any fee policy.
                    "A sliding-fee schedule based on ability to pay is in place for "
                    "all patients.",
                    planted=True, tag="med-sliding-fee-claim",
                    hallucination_type="unsupported-eligibility",
                ),
                Sentence(
                    "Last year the center provided care to over 85,000 unique patients "
                    "across its service area.",
                    planted=True, tag="med-85000-patients",
                    hallucination_type="quantity-distortion",
                ),
            ],
        )
    )

    # 3. Scope inflation: claims specialty services not in profile (adversarial)
    cases.append(
        EvalCase(
            name="med/scope-inflation-specialty",
            profile=p(), opportunity=o(), difficulty="adversarial",
            boilerplate_sentences=[
                Sentence(
                    "The mission of the center is to deliver primary care, behavioral "
                    "health, and dental services to underserved residents.",
                    planted=False, tag="med-mission-grounded",
                ),
                Sentence(
                    "The center also operates a Level II trauma unit and a neonatal "
                    "intensive care ward.",
                    planted=True, tag="med-trauma-nicu",
                    hallucination_type="scope-inflation",
                ),
            ],
        )
    )

    # 4. Negation flip: opp requires sliding-fee; claim says fee-for-service (obvious)
    cases.append(
        EvalCase(
            name="med/negation-flip-fee-model",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    # Populations are profile-stated, but the MUA designation is
                    # only in the opp's eligibility notes — never in the profile.
                    "The applicant serves uninsured and underinsured populations in "
                    "a rural Medically Underserved Area.",
                    planted=True, tag="med-mua-populations-claim",
                    hallucination_type="unsupported-eligibility",
                ),
                Sentence(
                    "The center operates on a strict fee-for-service model with no "
                    "sliding-scale discounts.",
                    planted=True, tag="med-fee-for-service",
                    hallucination_type="negation-flip",
                ),
            ],
        )
    )

    # 5. Attribution shift: wrong federal agency (adversarial)
    cases.append(
        EvalCase(
            name="med/attribution-shift-agency",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The organization requests 750,000 dollars for health center "
                    "expansion.",
                    planted=False, tag="med-amount-grounded",
                ),
                Sentence(
                    "The center is currently accredited by the Centers for Medicare "
                    "and Medicaid Services as a Critical Access Hospital.",
                    planted=True, tag="med-cms-cah-accreditation",
                    hallucination_type="attribution-shift",
                ),
            ],
        )
    )

    # 6. Clean draft — no planted claims
    cases.append(
        EvalCase(
            name="med/clean-no-planted",
            profile=p(), opportunity=o(), difficulty="obvious",
            eligibility_sentences=[
                Sentence(
                    "The applicant is a 501(c)(3) nonprofit that has operated for "
                    "twenty-two years in the Mississippi Delta.",
                    planted=False, tag="med-clean-elig-1",
                ),
                Sentence(
                    "Services target uninsured and underinsured residents of the "
                    "rural Mississippi Delta.",
                    planted=False, tag="med-clean-elig-2",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "The center delivers primary medical, dental, and behavioral "
                    "health services to residents of the Mississippi Delta.",
                    planted=False, tag="med-clean-boiler-1",
                ),
            ],
        )
    )

    # 7. High claim density: 2 planted in eligibility + 1 in boilerplate (hard)
    cases.append(
        EvalCase(
            name="med/high-density-three-planted",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence(
                    "The organization has served the Delta region for over two decades.",
                    planted=False, tag="med-hd-grounded",
                ),
                Sentence(
                    "The center maintains Joint Commission accreditation for ambulatory "
                    "care excellence.",
                    planted=True, tag="med-joint-commission",
                    hallucination_type="entity-fabrication",
                ),
                Sentence(
                    "Its patient satisfaction scores exceed the 99th national percentile "
                    "as measured by Press Ganey surveys.",
                    planted=True, tag="med-99th-percentile",
                    hallucination_type="quantity-distortion",
                ),
            ],
            boilerplate_sentences=[
                Sentence(
                    "Under a cooperative agreement with the National Institutes of Health, "
                    "the center conducts clinical trials for diabetes interventions.",
                    planted=True, tag="med-nih-trials",
                    hallucination_type="attribution-shift",
                ),
            ],
        )
    )

    # 8. Arithmetic: ask exceeds award ceiling (hard)
    cases.append(
        EvalCase(
            name="med/arithmetic-over-ceiling",
            profile=p(), opportunity=o(), difficulty="hard",
            eligibility_sentences=[
                Sentence(
                    # 501(c)(3) is profile-stated, but the MUA designation is only
                    # in the opp's eligibility notes — never in the profile.
                    "The applicant is a 501(c)(3) serving a Medically Underserved Area.",
                    planted=True, tag="med-mua-501c3-claim",
                    hallucination_type="unsupported-eligibility",
                ),
                Sentence(
                    "The 750,000 dollar request is within the program's stated annual "
                    "award maximum.",
                    planted=True, tag="med-over-ceiling",
                    hallucination_type="quantity-distortion",
                ),
            ],
        )
    )

    # 9. Temporal misstatement: claims recent founding (obvious)
    cases.append(
        EvalCase(
            name="med/temporal-recent-founding",
            profile=p(), opportunity=o(), difficulty="obvious",
            boilerplate_sentences=[
                Sentence(
                    "The center delivers primary care to rural populations.",
                    planted=False, tag="med-primary-grounded",
                ),
                Sentence(
                    "Established only three years ago, the organization has grown "
                    "rapidly to meet community demand.",
                    planted=True, tag="med-three-year-founding",
                    hallucination_type="temporal-state-error",
                ),
            ],
        )
    )

    # 10. Unstated inference: primary care doesn't imply pharmacy (adversarial)
    cases.append(
        EvalCase(
            name="med/unstated-pharmacy",
            profile=p(), opportunity=o(), difficulty="adversarial",
            eligibility_sentences=[
                Sentence(
                    "The center provides primary medical, behavioral health, and dental "
                    "services.",
                    planted=False, tag="med-services-grounded",
                ),
                Sentence(
                    "The on-site 340B pharmacy dispenses over 50,000 prescriptions "
                    "annually at reduced cost.",
                    planted=True, tag="med-340b-pharmacy",
                    hallucination_type="unstated-technical",
                ),
            ],
        )
    )

    return cases
