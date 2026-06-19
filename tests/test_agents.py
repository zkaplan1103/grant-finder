"""Phase 2 done-condition: each agent unit-tested against a MOCKED client,
asserting prompt assembly, model selection, and output parsing. No live calls.
"""

import json

import pytest

from app.agents import DrafterAgent, MatchAgent, VerifyAgent
from app.agents.parsing import AgentOutputError, extract_json_object
from app.models import DraftStatus, UnsupportedClaim
from tests.fakes import FakeLLMClient


# --------------------------- Match agent ----------------------------------- #
def test_match_model_thinking_and_cache(full_profile, opportunity):
    client = FakeLLMClient(
        json.dumps(
            {
                "fit_score": 0.82,
                "reasoning": "Good fit.",
                "low_confidence": False,
                "caveats": [],
            }
        )
    )
    match = MatchAgent(client).score(full_profile, opportunity)

    assert match.fit_score == 0.82
    assert match.opportunity_id == "OPP-1"

    call = client.calls[0]
    assert call["model"] == "claude-sonnet-4-6"  # Sonnet for Match
    assert call["thinking"] == {"type": "adaptive"}  # adaptive thinking on
    # cache_control on the shared profile+requirements prefix block.
    assert call["system"][-1]["cache_control"] == {"type": "ephemeral"}
    prefix = call["system"][-1]["text"]
    assert "NONPROFIT PROFILE" in prefix and "FUNDING OPPORTUNITY" in prefix


def test_match_sparse_low_confidence_parsing(sparse_profile, opportunity):
    client = FakeLLMClient(
        json.dumps(
            {
                "fit_score": 0.4,
                "reasoning": "Limited info.",
                "low_confidence": True,
                "caveats": ["ranked on limited info; add geography for better fit"],
            }
        )
    )
    match = MatchAgent(client).score(sparse_profile, opportunity)
    assert match.low_confidence is True
    assert match.caveats == ["ranked on limited info; add geography for better fit"]


def test_match_tolerates_fenced_json(full_profile, opportunity):
    client = FakeLLMClient(
        '```json\n{"fit_score": 0.5, "reasoning": "ok", "low_confidence": false}\n```'
    )
    match = MatchAgent(client).score(full_profile, opportunity)
    assert match.fit_score == 0.5


# --------------------------- Drafter agent --------------------------------- #
def test_drafter_draft_model_and_parsing(full_profile, opportunity, strong_match):
    client = FakeLLMClient(
        json.dumps(
            {"eligibility_summary": "Eligible as 501(c)(3).", "boilerplate": "We are..."}
        )
    )
    draft = DrafterAgent(client).draft(full_profile, opportunity, strong_match)

    assert draft.status == DraftStatus.DRAFT
    assert draft.revision == 0
    assert draft.eligibility_summary == "Eligible as 501(c)(3)."

    call = client.calls[0]
    assert call["model"] == "claude-sonnet-4-6"  # Sonnet for Draft
    assert call["thinking"] is None  # no adaptive thinking on Draft
    assert call["system"][-1]["cache_control"] == {"type": "ephemeral"}


def test_drafter_revise_feeds_specific_failures(full_profile, opportunity, strong_match):
    # First reply = initial draft; second = revised draft.
    client = FakeLLMClient(
        [
            json.dumps({"eligibility_summary": "S0", "boilerplate": "B0 claims TX"}),
            json.dumps({"eligibility_summary": "S1", "boilerplate": "B1 fixed"}),
        ]
    )
    agent = DrafterAgent(client)
    draft0 = agent.draft(full_profile, opportunity, strong_match)
    failures = [UnsupportedClaim(claim="Org is in TX", reason="Profile says CA")]
    draft1 = agent.revise(full_profile, opportunity, draft0, failures)

    assert draft1.revision == 1
    assert draft1.boilerplate == "B1 fixed"
    # The specific failure text is fed back into the revise prompt.
    revise_msg = client.calls[1]["messages"][0]["content"]
    assert "Org is in TX" in revise_msg and "Profile says CA" in revise_msg


# --------------------------- Verify agent ---------------------------------- #
def test_verify_model_thinking_and_pass(full_profile, opportunity):
    client = FakeLLMClient(json.dumps({"passed": True, "failures": []}))
    from app.models import Draft

    draft = Draft(opportunity_id="OPP-1", eligibility_summary="s", boilerplate="b")
    result = VerifyAgent(client).verify(full_profile, opportunity, draft)

    assert result.passed is True and result.failures == []
    call = client.calls[0]
    assert call["model"] == "claude-opus-4-8"  # Opus for Verify
    assert call["thinking"] == {"type": "adaptive"}
    assert call["system"][-1]["cache_control"] == {"type": "ephemeral"}


def test_verify_returns_specific_failures(full_profile, opportunity):
    client = FakeLLMClient(
        json.dumps(
            {
                "passed": False,
                "failures": [{"claim": "Serves 10k people", "reason": "Not in profile"}],
            }
        )
    )
    from app.models import Draft

    draft = Draft(opportunity_id="OPP-1", eligibility_summary="s", boilerplate="b")
    result = VerifyAgent(client).verify(full_profile, opportunity, draft)
    assert result.passed is False
    assert result.failures[0].claim == "Serves 10k people"


def test_verify_failures_force_not_passed(full_profile, opportunity):
    # Even if the model says passed=true, a non-empty failures list overrides.
    client = FakeLLMClient(
        json.dumps({"passed": True, "failures": [{"claim": "x", "reason": "y"}]})
    )
    from app.models import Draft

    draft = Draft(opportunity_id="OPP-1", eligibility_summary="s", boilerplate="b")
    result = VerifyAgent(client).verify(full_profile, opportunity, draft)
    assert result.passed is False


# --------------------------- parsing helper -------------------------------- #
def test_extract_json_with_leading_prose():
    obj = extract_json_object('Here is the result: {"a": 1, "b": "two"} done.')
    assert obj == {"a": 1, "b": "two"}


def test_extract_json_missing_raises():
    with pytest.raises(AgentOutputError):
        extract_json_object("no json here")
