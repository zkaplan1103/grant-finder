"""Score the Verify agent against labeled cases.

Per case, every sentence is either planted (should be flagged) or grounded (should
not be). We match Verify's flagged claims to planted sentences by tag keyword, then
roll up to a confusion matrix and precision / recall / F1.

  TP: a planted sentence that Verify flagged
  FN: a planted sentence Verify missed (a hallucination slipped through — the
      costly error for this product)
  FP: a flag that doesn't correspond to any planted sentence (Verify cried wolf
      on grounded text)
  TN: a grounded sentence Verify correctly left alone
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List

from app.models import UnsupportedClaim
from eval.cases import EvalCase, Sentence

# A matcher decides "does this Verify flag refer to this planted sentence?".
# The default is deterministic token overlap (free, used by CI/tests); --judge
# swaps in an LLM judge (eval/judge.py) for the rigorous, non-deterministic run.
Matcher = Callable[[UnsupportedClaim, Sentence], bool]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def token_matcher(flag: UnsupportedClaim, sentence: Sentence) -> bool:
    """Match on shared distinctive tokens between the flagged claim and the
    planted sentence. Numbers and proper nouns (the stuff that gets fabricated)
    are distinctive, so require overlap on the sentence's content words.

    Blind spot this leaves (the reason --judge exists): a flag that catches a
    claim in *different words* scores as a miss, and a vague flag that happens to
    share words scores as a catch. Surface-form, not meaning.
    """
    flag_tokens = set(_norm(flag.claim).split())
    sent_tokens = [t for t in _norm(sentence.text).split() if len(t) > 3]
    if not sent_tokens:
        return False
    overlap = sum(1 for t in sent_tokens if t in flag_tokens)
    return overlap >= max(2, len(sent_tokens) // 3)


@dataclass
class CaseScore:
    name: str
    difficulty: str = "obvious"
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    missed_tags: List[str] = field(default_factory=list)  # planted but not flagged
    false_alarms: List[str] = field(default_factory=list)  # flagged grounded text
    errored: bool = False  # Verify call/parse failed for this case


@dataclass
class Report:
    cases: List[CaseScore] = field(default_factory=list)

    @property
    def tp(self) -> int:
        return sum(c.tp for c in self.cases)

    @property
    def fp(self) -> int:
        return sum(c.fp for c in self.cases)

    @property
    def fn(self) -> int:
        return sum(c.fn for c in self.cases)

    @property
    def tn(self) -> int:
        return sum(c.tn for c in self.cases)

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def subset(self, difficulty: str) -> "Report":
        """A Report over just the cases of one difficulty tier — reuses every
        metric property above, so per-tier scoring needs no duplicated math."""
        return Report(cases=[c for c in self.cases if c.difficulty == difficulty])


def score_case(
    case: EvalCase,
    flags: List[UnsupportedClaim],
    matcher: Matcher = token_matcher,
) -> CaseScore:
    """Score one case given the Verify agent's flagged claims and a matcher."""
    cs = CaseScore(name=case.name, difficulty=case.difficulty)
    matched_flag_idx: set[int] = set()

    for sent in case.all_sentences():
        hit = False
        for i, flag in enumerate(flags):
            if matcher(flag, sent):
                hit = True
                matched_flag_idx.add(i)
        if sent.planted:
            if hit:
                cs.tp += 1
            else:
                cs.fn += 1
                cs.missed_tags.append(sent.tag)
        else:
            if hit:
                cs.fp += 1
                cs.false_alarms.append(sent.tag)
            else:
                cs.tn += 1

    # Flags that matched nothing are also false alarms (Verify invented a problem).
    for i, flag in enumerate(flags):
        if i not in matched_flag_idx:
            cs.fp += 1
            cs.false_alarms.append(f"unmatched:{flag.claim[:40]}")

    return cs


def diff_reports(old: dict, new: dict) -> list[dict]:
    """Find cases that regressed (were passing, now failing)."""
    old_by_name = {c["name"]: c for c in old["cases"]}
    regressions = []
    for c in new["cases"]:
        prev = old_by_name.get(c["name"])
        if prev is None:
            continue
        if prev["fn"] == 0 and c["fn"] > 0:
            regressions.append({"name": c["name"], "type": "recall_regression", "fn": c["fn"]})
        if prev["fp"] == 0 and c["fp"] > 0:
            regressions.append({"name": c["name"], "type": "precision_regression", "fp": c["fp"]})
    return regressions
