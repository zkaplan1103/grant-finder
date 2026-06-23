"""Phase 1 done-condition: round-trip each model; a sparse profile validates."""

import pytest
from pydantic import ValidationError

from app.models import (
    Draft,
    DraftStatus,
    FundingPreference,
    Match,
    Opportunity,
    OpportunitySource,
    OrgBasics,
    Profile,
    UnsupportedClaim,
    VerifyResult,
)


def _full_profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=500_000, org_age_years=8),
        project_type="solar",
        funding_preference=FundingPreference.GRANT,
        geography={"state": "CA", "disadvantaged_community": True},
        project={"project_type": "community solar", "size_kw": 120.0, "amount_needed_usd": 250_000},
        mission={
            "mission_statement": "Bring solar to low-income households.",
            "populations_served": ["low-income", "rural"],
        },
    )


def _sparse_profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=100_000, org_age_years=2),
        project_type="solar",
        funding_preference=FundingPreference.EITHER,
    )


def _roundtrip(model):
    cls = type(model)
    again = cls.model_validate(model.model_dump())
    assert again == model
    again_json = cls.model_validate_json(model.model_dump_json())
    assert again_json == model


def test_profile_roundtrip_full():
    _roundtrip(_full_profile())


def test_profile_roundtrip_sparse():
    p = _sparse_profile()
    _roundtrip(p)
    assert p.is_sparse() is True


def test_full_profile_is_not_sparse():
    assert _full_profile().is_sparse() is False


def test_profile_requires_core_fields():
    with pytest.raises(ValidationError):
        Profile(project_type="solar", funding_preference=FundingPreference.GRANT)
    with pytest.raises(ValidationError):
        Profile(
            org_basics=OrgBasics(is_501c3=True, annual_budget_usd=1, org_age_years=1),
            funding_preference=FundingPreference.GRANT,
        )


def test_negative_budget_rejected():
    with pytest.raises(ValidationError):
        OrgBasics(is_501c3=True, annual_budget_usd=-1, org_age_years=1)


def test_opportunity_roundtrip():
    _roundtrip(
        Opportunity(
            id="OPP-1",
            source=OpportunitySource.GRANTS_GOV,
            title="Solar Energy Innovation",
            agency="DOE",
            status="posted",
            aln="81.087",
        )
    )
    _roundtrip(
        Opportunity(
            id="solar-moonshot",
            source=OpportunitySource.CURATED,
            title="Solar Moonshot Program",
            typical_award="$10k-$100k",
            eligibility_notes="501(c)(3) nonprofits.",
        )
    )


def test_match_roundtrip_and_bounds():
    _roundtrip(
        Match(
            opportunity_id="OPP-1",
            fit_score=0.82,
            reasoning="Strong geographic and mission alignment.",
            low_confidence=False,
        )
    )
    with pytest.raises(ValidationError):
        Match(opportunity_id="x", fit_score=1.5, reasoning="bad")


def test_verify_result_roundtrip():
    _roundtrip(VerifyResult(passed=True))
    _roundtrip(
        VerifyResult(
            passed=False,
            failures=[UnsupportedClaim(claim="Org is in TX", reason="Profile says CA")],
        )
    )


def test_draft_roundtrip_with_nested_unresolved():
    _roundtrip(
        Draft(
            opportunity_id="OPP-1",
            eligibility_summary="Eligible as a 501(c)(3).",
            boilerplate="We are a nonprofit...",
            status=DraftStatus.NEEDS_HUMAN,
            revision=2,
            unresolved_claims=[UnsupportedClaim(claim="Serves 10k people", reason="Not in profile")],
        )
    )
