"""Phase 7 done-condition: TestClient hits the form and a results route with the
WHOLE pipeline mocked (no live calls); error state renders without leaking internals.
"""

import pytest
from fastapi.testclient import TestClient

from app.models import (
    Draft,
    DraftStatus,
    Match,
    Opportunity,
    OpportunitySource,
    UnsupportedClaim,
)
from app.orchestrator import MatchedOpportunity, PipelineResult
from app.web.app import app
from app.web.pipeline import FullResult, PipelineConfigError


@pytest.fixture
def client():
    return TestClient(app)


def _good_form():
    return {
        "is_501c3": "true",
        "annual_budget_usd": "500000",
        "org_age_years": "8",
        "project_type": "solar",
        "funding_preference": "grant",
        "state": "CA",
        "populations_served": "low-income, rural",
    }


def _fake_full_result(*, sparse=False, grants_ok=True):
    opp = Opportunity(
        id="OPP-1",
        source=OpportunitySource.GRANTS_GOV,
        title="Solar Innovation Grant",
        agency="DOE",
        url="https://www.grants.gov/x/OPP-1",
    )
    match = Match(opportunity_id="OPP-1", fit_score=0.87, reasoning="Strong fit.", low_confidence=sparse)
    draft = Draft(
        opportunity_id="OPP-1",
        eligibility_summary="Eligible as a 501(c)(3).",
        boilerplate="We are a nonprofit serving low-income households.",
        status=DraftStatus.VERIFIED,
    )
    pipeline = PipelineResult(
        profile_sparse=sparse,
        results=[MatchedOpportunity(opportunity=opp, match=match, draft=draft)],
    )
    return FullResult(pipeline=pipeline, grants_gov_ok=grants_ok, grants_gov_message=None)


def test_form_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Find funding matches" in resp.text
    assert "501(c)(3)" in resp.text


def test_results_with_mocked_pipeline(client):
    app.state.run_pipeline = lambda profile: _fake_full_result()
    try:
        resp = client.post("/results", data=_good_form())
    finally:
        app.state.run_pipeline = None  # reset
    assert resp.status_code == 200
    assert "Solar Innovation Grant" in resp.text
    assert "87% fit" in resp.text
    assert "verified" in resp.text.lower()


def test_results_shows_needs_human_with_claims(client):
    def runner(profile):
        opp = Opportunity(id="OPP-2", source=OpportunitySource.CURATED, title="Curated Grant")
        match = Match(opportunity_id="OPP-2", fit_score=0.7, reasoning="ok")
        draft = Draft(
            opportunity_id="OPP-2",
            eligibility_summary="s",
            boilerplate="b",
            status=DraftStatus.NEEDS_HUMAN,
            revision=3,
            unresolved_claims=[UnsupportedClaim(claim="Serves 10k", reason="Not in profile")],
        )
        return FullResult(
            pipeline=PipelineResult(
                profile_sparse=False,
                results=[MatchedOpportunity(opportunity=opp, match=match, draft=draft)],
            ),
            grants_gov_ok=True,
            grants_gov_message=None,
        )

    app.state.run_pipeline = runner
    try:
        resp = client.post("/results", data=_good_form())
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 200
    assert "Serves 10k" in resp.text
    assert "Not in profile" in resp.text


def test_grants_gov_unreachable_banner(client):
    app.state.run_pipeline = lambda p: FullResult(
        pipeline=PipelineResult(profile_sparse=False, results=[]),
        grants_gov_ok=False,
        grants_gov_message="grants.gov is unreachable",
    )
    try:
        resp = client.post("/results", data=_good_form())
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 200
    assert "unavailable" in resp.text.lower()
    assert "curated sources only" in resp.text.lower()


def test_sparse_profile_banner(client):
    app.state.run_pipeline = lambda p: _fake_full_result(sparse=True)
    try:
        # minimal required-only form
        resp = client.post(
            "/results",
            data={
                "is_501c3": "true",
                "annual_budget_usd": "100000",
                "org_age_years": "2",
                "project_type": "solar",
                "funding_preference": "either",
            },
        )
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 200
    assert "limited information" in resp.text.lower()


def test_invalid_form_friendly_400(client):
    resp = client.post("/results", data={"project_type": "solar"})  # missing required
    assert resp.status_code == 400
    assert "required fields" in resp.text.lower()


def test_config_error_is_sanitized(client):
    # Simulate the no-API-key path. The error message must not leak internals.
    def runner(profile):
        raise PipelineConfigError(
            "The matching service is not configured. An administrator must set the "
            "API credentials before running matches."
        )

    app.state.run_pipeline = runner
    try:
        resp = client.post("/results", data=_good_form())
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 503
    assert "not configured" in resp.text.lower()
    # No secret/internal leakage.
    assert "ANTHROPIC_API_KEY" not in resp.text
    assert "Traceback" not in resp.text


def test_unexpected_error_is_sanitized(client):
    def runner(profile):
        raise RuntimeError("boom secret-internal-detail sk-ant-xyz")

    app.state.run_pipeline = runner
    try:
        resp = client.post("/results", data=_good_form())
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 500
    # The raw exception text (and any secret-looking material) must not appear.
    assert "boom" not in resp.text
    assert "sk-ant" not in resp.text
    assert "Traceback" not in resp.text
    assert "something went wrong" in resp.text.lower()
