"""Shared fixtures."""

import pytest

from app.models import (
    FundingPreference,
    Match,
    Opportunity,
    OpportunitySource,
    OrgBasics,
    Profile,
    ProjectType,
)


@pytest.fixture
def full_profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=500_000, org_age_years=8),
        project_type=ProjectType.SOLAR,
        funding_preference=FundingPreference.GRANT,
        geography={"state": "CA", "disadvantaged_community": True},
        project={"project_type": "community solar", "amount_needed_usd": 250_000},
        mission={
            "mission_statement": "Bring solar to low-income households.",
            "populations_served": ["low-income", "rural"],
        },
    )


@pytest.fixture
def sparse_profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=100_000, org_age_years=2),
        project_type=ProjectType.SOLAR,
        funding_preference=FundingPreference.EITHER,
    )


@pytest.fixture
def opportunity() -> Opportunity:
    return Opportunity(
        id="OPP-1",
        source=OpportunitySource.GRANTS_GOV,
        title="Solar Energy Innovation Grant",
        agency="DOE",
        status="posted",
        aln="81.087",
        eligibility_notes="Open to 501(c)(3) nonprofits serving disadvantaged communities.",
        description="Funds community solar in low-income areas.",
    )


@pytest.fixture
def strong_match() -> Match:
    return Match(
        opportunity_id="OPP-1",
        fit_score=0.88,
        reasoning="Strong mission and geographic alignment.",
    )
