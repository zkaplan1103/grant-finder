"""JSON API tests: TestClient hits POST /api/match with the WHOLE pipeline mocked
(no live calls); error states return sanitized JSON without leaking internals.
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
    # Fresh guard per test so rate-limit state from one test can't 429 the next.
    from app.web.guard import GuardState
    app.state.guard = GuardState()
    return TestClient(app)


def _good_profile():
    return {
        "org_basics": {"is_501c3": True, "annual_budget_usd": 500000, "org_age_years": 8},
        "project_type": "solar",
        "funding_preference": "grant",
        "geography": {"state": "CA"},
        "mission": {"populations_served": ["low-income", "rural"]},
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


def test_match_with_mocked_pipeline(client):
    app.state.run_pipeline = lambda profile: _fake_full_result()
    try:
        resp = client.post("/api/match", json=_good_profile())
    finally:
        app.state.run_pipeline = None  # reset
    assert resp.status_code == 200
    body = resp.json()
    assert body["matches"][0]["opportunity"]["title"] == "Solar Innovation Grant"
    assert body["matches"][0]["match"]["fit_score"] == 0.87
    assert body["matches"][0]["draft"]["status"] == "verified"


def test_match_needs_human_with_claims(client):
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
        resp = client.post("/api/match", json=_good_profile())
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 200
    claims = resp.json()["matches"][0]["draft"]["unresolved_claims"]
    assert claims[0]["claim"] == "Serves 10k"
    assert claims[0]["reason"] == "Not in profile"


def test_grants_gov_unreachable_flag(client):
    app.state.run_pipeline = lambda p: FullResult(
        pipeline=PipelineResult(profile_sparse=False, results=[]),
        grants_gov_ok=False,
        grants_gov_message="grants.gov is unreachable",
    )
    try:
        resp = client.post("/api/match", json=_good_profile())
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 200
    body = resp.json()
    assert body["grants_gov_ok"] is False
    assert body["grants_gov_message"] == "grants.gov is unreachable"
    assert body["matches"] == []


def test_sparse_profile_flag(client):
    app.state.run_pipeline = lambda p: _fake_full_result(sparse=True)
    try:
        resp = client.post(
            "/api/match",
            json={
                "org_basics": {"is_501c3": True, "annual_budget_usd": 100000, "org_age_years": 2},
                "project_type": "solar",
                "funding_preference": "either",
            },
        )
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 200
    assert resp.json()["profile_sparse"] is True


def test_invalid_body_friendly_400(client):
    resp = client.post("/api/match", json={"project_type": "solar"})  # missing required
    assert resp.status_code == 400
    assert "required fields" in resp.json()["error"].lower()


def test_config_error_is_sanitized(client):
    # Simulate the no-API-key path. The error message must not leak internals.
    def runner(profile):
        raise PipelineConfigError(
            "The matching service is not configured. An administrator must set the "
            "API credentials before running matches."
        )

    app.state.run_pipeline = runner
    try:
        resp = client.post("/api/match", json=_good_profile())
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 503
    text = resp.text
    assert "not configured" in text.lower()
    assert "ANTHROPIC_API_KEY" not in text
    assert "sk-ant" not in text
    assert "Traceback" not in text


def test_unexpected_error_is_sanitized(client):
    def runner(profile):
        raise RuntimeError("boom secret-internal-detail sk-ant-xyz")

    app.state.run_pipeline = runner
    try:
        resp = client.post("/api/match", json=_good_profile())
    finally:
        app.state.run_pipeline = None
    assert resp.status_code == 500
    text = resp.text
    assert "boom" not in text
    assert "sk-ant" not in text
    assert "Traceback" not in text
    assert "something went wrong" in text.lower()
