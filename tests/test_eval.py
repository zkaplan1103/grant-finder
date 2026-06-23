"""Offline tests for the eval harness itself — no live API.

We feed the scorer hand-built Verify outputs and assert the confusion matrix and
metrics are computed correctly, plus drive the full runner with a fake client.
"""

import json

from app.models import UnsupportedClaim
from eval.cases import EvalCase, Sentence, load_cases
from eval.scorer import Report, score_case
from tests.fakes import FakeLLMClient


def _case() -> EvalCase:
    # 2 planted, 2 grounded.
    c = load_cases()[0]  # hand/invented-award-and-geo: 2 planted, 3 grounded
    return c


def test_scorer_perfect_detection():
    case = _case()
    # Flag exactly the planted sentences (copy their text so tokens overlap).
    planted = [s for s in case.all_sentences() if s.planted]
    flags = [UnsupportedClaim(claim=s.text, reason="unsupported") for s in planted]
    cs = score_case(case, flags)
    assert cs.fn == 0  # nothing missed
    assert cs.tp == len(planted)
    assert cs.false_alarms == []  # grounded text untouched


def test_scorer_counts_missed_hallucination():
    case = _case()
    cs = score_case(case, [])  # Verify flagged nothing
    assert cs.tp == 0
    assert cs.fn == len(case.planted_tags())  # every planted claim missed
    assert set(cs.missed_tags) == set(case.planted_tags())


def test_scorer_counts_false_alarm_on_grounded():
    case = _case()
    grounded = [s for s in case.all_sentences() if not s.planted][0]
    flags = [UnsupportedClaim(claim=grounded.text, reason="bogus")]
    cs = score_case(case, flags)
    assert cs.fp >= 1  # flagged grounded text


def test_report_metrics():
    r = Report()
    # Build a known confusion matrix by hand via score_case on a synthetic case.
    case = EvalCase(
        name="synthetic",
        profile=_case().profile,
        opportunity=_case().opportunity,
        eligibility_sentences=[
            Sentence("The org received a fake 5 million dollar award yesterday.", True, "u"),
            Sentence("The applicant is a 501(c)(3) organization here.", False, "g"),
        ],
    )
    flags = [UnsupportedClaim(claim="received a fake 5 million dollar award yesterday", reason="x")]
    r.cases.append(score_case(case, flags))
    assert r.tp == 1 and r.fn == 0
    assert r.recall == 1.0
    assert 0.0 <= r.precision <= 1.0


def test_runner_with_fake_client_no_failures():
    """Full runner path: a fake Verify that always passes -> all planted missed."""
    from eval.run import run, to_dict

    client = FakeLLMClient(json.dumps({"passed": True, "failures": []}))
    report = run(client)
    assert len(report.cases) == len(load_cases())
    # A Verify that flags nothing catches no hallucinations.
    assert report.tp == 0
    d = to_dict(report)
    assert "overall" in d and d["overall"]["recall"] == 0.0
    assert "by_difficulty" in d and "adversarial" in d["by_difficulty"]


def test_difficulty_split_present():
    """Cases carry a difficulty tier and the report can subset by it."""
    cases = load_cases()
    levels = {c.difficulty for c in cases}
    assert levels == {"obvious", "adversarial"}

    from eval.run import run

    report = run(FakeLLMClient(json.dumps({"passed": True, "failures": []})))
    adv = report.subset("adversarial")
    obv = report.subset("obvious")
    assert len(adv.cases) > 0 and len(obv.cases) > 0
    assert len(adv.cases) + len(obv.cases) == len(report.cases)
