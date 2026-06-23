"""Phase 6 done-condition: against a temp/in-memory SQLite db, insert + read
back each entity; schema creates idempotently.
"""

import pytest

from app.db import Database
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
)


@pytest.fixture
def db():
    d = Database(":memory:")
    yield d
    d.close()


def _profile() -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=300_000, org_age_years=6),
        project_type="solar",
        funding_preference=FundingPreference.GRANT,
        geography={"state": "CA"},
    )


def test_schema_creates_idempotently(db):
    db.init_schema()
    db.init_schema()  # no error on re-create


def test_profile_insert_and_read_back(db):
    p = _profile()
    pid = db.insert_profile(p)
    assert isinstance(pid, int)
    got = db.get_profile(pid)
    assert got == p


def test_get_missing_profile_returns_none(db):
    assert db.get_profile(999) is None


def test_opportunity_upsert_and_read(db):
    opp = Opportunity(
        id="OPP-9",
        source=OpportunitySource.GRANTS_GOV,
        title="Solar Grant",
        agency="DOE",
        eligibility_notes="501(c)(3).",
    )
    db.upsert_opportunity(opp)
    assert db.get_opportunity("OPP-9") == opp

    # Upsert updates rather than duplicating.
    updated = opp.model_copy(update={"title": "Solar Grant (updated)"})
    db.upsert_opportunity(updated)
    assert db.get_opportunity("OPP-9").title == "Solar Grant (updated)"


def test_match_insert_and_read_back_sorted(db):
    pid = db.insert_profile(_profile())
    db.insert_match(pid, Match(opportunity_id="A", fit_score=0.3, reasoning="weak"))
    db.insert_match(pid, Match(opportunity_id="B", fit_score=0.9, reasoning="strong"))
    matches = db.get_matches_for_profile(pid)
    assert [m.opportunity_id for m in matches] == ["B", "A"]  # sorted by fit_score desc


def test_draft_insert_and_read_back_with_nested(db):
    pid = db.insert_profile(_profile())
    draft = Draft(
        opportunity_id="OPP-9",
        eligibility_summary="Eligible.",
        boilerplate="We are a nonprofit.",
        status=DraftStatus.NEEDS_HUMAN,
        revision=2,
        unresolved_claims=[UnsupportedClaim(claim="x", reason="y")],
    )
    db.insert_draft(pid, draft)
    drafts = db.get_drafts_for_profile(pid)
    assert len(drafts) == 1
    assert drafts[0] == draft
    assert drafts[0].unresolved_claims[0].claim == "x"
