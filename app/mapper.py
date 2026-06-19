"""ICP -> grants.gov Search2 params mapper (PRD section 4, 9).

Stage 1 of the two-stage design: map the structured required profile fields to
grants.gov's coarse, code-based filters to pull a deliberately WIDE candidate set.
Deterministic, no LLM, reproducible. The narrow/smart fit scoring is Stage 2 (the
Match agent).

grants.gov Search2 coarse filters used here: keyword, oppStatuses, eligibilities,
fundingCategories, fundingInstruments, rows. The mapping is intentionally
high-recall: it errs toward pulling too many candidates rather than too few.
"""

from __future__ import annotations

from typing import Any, Dict

from app.models import FundingPreference, Profile, ProjectType

# Always-on: only posted and forecasted opportunities are worth surfacing.
DEFAULT_OPP_STATUSES = "posted|forecasted"
DEFAULT_ROWS = 50  # wide net

# grants.gov fundingCategories code: ENERGY covers energy/clean-energy programs.
FUNDING_CATEGORY_ENERGY = "ENERGY"

# Funding instruments: grants vs. (direct) loans, plus cooperative agreements
# which behave like grants for a nonprofit applicant.
INSTRUMENT_GRANT = "G"  # Grant
INSTRUMENT_COOP = "CA"  # Cooperative Agreement
INSTRUMENT_LOAN = "DL"  # Direct Loan

# Eligibility codes (grants.gov "eligibilities"):
#   12 = Nonprofits with 501(c)(3) status (other than IHEs)
#   25 = Others (e.g. nonprofits without 501(c)(3))
ELIGIBILITY_501C3 = "12"
ELIGIBILITY_NONPROFIT_OTHER = "25"

# Keyword seeds per project anchor — wide on purpose.
_KEYWORDS = {
    ProjectType.SOLAR: "solar",
    ProjectType.CLEAN_ENERGY: "clean energy",
}


def _instruments_for(pref: FundingPreference) -> str:
    if pref is FundingPreference.GRANT:
        return f"{INSTRUMENT_GRANT}|{INSTRUMENT_COOP}"
    if pref is FundingPreference.LOAN:
        return INSTRUMENT_LOAN
    # EITHER: cast the widest net.
    return f"{INSTRUMENT_GRANT}|{INSTRUMENT_COOP}|{INSTRUMENT_LOAN}"


def _eligibilities_for(profile: Profile) -> str:
    # 501(c)(3) orgs are eligible for both the 501(c)(3) bucket and the general
    # nonprofit bucket; non-501(c)(3) nonprofits map only to the general bucket.
    if profile.org_basics.is_501c3:
        return f"{ELIGIBILITY_501C3}|{ELIGIBILITY_NONPROFIT_OTHER}"
    return ELIGIBILITY_NONPROFIT_OTHER


def profile_to_search_params(profile: Profile) -> Dict[str, Any]:
    """Map the required core fields to a wide-net Search2 param dict.

    Only the *required* core (org basics + funding anchor) drives Stage 1; the
    optional context is reserved for the Match agent. Geography is deliberately
    NOT used as a hard grants.gov filter — federal programs are mostly national,
    and filtering by state here would drop eligible national opportunities. The
    Match agent reasons about geography in Stage 2 instead.
    """
    keyword = _KEYWORDS[profile.project_type]
    return {
        "keyword": keyword,
        "oppStatuses": DEFAULT_OPP_STATUSES,
        "eligibilities": _eligibilities_for(profile),
        "fundingCategories": FUNDING_CATEGORY_ENERGY,
        "fundingInstruments": _instruments_for(profile.funding_preference),
        "rows": DEFAULT_ROWS,
    }
