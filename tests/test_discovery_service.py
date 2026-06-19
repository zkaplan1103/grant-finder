"""Discovery service: combines curated + live grants.gov, degrades gracefully."""

import os

from app.discovery.grants_gov import GrantsGovTimeout
from app.discovery.service import discover
from app.models import (
    FundingPreference,
    Opportunity,
    OpportunitySource,
    OrgBasics,
    Profile,
    ProjectType,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "curated_fixture.yaml")


def _profile():
    return Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=200_000, org_age_years=5),
        project_type=ProjectType.SOLAR,
        funding_preference=FundingPreference.GRANT,
    )


class FakeGrantsClient:
    def __init__(self, hits=None, raise_exc=None):
        self._hits = hits or []
        self._raise = raise_exc

    def search(self, params):
        if self._raise:
            raise self._raise
        return self._hits

    def fetch_details(self, opp_id):
        return None


def test_curated_only_when_no_client():
    res = discover(_profile(), grants_client=None, curated_path=FIXTURE)
    assert res.grants_gov_ok is True
    assert all(o.source == OpportunitySource.CURATED for o in res.opportunities)
    assert len(res.opportunities) == 2


def test_combines_curated_and_live_hits():
    hits = [Opportunity(id="G1", source=OpportunitySource.GRANTS_GOV, title="Live Grant")]
    res = discover(_profile(), grants_client=FakeGrantsClient(hits=hits), curated_path=FIXTURE)
    sources = {o.source for o in res.opportunities}
    assert OpportunitySource.CURATED in sources
    assert OpportunitySource.GRANTS_GOV in sources
    assert res.grants_gov_ok is True


def test_grants_gov_failure_degrades_to_curated():
    res = discover(
        _profile(),
        grants_client=FakeGrantsClient(raise_exc=GrantsGovTimeout("grants.gov request timed out")),
        curated_path=FIXTURE,
    )
    assert res.grants_gov_ok is False
    assert res.grants_gov_message == "grants.gov request timed out"
    # Curated results still present.
    assert len(res.opportunities) == 2
    assert all(o.source == OpportunitySource.CURATED for o in res.opportunities)
