"""Verify agent (Opus 4.8) — the trust guarantee (PRD section 6, 7).

Checks every factual claim in a draft against the profile + the grant's stated
requirements and returns the *specific* unsupported claims (not a thumbs-down) so
the Drafter can revise against them. Runs on the strongest model because a cheap
model silently waves through hallucinations. Adaptive thinking is on.
"""

from __future__ import annotations

from app.agents.client import LLMClient
from app.agents.parsing import extract_json_object
from app.agents.prompts import cached_system_blocks
from app.models import Draft, Opportunity, Profile, UnsupportedClaim, VerifyResult

MODEL = "claude-opus-4-8"
# Adaptive thinking shares this budget with the answer; an undersized cap truncates
# the JSON. Opus reasons more than Sonnet here, so give it generous headroom.
MAX_TOKENS = 16000
THINKING = {"type": "adaptive"}

SYSTEM_PROMPT = (
    "You are the Verify agent for Grant Navigator — the trust guarantee. "
    "You check a drafted application for any factual claim that is NOT supported "
    "by the nonprofit profile or the funding opportunity's stated requirements "
    "above.\n\n"
    "Flag a claim when it asserts something the profile/requirements do not state, "
    "or that contradicts them (wrong geography, invented award amount, invented "
    "population served, eligibility the org does not actually meet). Do not flag "
    "clearly-marked placeholders the caseworker must fill in. Be specific: return "
    "the exact claim text and why it is unsupported, so the Drafter can fix it. "
    "Err toward catching unsupported eligibility claims — a fabricated one can get "
    "an org barred.\n\n"
    "Write in plain, professional prose. Use no emojis, no markdown, and no "
    "decorative symbols anywhere in your output.\n"
    "Reply with a single JSON object and nothing else:\n"
    '{"passed": <true|false>, "failures": [{"claim": "<text>", "reason": "<why>"}, ...]}'
    "\nIf nothing is unsupported, return passed true with an empty failures list."
)


class VerifyAgent:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def verify(self, profile: Profile, opportunity: Opportunity, draft: Draft) -> VerifyResult:
        system = cached_system_blocks(SYSTEM_PROMPT, profile, opportunity)
        messages = [
            {
                "role": "user",
                "content": (
                    "Check this draft for unsupported claims.\n\n"
                    f"ELIGIBILITY SUMMARY:\n{draft.eligibility_summary}\n\n"
                    f"BOILERPLATE:\n{draft.boilerplate}\n\n"
                    "Return the JSON object only."
                ),
            }
        ]
        resp = self._client.complete(
            model=MODEL,
            system=system,
            messages=messages,
            max_tokens=MAX_TOKENS,
            thinking=THINKING,
        )
        data = extract_json_object(resp.text, resp.stop_reason)
        failures = [
            UnsupportedClaim(claim=str(f["claim"]), reason=str(f["reason"]))
            for f in (data.get("failures") or [])
        ]
        # Trust the failures list as the source of truth for pass/fail.
        passed = bool(data.get("passed", not failures)) and not failures
        return VerifyResult(passed=passed, failures=failures)
