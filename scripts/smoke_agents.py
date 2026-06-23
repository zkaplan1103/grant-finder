"""Real-API smoke test for the truncation fix. Runs Match -> Drafter -> Verify
against the live Anthropic API (the exact chain that raised AgentOutputError).

Usage:  ANTHROPIC_API_KEY=sk-... python scripts/smoke_agents.py
Costs a few cents. Not part of the test suite.
"""

from app.agents import DrafterAgent, MatchAgent, VerifyAgent
from app.agents.client import build_default_client
from app.models import (
    FundingPreference,
    Opportunity,
    OpportunitySource,
    OrgBasics,
    Profile,
)

client = build_default_client()
if client is None:
    raise SystemExit("ANTHROPIC_API_KEY not set — cannot run the live smoke test.")

profile = Profile(
    org_basics=OrgBasics(is_501c3=True, annual_budget_usd=500_000, org_age_years=8),
    project_type="solar",
    funding_preference=FundingPreference.GRANT,
    geography={"state": "CA", "disadvantaged_community": True},
    project={"project_type": "community solar", "amount_needed_usd": 250_000},
    mission={
        "mission_statement": "Bring solar to low-income households.",
        "populations_served": ["low-income", "rural"],
    },
)
opp = Opportunity(
    id="OPP-1", source=OpportunitySource.GRANTS_GOV,
    title="Solar Energy Innovation Grant", agency="DOE", status="posted",
    aln="81.087",
    eligibility_notes="Open to 501(c)(3) nonprofits serving disadvantaged communities.",
    description="Funds community solar in low-income areas.",
)

print("Match...")
match = MatchAgent(client).score(profile, opp)
print(f"  fit_score={match.fit_score} low_confidence={match.low_confidence}")
assert match.fit_score > 0, "Match scored 0 — truncation/parse still failing"

print("Draft...")
draft = DrafterAgent(client).draft(profile, opp, match)
print(f"  eligibility={len(draft.eligibility_summary)} chars, "
      f"boilerplate={len(draft.boilerplate)} chars")
assert draft.boilerplate, "Drafter returned empty boilerplate"

print("Verify...")
result = VerifyAgent(client).verify(profile, opp, draft)
print(f"  passed={result.passed} failures={len(result.failures)}")

print("\nOK — full Match->Draft->Verify chain ran without AgentOutputError.")
