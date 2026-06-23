"""Pydantic data models — the contract shared across every layer (PRD section 5).

The Profile models the required/optional split from the PRD: required core fields
drive the deterministic Stage-1 grants.gov search; optional context enriches the
Stage-2 Match scoring and may be blank (graceful degradation).
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enumerations for the small, fixed-vocabulary required fields.
# --------------------------------------------------------------------------- #
class FundingPreference(str, Enum):
    GRANT = "grant"
    LOAN = "loan"
    EITHER = "either"


# --------------------------------------------------------------------------- #
# Profile (the ICP).
# --------------------------------------------------------------------------- #
class OrgBasics(BaseModel):
    """Required eligibility-gate fields — these drive the Stage-1 search."""

    is_501c3: bool = Field(..., description="Whether the org holds 501(c)(3) status.")
    annual_budget_usd: int = Field(..., ge=0, description="Annual operating budget in USD.")
    org_age_years: int = Field(..., ge=0, description="Years since the org was founded.")


class Geography(BaseModel):
    """Optional — enriches Stage-2 Match scoring. Blank is acceptable."""

    state: Optional[str] = Field(None, description="Two-letter US state code, e.g. 'CA'.")
    service_area: Optional[str] = Field(None, description="Free-text service area description.")
    disadvantaged_community: Optional[bool] = Field(
        None, description="Whether the org serves a designated disadvantaged community."
    )


class ProjectSpecifics(BaseModel):
    """Optional — enriches Stage-2 Match scoring. Blank is acceptable."""

    project_type: Optional[str] = Field(
        None, description="A more specific sub-type, e.g. 'rooftop solar', 'after-school program'."
    )
    size_kw: Optional[float] = Field(None, ge=0, description="System size in kW.")
    estimated_cost_usd: Optional[int] = Field(None, ge=0, description="Estimated project cost.")
    stage: Optional[str] = Field(None, description="e.g. 'planning', 'shovel-ready'.")
    amount_needed_usd: Optional[int] = Field(None, ge=0, description="Funding amount needed.")


class MissionPopulations(BaseModel):
    """Optional — enriches Stage-2 Match scoring. Blank is acceptable."""

    mission_statement: Optional[str] = Field(None, description="The org's mission statement.")
    populations_served: List[str] = Field(
        default_factory=list,
        description="e.g. ['low-income', 'tribal', 'rural'].",
    )


class Profile(BaseModel):
    """A nonprofit profile. Required core + optional context (PRD section 5).

    A sparse profile (only `org_basics` and `funding_anchor`) is valid: the Match
    agent uses whatever is present and flags lower confidence when context is thin.
    """

    # Required core — drives the Stage-1 search.
    org_basics: OrgBasics
    project_type: str = Field(
        ..., min_length=1,
        description="Funding focus, used verbatim as the grants.gov keyword. "
        "e.g. 'solar', 'youth literacy', 'food security'.",
    )
    funding_preference: FundingPreference

    # Optional context — enriches Stage-2 scoring.
    geography: Geography = Field(default_factory=Geography)
    project: ProjectSpecifics = Field(default_factory=ProjectSpecifics)
    mission: MissionPopulations = Field(default_factory=MissionPopulations)

    def is_sparse(self) -> bool:
        """True when no optional context is filled in — Match should say so."""
        geo_empty = not any(
            [
                self.geography.state,
                self.geography.service_area,
                self.geography.disadvantaged_community is not None,
            ]
        )
        proj_empty = not any(
            [
                self.project.project_type,
                self.project.size_kw is not None,
                self.project.estimated_cost_usd is not None,
                self.project.stage,
                self.project.amount_needed_usd is not None,
            ]
        )
        mission_empty = not (self.mission.mission_statement or self.mission.populations_served)
        return geo_empty and proj_empty and mission_empty


# --------------------------------------------------------------------------- #
# Opportunity — a candidate funding source (grants.gov hit or curated entry).
# The agents reason over both kinds identically (PRD section 9).
# --------------------------------------------------------------------------- #
class OpportunitySource(str, Enum):
    GRANTS_GOV = "grants_gov"
    CURATED = "curated"


class Opportunity(BaseModel):
    id: str = Field(..., description="Stable id (grants.gov oppId, or curated slug).")
    source: OpportunitySource
    title: str
    agency: Optional[str] = None
    url: Optional[str] = None

    # Thin Search2 fields / curated metadata.
    status: Optional[str] = None
    close_date: Optional[str] = None
    aln: Optional[str] = Field(None, description="Assistance Listing Number (CFDA).")
    typical_award: Optional[str] = Field(None, description="Curated typical award size.")

    # Rich detail (filled from the Get Full Opportunity Details call, or curated notes).
    eligibility_notes: Optional[str] = None
    description: Optional[str] = None


# --------------------------------------------------------------------------- #
# Match — the Match agent's scored, reasoned fit for one opportunity.
# --------------------------------------------------------------------------- #
class Match(BaseModel):
    opportunity_id: str
    fit_score: float = Field(..., ge=0.0, le=1.0, description="0..1 fit confidence.")
    reasoning: str = Field(..., description="Why this opportunity fits (or does not).")
    low_confidence: bool = Field(
        False, description="True when the profile was too sparse for a confident score."
    )
    caveats: List[str] = Field(
        default_factory=list,
        description="e.g. ['ranked on limited info; add geography for better fit'].",
    )


# --------------------------------------------------------------------------- #
# Draft — the Drafter's boilerplate for a strong match.
# --------------------------------------------------------------------------- #
class DraftStatus(str, Enum):
    DRAFT = "draft"  # produced, not yet verified
    VERIFIED = "verified"  # passed the Verify loop
    NEEDS_HUMAN = "needs_human"  # escalated with unresolved claims


class Draft(BaseModel):
    opportunity_id: str
    eligibility_summary: str
    boilerplate: str = Field(..., description="Org description, need statement, etc.")
    status: DraftStatus = DraftStatus.DRAFT
    revision: int = Field(0, ge=0, description="How many revise passes produced this draft.")
    unresolved_claims: List["UnsupportedClaim"] = Field(
        default_factory=list,
        description="Populated when status == needs_human.",
    )


# --------------------------------------------------------------------------- #
# VerifyResult — the Verify agent's claim check (PRD section 6, 7).
# --------------------------------------------------------------------------- #
class UnsupportedClaim(BaseModel):
    claim: str = Field(..., description="The specific claim text that is unsupported.")
    reason: str = Field(..., description="Why it is unsupported by profile or requirements.")


class VerifyResult(BaseModel):
    passed: bool = Field(..., description="True when no unsupported claims were found.")
    failures: List[UnsupportedClaim] = Field(
        default_factory=list,
        description="Specific failures fed back to the Drafter (PRD section 7).",
    )


Draft.model_rebuild()
