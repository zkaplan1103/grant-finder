"""Drafter agent (Sonnet 4.6) — application boilerplate for a strong match.

Two entry points (PRD section 7):
  - draft():  produce the eligibility summary + boilerplate for a match.
  - revise(): given specific Verify failures, revise the draft against them.

No adaptive thinking here (it is volume drafting work, not the reasoning-heavy
Match/Verify steps; PRD section 8 puts adaptive thinking only on Match + Verify).
"""

from __future__ import annotations

from typing import List

from app.agents.client import LLMClient
from app.agents.parsing import extract_json_object
from app.agents.prompts import cached_system_blocks
from app.models import Draft, DraftStatus, Match, Opportunity, Profile, UnsupportedClaim

MODEL = "claude-sonnet-4-6"
# Two prose fields (eligibility summary + boilerplate) wrapped in JSON. 3072 is
# too tight — a long boilerplate truncates the JSON mid-string (AgentOutputError).
MAX_TOKENS = 8192

SYSTEM_PROMPT = (
    "You are the Drafter agent for Grant Navigator. You write application "
    "boilerplate for a nonprofit applying to a funding opportunity: an "
    "eligibility summary and reusable boilerplate (org description, need "
    "statement).\n\n"
    "Ground every factual statement in the profile and the opportunity's stated "
    "requirements above. Do not invent eligibility facts, award amounts, "
    "geographies, or populations the profile does not state — a fabricated "
    "eligibility claim can get an org barred. When the profile lacks something an "
    "application would need, write it as a placeholder the caseworker must fill, "
    "not as a fact.\n\n"
    "Write in plain, professional prose suitable for a grant application. Use no "
    "emojis, no markdown, and no decorative symbols anywhere in your output.\n"
    "Reply with a single JSON object and nothing else:\n"
    '{"eligibility_summary": "<text>", "boilerplate": "<text>"}'
)


def _failures_block(failures: List[UnsupportedClaim]) -> str:
    lines = ["The Verify agent flagged these specific unsupported claims. Fix each:"]
    for i, f in enumerate(failures, 1):
        lines.append(f"{i}. Claim: {f.claim}\n   Why it failed: {f.reason}")
    lines.append(
        "Revise the draft to remove or correct each flagged claim, keeping every "
        "remaining statement grounded in the profile and requirements. Return the "
        "JSON object only."
    )
    return "\n".join(lines)


class DrafterAgent:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def draft(self, profile: Profile, opportunity: Opportunity, match: Match) -> Draft:
        system = cached_system_blocks(SYSTEM_PROMPT, profile, opportunity)
        messages = [
            {
                "role": "user",
                "content": (
                    "Write the eligibility summary and boilerplate for this "
                    f"application. The Match agent's fit reasoning was: "
                    f"{match.reasoning}\nReturn the JSON object only."
                ),
            }
        ]
        resp = self._client.complete(
            model=MODEL, system=system, messages=messages, max_tokens=MAX_TOKENS
        )
        data = extract_json_object(resp.text, resp.stop_reason)
        return Draft(
            opportunity_id=opportunity.id,
            eligibility_summary=str(data["eligibility_summary"]),
            boilerplate=str(data["boilerplate"]),
            status=DraftStatus.DRAFT,
            revision=0,
        )

    def revise(
        self,
        profile: Profile,
        opportunity: Opportunity,
        draft: Draft,
        failures: List[UnsupportedClaim],
    ) -> Draft:
        system = cached_system_blocks(SYSTEM_PROMPT, profile, opportunity)
        messages = [
            {
                "role": "user",
                "content": (
                    "Here is the current draft to revise.\n\n"
                    f"ELIGIBILITY SUMMARY:\n{draft.eligibility_summary}\n\n"
                    f"BOILERPLATE:\n{draft.boilerplate}\n\n"
                    + _failures_block(failures)
                ),
            }
        ]
        resp = self._client.complete(
            model=MODEL, system=system, messages=messages, max_tokens=MAX_TOKENS
        )
        data = extract_json_object(resp.text, resp.stop_reason)
        return Draft(
            opportunity_id=opportunity.id,
            eligibility_summary=str(data["eligibility_summary"]),
            boilerplate=str(data["boilerplate"]),
            status=DraftStatus.DRAFT,
            revision=draft.revision + 1,
        )
