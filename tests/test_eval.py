"""Offline tests for the eval harness itself — no live API.

We feed the scorer hand-built Verify outputs and assert the confusion matrix and
metrics are computed correctly, plus drive the full runner with a fake client.
"""

import json

from app.models import UnsupportedClaim
from eval.cases import EvalCase, Sentence, load_cases
from eval.judge import make_judge_matcher
from eval.run import _ci95
from eval.scorer import Report, diff_reports, score_case
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


def test_judge_matcher_scores_paraphrase_as_catch():
    """The judge matches on meaning: a paraphrased flag the token matcher would
    miss still counts as a catch when the judge says it refers to the claim."""
    case = EvalCase(
        name="judge-test",
        profile=_case().profile,
        opportunity=_case().opportunity,
        eligibility_sentences=[
            Sentence("The org operates a fleet of 30 electric vehicles.", True, "u-fleet"),
        ],
    )
    # Flag shares almost no surface tokens with the sentence — token matcher misses it.
    flag = UnsupportedClaim(claim="unsupported assertion about thirty vans", reason="x")

    # Judge says yes -> counted as a true positive.
    judge_yes = make_judge_matcher(FakeLLMClient(json.dumps({"refers_to": True})))
    cs = score_case(case, [flag], matcher=judge_yes)
    assert cs.tp == 1 and cs.fn == 0

    # Judge says no -> the planted claim is missed.
    judge_no = make_judge_matcher(FakeLLMClient(json.dumps({"refers_to": False})))
    cs = score_case(case, [flag], matcher=judge_no)
    assert cs.fn == 1


def test_difficulty_split_present():
    """Cases carry a difficulty tier and the report can subset by it."""
    cases = load_cases()
    levels = {c.difficulty for c in cases}
    assert levels == {"obvious", "adversarial", "hard"}

    from eval.run import run

    report = run(FakeLLMClient(json.dumps({"passed": True, "failures": []})))
    tiers = ["obvious", "adversarial", "hard"]
    counts = {t: len(report.subset(t).cases) for t in tiers}
    assert all(n > 0 for n in counts.values())  # every tier populated
    assert sum(counts.values()) == len(report.cases)  # tiers partition the set


# --------------------------------------------------------------------------- #
# diff_reports tests
# --------------------------------------------------------------------------- #

def test_diff_reports_no_regression():
    old = {"cases": [{"name": "a", "fn": 0, "fp": 0}]}
    new = {"cases": [{"name": "a", "fn": 0, "fp": 0}]}
    assert diff_reports(old, new) == []


def test_diff_reports_recall_regression():
    old = {"cases": [{"name": "a", "fn": 0, "fp": 0}]}
    new = {"cases": [{"name": "a", "fn": 2, "fp": 0}]}
    regs = diff_reports(old, new)
    assert len(regs) == 1
    assert regs[0]["type"] == "recall_regression"
    assert regs[0]["fn"] == 2


def test_diff_reports_precision_regression():
    old = {"cases": [{"name": "a", "fn": 0, "fp": 0}]}
    new = {"cases": [{"name": "a", "fn": 0, "fp": 3}]}
    regs = diff_reports(old, new)
    assert len(regs) == 1
    assert regs[0]["type"] == "precision_regression"
    assert regs[0]["fp"] == 3


def test_diff_reports_new_case_no_regression():
    old = {"cases": [{"name": "a", "fn": 0, "fp": 0}]}
    new = {"cases": [{"name": "a", "fn": 0, "fp": 0}, {"name": "b", "fn": 1, "fp": 1}]}
    assert diff_reports(old, new) == []


# --------------------------------------------------------------------------- #
# --cases filter + CI math tests
# --------------------------------------------------------------------------- #

def test_cases_filter():
    from eval.run import run

    client = FakeLLMClient(json.dumps({"passed": True, "failures": []}))
    report = run(client, case_filter="hand/*")
    assert len(report.cases) > 0
    assert all(c.name.startswith("hand/") for c in report.cases)
    assert len(report.cases) < len(load_cases())


def test_ci95_known_values():
    mu, lo, hi = _ci95([0.5, 0.5, 0.5])
    assert mu == 0.5
    assert lo == 0.5
    assert hi == 0.5

    mu, lo, hi = _ci95([0.7])
    assert mu == 0.7
    assert lo == 0.7
    assert hi == 0.7

    mu, lo, hi = _ci95([0.0, 1.0])
    assert abs(mu - 0.5) < 1e-9
    assert lo < mu
    assert hi > mu
    assert abs((hi - mu) - (mu - lo)) < 1e-9


# --------------------------------------------------------------------------- #
# Taxonomy tests
# --------------------------------------------------------------------------- #
def test_taxonomy_ids_valid():
    """Every planted sentence with a hallucination_type uses a valid taxonomy ID."""
    from eval.taxonomy import TAXONOMY_IDS

    cases = load_cases()
    for case in cases:
        for s in case.all_sentences():
            if s.planted and s.hallucination_type:
                assert s.hallucination_type in TAXONOMY_IDS, (
                    f"{case.name}: unknown hallucination_type {s.hallucination_type!r}"
                )


def test_taxonomy_no_orphans():
    """Every taxonomy ID appears in at least one planted sentence."""
    from eval.taxonomy import TAXONOMY_IDS, coverage_report

    report = coverage_report(load_cases())
    assert not report["uncovered"], (
        f"Taxonomy IDs with zero cases: {report['uncovered']}"
    )
    # Also verify counts keys are a subset of valid IDs (no stale types).
    assert set(report["counts"].keys()) <= TAXONOMY_IDS


def test_taxonomy_category_coverage():
    """The taxonomy spans the expected set of categories."""
    from eval.taxonomy import TAXONOMY_CATEGORIES

    expected = {"fabrication", "distortion", "logical", "attribution", "omission"}
    assert TAXONOMY_CATEGORIES == expected


# --------------------------------------------------------------------------- #
# Cross-domain case tests
# --------------------------------------------------------------------------- #

def test_legal_cases_load():
    from eval.cases_legal import load_legal_cases

    cases = load_legal_cases()
    assert len(cases) >= 8
    assert any(len(c.planted_tags()) == 0 for c in cases)
    assert all(c.name.startswith("legal/") for c in cases)


def test_medical_cases_load():
    from eval.cases_medical import load_medical_cases

    cases = load_medical_cases()
    assert len(cases) >= 8
    assert any(len(c.planted_tags()) == 0 for c in cases)
    assert all(c.name.startswith("med/") for c in cases)


def test_education_cases_load():
    from eval.cases_education import load_education_cases

    cases = load_education_cases()
    assert len(cases) >= 8
    assert any(len(c.planted_tags()) == 0 for c in cases)
    assert all(c.name.startswith("edu/") for c in cases)


def test_cross_domain_valid_taxonomy_types():
    """Every planted sentence across all domains has a valid hallucination_type."""
    from eval.cases_education import load_education_cases
    from eval.cases_legal import load_legal_cases
    from eval.cases_medical import load_medical_cases
    from eval.taxonomy import TAXONOMY_IDS

    for loader in [load_legal_cases, load_medical_cases, load_education_cases]:
        for case in loader():
            for sent in case.all_sentences():
                if sent.planted:
                    assert sent.hallucination_type, (
                        f"Planted sentence in {case.name} missing hallucination_type: "
                        f"{sent.tag}"
                    )
                    assert sent.hallucination_type in TAXONOMY_IDS, (
                        f"Invalid hallucination_type '{sent.hallucination_type}' "
                        f"in {case.name} / {sent.tag}"
                    )


def test_cross_domain_taxonomy_coverage():
    """Each domain covers at least 5 different taxonomy types."""
    from eval.cases_education import load_education_cases
    from eval.cases_legal import load_legal_cases
    from eval.cases_medical import load_medical_cases

    for name, loader in [
        ("legal", load_legal_cases),
        ("medical", load_medical_cases),
        ("education", load_education_cases),
    ]:
        types = {
            s.hallucination_type
            for c in loader()
            for s in c.all_sentences()
            if s.planted and s.hallucination_type
        }
        assert len(types) >= 5, f"{name} only covers {len(types)} taxonomy types: {types}"


def test_load_cases_includes_cross_domain():
    """load_cases() total count includes all domain cases."""
    from eval.cases_education import load_education_cases
    from eval.cases_legal import load_legal_cases
    from eval.cases_medical import load_medical_cases

    all_cases = load_cases()
    legal_count = len(load_legal_cases())
    medical_count = len(load_medical_cases())
    education_count = len(load_education_cases())

    cross_domain_names = {c.name for c in all_cases if c.name.startswith(("legal/", "med/", "edu/"))}
    assert len(cross_domain_names) == legal_count + medical_count + education_count


def test_cross_domain_tags_unique():
    """All tags across cross-domain cases are unique."""
    from eval.cases_education import load_education_cases
    from eval.cases_legal import load_legal_cases
    from eval.cases_medical import load_medical_cases

    all_tags = []
    for loader in [load_legal_cases, load_medical_cases, load_education_cases]:
        for case in loader():
            for sent in case.all_sentences():
                all_tags.append(sent.tag)
    assert len(all_tags) == len(set(all_tags)), "Duplicate tags found in cross-domain cases"


# --------------------------------------------------------------------------- #
# Adversarial cases (Task 3)
# --------------------------------------------------------------------------- #

def test_adversarial_cases_load():
    from eval.cases_adversarial import load_adversarial_cases

    adv = load_adversarial_cases()
    assert len(adv) == 20
    names = [c.name for c in adv]
    assert len(names) == len(set(names))


def test_adversarial_cases_in_load_cases():
    cases = load_cases()
    adv_names = [c.name for c in cases if c.name.startswith("advx/")]
    assert len(adv_names) == 20


def test_adversarial_cases_have_valid_structure():
    from eval.cases_adversarial import load_adversarial_cases

    for case in load_adversarial_cases():
        sents = case.all_sentences()
        assert len(sents) > 0, f"{case.name} has no sentences"
        for s in sents:
            assert s.tag, f"{case.name} has sentence with empty tag"
            assert s.text, f"{case.name} has sentence with empty text"


def test_adversarial_dry_run():
    from eval.adversarial import dry_run_report

    output = dry_run_report()
    assert "DRY RUN" in output


# --------------------------------------------------------------------------- #
# Multi-run stats (Task 4)
# --------------------------------------------------------------------------- #

def test_multi_run_with_fake_client():
    from eval.run import _print_multi_run, run

    client = FakeLLMClient(json.dumps({"passed": True, "failures": []}))
    cases = load_cases()[:3]
    reports = [run(client, cases=cases) for _ in range(3)]

    assert len(reports) == 3
    for r in reports:
        assert len(r.cases) == 3

    precisions = [r.precision for r in reports]
    mu, lo, hi = _ci95(precisions)
    assert lo <= mu <= hi

    _print_multi_run(reports)


def test_multi_run_json_output():
    from eval.run import _multi_run_dict, run

    client = FakeLLMClient(json.dumps({"passed": True, "failures": []}))
    cases = load_cases()[:3]
    reports = [run(client, cases=cases) for _ in range(3)]

    result = _multi_run_dict(reports)
    assert result["runs"] == 3
    assert "mean" in result["precision"]
    assert "ci_low" in result["precision"]
    assert len(result["per_run"]) == 3


# --------------------------------------------------------------------------- #
# Ablation runner (Task 5)
# --------------------------------------------------------------------------- #

def test_ablation_configs_well_formed():
    from eval.ablation import CONFIGS

    assert len(CONFIGS) >= 5
    for c in CONFIGS:
        assert "name" in c
        assert "model" in c
        assert "max_tokens" in c
        assert isinstance(c["max_tokens"], int)


def test_ablation_dry_run():
    from eval.ablation import dry_run_report

    output = dry_run_report()
    assert "DRY RUN" in output
    assert "opus-adaptive" in output


def test_ablation_monkey_patch():
    import app.agents.verify as verify_mod
    from eval.ablation import _run_with_config

    original_model = verify_mod.MODEL
    config = {
        "name": "test-config",
        "model": "claude-haiku-4-5",
        "thinking": None,
        "max_tokens": 4000,
    }
    client = FakeLLMClient(json.dumps({"passed": True, "failures": []}))
    cases = load_cases()[:1]

    result = _run_with_config(config, client, cases)
    assert client.calls[0]["model"] == "claude-haiku-4-5"
    assert client.calls[0]["max_tokens"] == 4000
    assert verify_mod.MODEL == original_model
    assert "precision" in result


# --------------------------------------------------------------------------- #
# Failure analysis (Task 6)
# --------------------------------------------------------------------------- #

def test_analysis_with_hand_built_report():
    from eval.analysis import analyze

    report = {
        "overall": {"tp": 5, "fp": 2, "fn": 3, "tn": 10},
        "cases": [
            {"name": "hand/test-1", "difficulty": "obvious",
             "tp": 2, "fp": 1, "fn": 1, "tn": 3,
             "missed": ["tag-a"], "false_alarms": ["tag-b"], "errored": False},
            {"name": "adv/test-2", "difficulty": "adversarial",
             "tp": 1, "fp": 0, "fn": 2, "tn": 4,
             "missed": ["tag-c", "tag-d"], "false_alarms": [], "errored": False},
        ],
    }

    result = analyze(report)
    assert result["total_cases"] == 2
    assert result["total_fn"] == 3
    assert result["total_fp"] == 1
    assert "miss_rate_by_difficulty" in result
    assert "suggestions" in result


def test_analysis_sample_mode():
    from eval.analysis import analyze, generate_sample_report, print_analysis

    report_data = generate_sample_report()
    assert "cases" in report_data
    result = analyze(report_data)
    assert result["total_cases"] > 0
    print_analysis(result)
