"""Phase 3 done-condition: the bounded loop, tested with FAKE Drafter/Verify
(no LLM):
  - verifies first try -> returns verified;
  - fails then passes  -> returns verified after N < cap revisions;
  - never passes        -> returns needs_human with unresolved claims at the cap.
"""

from typing import List

from app.models import (
    Draft,
    DraftStatus,
    Match,
    Opportunity,
    OpportunitySource,
    UnsupportedClaim,
    VerifyResult,
)
from app.orchestrator import run_draft_verify_loop, run_pipeline


# --------------------------- fakes (no LLM) -------------------------------- #
class FakeDrafter:
    def __init__(self):
        self.draft_calls = 0
        self.revise_calls = 0
        self.revise_failures_seen: List[List[UnsupportedClaim]] = []

    def draft(self, profile, opportunity, match) -> Draft:
        self.draft_calls += 1
        return Draft(
            opportunity_id=opportunity.id,
            eligibility_summary="summary v0",
            boilerplate="boilerplate v0",
            status=DraftStatus.DRAFT,
            revision=0,
        )

    def revise(self, profile, opportunity, draft, failures) -> Draft:
        self.revise_calls += 1
        self.revise_failures_seen.append(failures)
        return Draft(
            opportunity_id=opportunity.id,
            eligibility_summary=f"summary v{draft.revision + 1}",
            boilerplate=f"boilerplate v{draft.revision + 1}",
            status=DraftStatus.DRAFT,
            revision=draft.revision + 1,
        )


class ScriptedVerifier:
    """Returns scripted VerifyResults in order; repeats the last entry."""

    def __init__(self, results: List[VerifyResult]):
        self._results = results
        self._i = 0
        self.calls = 0

    def verify(self, profile, opportunity, draft) -> VerifyResult:
        self.calls += 1
        r = self._results[min(self._i, len(self._results) - 1)]
        self._i += 1
        return r


def _opp() -> Opportunity:
    return Opportunity(id="OPP-1", source=OpportunitySource.GRANTS_GOV, title="T")


def _match() -> Match:
    return Match(opportunity_id="OPP-1", fit_score=0.9, reasoning="fit")


_FAIL = VerifyResult(
    passed=False, failures=[UnsupportedClaim(claim="bad claim", reason="not in profile")]
)
_PASS = VerifyResult(passed=True, failures=[])


def test_verifies_first_try(full_profile):
    drafter = FakeDrafter()
    verifier = ScriptedVerifier([_PASS])
    draft = run_draft_verify_loop(full_profile, _opp(), _match(), drafter, verifier, max_revisions=3)

    assert draft.status == DraftStatus.VERIFIED
    assert draft.revision == 0
    assert drafter.revise_calls == 0
    assert verifier.calls == 1
    assert draft.unresolved_claims == []


def test_fails_then_passes_before_cap(full_profile):
    drafter = FakeDrafter()
    verifier = ScriptedVerifier([_FAIL, _PASS])  # fail once, then pass
    draft = run_draft_verify_loop(full_profile, _opp(), _match(), drafter, verifier, max_revisions=3)

    assert draft.status == DraftStatus.VERIFIED
    assert draft.revision == 1  # one revise happened
    assert drafter.revise_calls == 1
    # The specific failure was fed back into the revise call.
    assert drafter.revise_failures_seen[0][0].claim == "bad claim"


def test_never_passes_escalates_with_unresolved(full_profile):
    drafter = FakeDrafter()
    verifier = ScriptedVerifier([_FAIL])  # always fails
    draft = run_draft_verify_loop(full_profile, _opp(), _match(), drafter, verifier, max_revisions=2)

    assert draft.status == DraftStatus.NEEDS_HUMAN
    assert drafter.revise_calls == 2  # capped at max_revisions
    assert draft.unresolved_claims and draft.unresolved_claims[0].claim == "bad claim"


def test_cap_is_respected_exactly(full_profile):
    drafter = FakeDrafter()
    verifier = ScriptedVerifier([_FAIL])
    run_draft_verify_loop(full_profile, _opp(), _match(), drafter, verifier, max_revisions=3)
    # 3 in-loop verifies + 1 final verify; 3 revises.
    assert verifier.calls == 4
    assert drafter.revise_calls == 3


# --------------------------- pipeline -------------------------------------- #
class ScoringMatcher:
    """Scores opportunities by a lookup table on opportunity id."""

    def __init__(self, scores):
        self._scores = scores

    def score(self, profile, opportunity) -> Match:
        return Match(
            opportunity_id=opportunity.id,
            fit_score=self._scores[opportunity.id],
            reasoning="scored",
            low_confidence=profile.is_sparse(),
        )


def test_pipeline_ranks_and_drafts_only_strong(full_profile):
    opps = [
        Opportunity(id="weak", source=OpportunitySource.CURATED, title="Weak"),
        Opportunity(id="strong", source=OpportunitySource.GRANTS_GOV, title="Strong"),
    ]
    matcher = ScoringMatcher({"weak": 0.2, "strong": 0.85})
    drafter = FakeDrafter()
    verifier = ScriptedVerifier([_PASS])

    out = run_pipeline(
        full_profile, opps, matcher, drafter, verifier, strong_fit_threshold=0.6
    )

    # Ranked best-first.
    assert [r.opportunity.id for r in out.results] == ["strong", "weak"]
    # Only the strong match got a draft.
    assert out.results[0].draft is not None
    assert out.results[0].draft.status == DraftStatus.VERIFIED
    assert out.results[1].draft is None
    assert out.profile_sparse is False


def test_pipeline_marks_sparse_profile(sparse_profile):
    opps = [Opportunity(id="a", source=OpportunitySource.CURATED, title="A")]
    matcher = ScoringMatcher({"a": 0.1})
    out = run_pipeline(sparse_profile, opps, matcher, FakeDrafter(), ScriptedVerifier([_PASS]))
    assert out.profile_sparse is True
    assert out.results[0].match.low_confidence is True
