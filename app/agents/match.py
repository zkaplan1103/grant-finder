"""Match agent (Sonnet 4.6) — semantic fit scoring over the rich ICP.

Given the full profile and one candidate opportunity's details, score fit (0..1)
and explain why; flag low confidence when the profile is sparse (PRD section 6).
Adaptive thinking is on (reasoning-heavy agent, PRD section 8).
"""

from __future__ import annotations

from app.agents.client import LLMClient
from app.agents.parsing import AgentOutputError, extract_json_object
from app.agents.prompts import cached_system_blocks
from app.models import Match, Opportunity, Profile

MODEL = "claude-sonnet-4-6"
# Adaptive thinking shares this budget with the answer; an undersized cap truncates
# the JSON mid-object → AgentOutputError. 8192 wasn't enough once real thinking ran.
MAX_TOKENS = 16000
THINKING = {"type": "adaptive"}

SYSTEM_PROMPT = (
    "You are the Match agent for Grant Navigator. You score how well one "
    "funding opportunity fits a nonprofit applicant, for a caseworker who needs "
    "trustworthy, cited reasoning.\n\n"
    "Score true fit: geography, mission, project specifics, and the org's "
    "eligibility against the opportunity's stated requirements. Use only what the "
    "profile actually contains. If the profile is sparse (little geography, "
    "project, or mission detail), widen your view but set low_confidence true and "
    "add a caveat naming what to fill in for a better match (for example: "
    "'ranked on limited info; add geography for better fit'). Never invent facts "
    "about the org.\n\n"
    "Write in plain, professional prose. Use no emojis, no markdown, and no "
    "decorative symbols anywhere in your output.\n"
    "Reply with a single JSON object and nothing else:\n"
    '{"fit_score": <number 0..1>, "reasoning": "<why it fits or not>", '
    '"low_confidence": <true|false>, "caveats": ["<caveat>", ...]}'
)


class MatchAgent:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def score(self, profile: Profile, opportunity: Opportunity) -> Match:
        system = cached_system_blocks(SYSTEM_PROMPT, profile, opportunity)
        messages = [
            {
                "role": "user",
                "content": (
                    "Score the fit between the profile and the opportunity above. "
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
        # A single malformed/truncated response must not sink the whole run:
        # score this candidate 0 with a caveat and let ranking drop it.
        try:
            data = extract_json_object(resp.text, resp.stop_reason)
            return Match(
                opportunity_id=opportunity.id,
                fit_score=float(data["fit_score"]),
                reasoning=str(data["reasoning"]),
                low_confidence=bool(data.get("low_confidence", False)),
                caveats=list(data.get("caveats", []) or []),
            )
        except (AgentOutputError, KeyError, ValueError, TypeError):
            return Match(
                opportunity_id=opportunity.id,
                fit_score=0.0,
                reasoning="Could not score this opportunity (unreadable model response).",
                low_confidence=True,
                caveats=["scoring failed for this candidate; excluded from strong matches"],
            )
