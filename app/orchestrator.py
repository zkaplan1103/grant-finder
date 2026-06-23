"""Orchestrator — the bounded Drafter<->Verify loop and the full pipeline.

The loop (PRD section 7) is the part worth owning:

    draft = Drafter(match, profile)
    for i in range(MAX_REVISIONS):       # hard ceiling, non-negotiable
        failures = Verify(draft, profile, requirements)
        if not failures:
            return draft, status="verified"
        draft = Drafter.revise(draft, failures)   # specific failures fed back
    # loop exhausted -> escalate to human with the unresolved claims

Two LLMs revising each other can ping-pong forever, so MAX_REVISIONS is the cap.
Anything still unsupported after the cap is flagged to the human (escalation, not
silent failure).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from app.agents.drafter import DrafterAgent
from app.agents.match import MatchAgent
from app.agents.verify import VerifyAgent
from app.models import (
    Draft,
    DraftStatus,
    Match,
    Opportunity,
    Profile,
)

# Optional progress sink: stage name + completed/total counts. Used by the SSE
# endpoint to report real progress; None in tests and non-streaming callers.
ProgressFn = Callable[[str, int, int], None]

DEFAULT_MAX_REVISIONS = 3


def run_draft_verify_loop(
    profile: Profile,
    opportunity: Opportunity,
    match: Match,
    drafter: DrafterAgent,
    verifier: VerifyAgent,
    max_revisions: int = DEFAULT_MAX_REVISIONS,
) -> Draft:
    """Draft, then verify/revise up to `max_revisions` times.

    Returns a Draft whose status is VERIFIED (Verify found nothing) or
    NEEDS_HUMAN (still had unsupported claims at the cap, carried in
    `unresolved_claims`).
    """
    draft = drafter.draft(profile, opportunity, match)

    last_failures = []
    for _ in range(max_revisions):
        result = verifier.verify(profile, opportunity, draft)
        if result.passed:
            draft.status = DraftStatus.VERIFIED
            draft.unresolved_claims = []
            return draft
        last_failures = result.failures
        # Feed the specific failures back; produce the next revision.
        draft = drafter.revise(profile, opportunity, draft, last_failures)

    # Cap exhausted: do a final verification on the last revision so we report
    # the truly-unresolved claims, and escalate.
    final = verifier.verify(profile, opportunity, draft)
    if final.passed:
        draft.status = DraftStatus.VERIFIED
        draft.unresolved_claims = []
        return draft

    draft.status = DraftStatus.NEEDS_HUMAN
    draft.unresolved_claims = final.failures or last_failures
    return draft


# --------------------------------------------------------------------------- #
# Full pipeline (used by the web layer). Ranks candidates with Match, then runs
# the bounded loop on the strongest matches.
# --------------------------------------------------------------------------- #
@dataclass
class MatchedOpportunity:
    opportunity: Opportunity
    match: Match
    draft: Optional[Draft] = None


@dataclass
class PipelineResult:
    profile_sparse: bool
    results: List[MatchedOpportunity] = field(default_factory=list)


def run_pipeline(
    profile: Profile,
    opportunities: List[Opportunity],
    match_agent: MatchAgent,
    drafter: DrafterAgent,
    verifier: VerifyAgent,
    *,
    max_revisions: int = DEFAULT_MAX_REVISIONS,
    strong_fit_threshold: float = 0.6,
    draft_top_n: int = 5,
    min_display_score: float = 0.5,
    progress: Optional[ProgressFn] = None,
) -> PipelineResult:
    """Score & rank every opportunity, then draft+verify the strong ones.

    Only matches at or above `strong_fit_threshold` (capped at `draft_top_n`) get
    boilerplate — drafting every candidate would waste model calls on poor fits.

    `progress(stage, done, total)` is called as work completes so the SSE endpoint
    can report real progress. Optional — None means no reporting.
    """
    def report(stage: str, done: int, total: int) -> None:
        if progress is not None:
            progress(stage, done, total)

    scored: List[MatchedOpportunity] = []
    total = len(opportunities)
    for i, opp in enumerate(opportunities, 1):
        match = match_agent.score(profile, opp)
        scored.append(MatchedOpportunity(opportunity=opp, match=match))
        report("match", i, total)

    scored.sort(key=lambda m: m.match.fit_score, reverse=True)

    to_draft = [m for m in scored if m.match.fit_score >= strong_fit_threshold][:draft_top_n]
    drafted = 0
    for item in scored:
        if drafted >= draft_top_n:
            break
        if item.match.fit_score >= strong_fit_threshold:
            item.draft = run_draft_verify_loop(
                profile,
                item.opportunity,
                item.match,
                drafter,
                verifier,
                max_revisions=max_revisions,
            )
            drafted += 1
            report("draft", drafted, len(to_draft))

    # Hide weak fits from the result list (a 0.2 match is noise to a caseworker).
    # min_display_score=0 shows everything for users who want the full ranking.
    visible = [m for m in scored if m.match.fit_score >= min_display_score]
    return PipelineResult(profile_sparse=profile.is_sparse(), results=visible)
