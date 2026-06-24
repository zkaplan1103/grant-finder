"""Tests for the abuse/cost guard — rate limits + daily spend kill-switch."""

from fastapi.testclient import TestClient

from app.web import guard as guard_mod
from app.web.app import app
from app.web.guard import GuardState


def _good_profile():
    return {
        "org_basics": {"is_501c3": True, "annual_budget_usd": 500000, "org_age_years": 8},
        "project_type": "solar",
        "funding_preference": "grant",
    }


# --------------------------- unit: GuardState ------------------------------ #
def test_per_ip_limit_blocks_after_cap(monkeypatch):
    monkeypatch.setattr(guard_mod, "PER_IP_PER_MIN", 2)
    monkeypatch.setattr(guard_mod, "GLOBAL_PER_MIN", 100)
    monkeypatch.setattr(guard_mod, "DAILY_SEARCH_CAP", 100)
    g = GuardState()
    assert g.check_and_consume("1.1.1.1").ok
    assert g.check_and_consume("1.1.1.1").ok
    assert not g.check_and_consume("1.1.1.1").ok  # 3rd from same IP blocked
    # A different IP is unaffected.
    assert g.check_and_consume("2.2.2.2").ok


def test_global_limit_blocks_across_ips(monkeypatch):
    monkeypatch.setattr(guard_mod, "PER_IP_PER_MIN", 100)
    monkeypatch.setattr(guard_mod, "GLOBAL_PER_MIN", 2)
    monkeypatch.setattr(guard_mod, "DAILY_SEARCH_CAP", 100)
    g = GuardState()
    assert g.check_and_consume("a").ok
    assert g.check_and_consume("b").ok
    assert not g.check_and_consume("c").ok  # global cap hit regardless of IP


def test_daily_cap_is_the_hard_ceiling(monkeypatch):
    # Even with generous per-minute limits, the daily cap stops spend.
    monkeypatch.setattr(guard_mod, "PER_IP_PER_MIN", 100)
    monkeypatch.setattr(guard_mod, "GLOBAL_PER_MIN", 100)
    monkeypatch.setattr(guard_mod, "DAILY_SEARCH_CAP", 3)
    g = GuardState()
    for _ in range(3):
        assert g.check_and_consume("x").ok
    blocked = g.check_and_consume("x")
    assert not blocked.ok
    assert "daily" in blocked.reason.lower()


# --------------------------- endpoint: 429 --------------------------------- #
def test_endpoint_returns_429_when_blocked(monkeypatch):
    monkeypatch.setattr(guard_mod, "PER_IP_PER_MIN", 1)
    app.state.guard = GuardState()
    app.state.run_pipeline = lambda p: (_ for _ in ()).throw(AssertionError("should not run when blocked"))
    client = TestClient(app)
    try:
        r1 = client.post("/api/match", json=_good_profile())
        assert r1.status_code != 429  # first allowed (pipeline raises, but that's past the guard)
        r2 = client.post("/api/match", json=_good_profile())
        assert r2.status_code == 429
        assert "error" in r2.json()
    finally:
        app.state.run_pipeline = None
        app.state.guard = GuardState()


def test_oversized_body_rejected():
    app.state.guard = GuardState()
    client = TestClient(app)
    # A body over the 64KB cap -> friendly 400, not a crash, and no pipeline run.
    huge = {"org_basics": {"is_501c3": True, "annual_budget_usd": 1, "org_age_years": 1},
            "project_type": "x" * 70_000, "funding_preference": "grant"}
    r = client.post("/api/match", json=huge)
    assert r.status_code == 400
