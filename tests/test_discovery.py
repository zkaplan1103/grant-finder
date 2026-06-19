"""Phase 5 done-condition:
  - grants.gov client tested with MOCKED HTTP (respx) for success, timeout, and
    unreachable -> graceful degradation. No live grants.gov calls.
  - curated loader tested against a fixture YAML.
"""

import os

import httpx
import pytest
import respx

from app.discovery import (
    CURATED_SOURCES_PATH,
    GrantsGovClient,
    GrantsGovTimeout,
    GrantsGovUnreachable,
    load_curated_sources,
)
from app.discovery.grants_gov import BASE_URL, FETCH_PATH, SEARCH2_PATH
from app.models import OpportunitySource

SEARCH_URL = f"{BASE_URL}{SEARCH2_PATH}"
FETCH_URL = f"{BASE_URL}{FETCH_PATH}"

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "curated_fixture.yaml")


# --------------------------- grants.gov: success --------------------------- #
@respx.mock
def test_search_success_normalizes_hits():
    respx.post(SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "oppHits": [
                        {
                            "id": "350000",
                            "title": "Solar Innovation",
                            "agencyName": "DOE",
                            "oppStatus": "posted",
                            "closeDate": "12/31/2026",
                            "alnist": "81.087",
                        }
                    ]
                }
            },
        )
    )
    with GrantsGovClient(client=httpx.Client()) as gg:
        opps = gg.search({"keyword": "solar"})

    assert len(opps) == 1
    o = opps[0]
    assert o.id == "350000"
    assert o.source == OpportunitySource.GRANTS_GOV
    assert o.title == "Solar Innovation"
    assert o.agency == "DOE"
    assert o.aln == "81.087"
    assert o.url and "350000" in o.url


@respx.mock
def test_search_empty_results_is_fine():
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(200, json={"data": {"oppHits": []}}))
    with GrantsGovClient(client=httpx.Client()) as gg:
        assert gg.search({"keyword": "solar"}) == []


@respx.mock
def test_fetch_details_enriches():
    respx.post(FETCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "opportunityTitle": "Solar Innovation",
                    "agencyName": "DOE",
                    "opportunityStatus": "posted",
                    "synopsis": {
                        "responseDate": "12/31/2026",
                        "applicantEligibilityDesc": "501(c)(3) nonprofits.",
                        "synopsisDesc": "Funds community solar.",
                    },
                }
            },
        )
    )
    with GrantsGovClient(client=httpx.Client()) as gg:
        o = gg.fetch_details("350000")
    assert o is not None
    assert o.eligibility_notes == "501(c)(3) nonprofits."
    assert o.description == "Funds community solar."


# --------------------------- grants.gov: failures -------------------------- #
@respx.mock
def test_search_timeout_raises_typed_sanitized():
    respx.post(SEARCH_URL).mock(side_effect=httpx.TimeoutException("boom"))
    with GrantsGovClient(client=httpx.Client()) as gg:
        with pytest.raises(GrantsGovTimeout) as exc:
            gg.search({"keyword": "solar"})
    # Sanitized: the underlying message ("boom") is never surfaced.
    assert "boom" not in str(exc.value)
    assert "timed out" in str(exc.value)


@respx.mock
def test_search_connect_error_unreachable():
    respx.post(SEARCH_URL).mock(side_effect=httpx.ConnectError("no route"))
    with GrantsGovClient(client=httpx.Client()) as gg:
        with pytest.raises(GrantsGovUnreachable) as exc:
            gg.search({"keyword": "solar"})
    assert "no route" not in str(exc.value)
    assert "unreachable" in str(exc.value)


@respx.mock
def test_search_500_unreachable():
    respx.post(SEARCH_URL).mock(return_value=httpx.Response(500, text="server error"))
    with GrantsGovClient(client=httpx.Client()) as gg:
        with pytest.raises(GrantsGovUnreachable):
            gg.search({"keyword": "solar"})


@respx.mock
def test_fetch_details_fails_softly_to_none():
    respx.post(FETCH_URL).mock(side_effect=httpx.ConnectError("down"))
    with GrantsGovClient(client=httpx.Client()) as gg:
        assert gg.fetch_details("350000") is None


# --------------------------- curated loader -------------------------------- #
def test_curated_loader_against_fixture():
    sources = load_curated_sources(FIXTURE)
    assert len(sources) == 2
    assert all(s.source == OpportunitySource.CURATED for s in sources)
    by_id = {s.id: s for s in sources}
    assert by_id["fixture-one"].typical_award == "$10,000"
    assert by_id["fixture-one"].agency == "Test Foundation"  # 'funder' maps to agency
    assert by_id["fixture-two"].agency == "Test State Energy Office"


def test_real_sources_yaml_loads_and_is_sized():
    sources = load_curated_sources(CURATED_SOURCES_PATH)
    # PRD: ~10-15 vetted sources.
    assert 10 <= len(sources) <= 15
    assert all(s.id and s.title for s in sources)
    assert all(s.source == OpportunitySource.CURATED for s in sources)
