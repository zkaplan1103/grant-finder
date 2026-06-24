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

import threading
from concurrent.futures import ThreadPoolExecutor
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

# Match scoring and the per-opportunity draft/verify loops are independent across
# opportunities, so we run them concurrently. The anthropic SDK client is
# thread-safe (httpx connection pool), so one client is shared across threads.
# ponytail: bounded pool, not unbounded threads — caps in-flight calls so a
# 40-opportunity search doesn't fire 40 simultaneous requests and trip rate limits.
_MAX_CONCURRENCY = 8


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
    # Thread-safe progress: a lock guards the per-stage completed counter so
    # concurrent workers report monotonic done/total counts to the SSE endpoint.
    _lock = threading.Lock()
    _done = {"n": 0}

    def report_one(stage: str, total: int) -> None:
        if progress is None:
            return
        with _lock:
            _done["n"] += 1
            n = _done["n"]
        progress(stage, n, total)

    total = len(opportunities)

    # Stage 1: score every opportunity concurrently (independent Match calls).
    def _score(opp: Opportunity) -> MatchedOpportunity:
        match = match_agent.score(profile, opp)
        report_one("match", total)
        return MatchedOpportunity(opportunity=opp, match=match)

    with ThreadPoolExecutor(max_workers=_MAX_CONCURRENCY) as pool:
        # executor.map preserves input order; sort below makes order irrelevant anyway.
        scored: List[MatchedOpportunity] = list(pool.map(_score, opportunities))

    scored.sort(key=lambda m: m.match.fit_score, reverse=True)

    to_draft = [m for m in scored if m.match.fit_score >= strong_fit_threshold][:draft_top_n]

    # Stage 2: draft+verify the selected candidates concurrently (each loop is
    # independent — a different opportunity's draft doesn't depend on this one).
    _done["n"] = 0  # reset counter for the draft stage

    def _draft(item: MatchedOpportunity) -> None:
        item.draft = run_draft_verify_loop(
            profile,
            item.opportunity,
            item.match,
            drafter,
            verifier,
            max_revisions=max_revisions,
        )
        report_one("draft", len(to_draft))

    if to_draft:
        with ThreadPoolExecutor(max_workers=_MAX_CONCURRENCY) as pool:
            list(pool.map(_draft, to_draft))

    # Hide weak fits from the result list (a 0.2 match is noise to a caseworker).
    # min_display_score=0 shows everything for users who want the full ranking.
    visible = [m for m in scored if m.match.fit_score >= min_display_score]
    return PipelineResult(profile_sparse=profile.is_sparse(), results=visible)
