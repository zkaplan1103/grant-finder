"""Parse the profile form's flat fields into a validated Profile.

Required fields raise pydantic ValidationError (turned into a 400 by the route);
optional fields are coerced and left blank when empty.
"""

from __future__ import annotations

from typing import List, Mapping, Optional

from app.models import (
    FundingPreference,
    Geography,
    MissionPopulations,
    OrgBasics,
    ProjectSpecifics,
    Profile,
    ProjectType,
)


def _opt_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    return v or None


def _opt_int(v: Optional[str]) -> Optional[int]:
    v = _opt_str(v)
    return int(v) if v is not None else None


def _opt_float(v: Optional[str]) -> Optional[float]:
    v = _opt_str(v)
    return float(v) if v is not None else None


def _opt_bool(v: Optional[str]) -> Optional[bool]:
    v = _opt_str(v)
    if v is None:
        return None
    return v.lower() in ("true", "1", "yes", "on")


def _populations(v: Optional[str]) -> List[str]:
    v = _opt_str(v)
    if not v:
        return []
    return [p.strip() for p in v.split(",") if p.strip()]


def parse_profile_form(form: Mapping[str, str]) -> Profile:
    return Profile(
        org_basics=OrgBasics(
            is_501c3=_opt_bool(form.get("is_501c3")) or False,
            annual_budget_usd=int(form["annual_budget_usd"]),
            org_age_years=int(form["org_age_years"]),
        ),
        project_type=ProjectType(form["project_type"]),
        funding_preference=FundingPreference(form["funding_preference"]),
        geography=Geography(
            state=_opt_str(form.get("state")),
            service_area=_opt_str(form.get("service_area")),
            disadvantaged_community=_opt_bool(form.get("disadvantaged_community")),
        ),
        project=ProjectSpecifics(
            project_type=_opt_str(form.get("project_specific_type")),
            size_kw=_opt_float(form.get("size_kw")),
            estimated_cost_usd=_opt_int(form.get("estimated_cost_usd")),
            stage=_opt_str(form.get("stage")),
            amount_needed_usd=_opt_int(form.get("amount_needed_usd")),
        ),
        mission=MissionPopulations(
            mission_statement=_opt_str(form.get("mission_statement")),
            populations_served=_populations(form.get("populations_served")),
        ),
    )
