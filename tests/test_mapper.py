"""Phase 4 done-condition: example profiles -> expected param dicts, including
always-on oppStatuses=posted|forecasted and the org-basics eligibility mapping.
"""

from app.mapper import (
    DEFAULT_OPP_STATUSES,
    DEFAULT_ROWS,
    ELIGIBILITY_501C3,
    ELIGIBILITY_NONPROFIT_OTHER,
    FUNDING_CATEGORY_ENERGY,
    profile_to_search_params,
)
from app.models import FundingPreference, OrgBasics, Profile, ProjectType


def _profile(is_501c3=True, project=ProjectType.SOLAR, pref=FundingPreference.GRANT) -> Profile:
    return Profile(
        org_basics=OrgBasics(is_501c3=is_501c3, annual_budget_usd=200_000, org_age_years=5),
        project_type=project,
        funding_preference=pref,
    )


def test_always_on_statuses_and_category_and_rows():
    p = profile_to_search_params(_profile())
    assert p["oppStatuses"] == DEFAULT_OPP_STATUSES == "posted|forecasted"
    assert p["fundingCategories"] == FUNDING_CATEGORY_ENERGY == "ENERGY"
    assert p["rows"] == DEFAULT_ROWS


def test_501c3_eligibility_mapping():
    p = profile_to_search_params(_profile(is_501c3=True))
    assert p["eligibilities"] == f"{ELIGIBILITY_501C3}|{ELIGIBILITY_NONPROFIT_OTHER}"


def test_non_501c3_eligibility_mapping():
    p = profile_to_search_params(_profile(is_501c3=False))
    assert p["eligibilities"] == ELIGIBILITY_NONPROFIT_OTHER


def test_keyword_per_project_anchor():
    assert profile_to_search_params(_profile(project=ProjectType.SOLAR))["keyword"] == "solar"
    assert (
        profile_to_search_params(_profile(project=ProjectType.CLEAN_ENERGY))["keyword"]
        == "clean energy"
    )


def test_funding_instruments_grant():
    p = profile_to_search_params(_profile(pref=FundingPreference.GRANT))
    assert p["fundingInstruments"] == "G|CA"


def test_funding_instruments_loan():
    p = profile_to_search_params(_profile(pref=FundingPreference.LOAN))
    assert p["fundingInstruments"] == "DL"


def test_funding_instruments_either_widest():
    p = profile_to_search_params(_profile(pref=FundingPreference.EITHER))
    assert p["fundingInstruments"] == "G|CA|DL"


def test_full_param_dict_for_canonical_profile():
    p = profile_to_search_params(_profile())
    assert p == {
        "keyword": "solar",
        "oppStatuses": "posted|forecasted",
        "eligibilities": "12|25",
        "fundingCategories": "ENERGY",
        "fundingInstruments": "G|CA",
        "rows": 50,
    }


def test_geography_not_used_as_hard_filter():
    # Geography stays out of Stage 1 (reserved for the Match agent). Use a state
    # whose USPS code can't collide with a grants.gov instrument code like "CA"
    # (Cooperative Agreement), and assert no param *value* carries the state.
    p = Profile(
        org_basics=OrgBasics(is_501c3=True, annual_budget_usd=1, org_age_years=1),
        project_type=ProjectType.SOLAR,
        funding_preference=FundingPreference.GRANT,
        geography={"state": "TX"},
    )
    params = profile_to_search_params(p)
    assert "TX" not in "".join(str(v) for v in params.values())
