"""Verify agent (Opus 4.8) — the trust guarantee (PRD section 6, 7).

Checks every factual claim in a draft against the profile + the grant's stated
requirements and returns the *specific* unsupported claims (not a thumbs-down) so
the Drafter can revise against them. Runs on the strongest model because a cheap
model silently waves through hallucinations. Adaptive thinking is on.

Thin adapter over the domain-agnostic engine in `mcp_verify`: renders the
profile + opportunity as the SOURCE and the draft sections as the DRAFT.
"""

from __future__ import annotations

from app.agents.client import LLMClient
from app.agents.prompts import shared_prefix_text
from app.models import Draft, Opportunity, Profile, UnsupportedClaim, VerifyResult
from mcp_verify import core as verify_core

MODEL = "claude-opus-4-8"
# Adaptive thinking shares this budget with the answer; an undersized cap truncates
# the JSON. Opus reasons more than Sonnet here, so give it generous headroom.
MAX_TOKENS = 16000
THINKING = {"type": "adaptive"}


class VerifyAgent:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def verify(self, profile: Profile, opportunity: Opportunity, draft: Draft) -> VerifyResult:
        source = shared_prefix_text(profile, opportunity)
        draft_text = (
            f"ELIGIBILITY SUMMARY:\n{draft.eligibility_summary}\n\n"
            f"BOILERPLATE:\n{draft.boilerplate}"
        )
        report = verify_core.verify(
            self._client,
            source,
            draft_text,
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking=THINKING,
        )
        failures = [
            UnsupportedClaim(
                claim=f.claim,
                reason=f.reason,
                source_fact_checked=f.source_fact_checked,
                category=f.category,
                severity=f.severity,
            )
            for f in report.failures
        ]
        return VerifyResult(passed=report.passed, failures=failures)
