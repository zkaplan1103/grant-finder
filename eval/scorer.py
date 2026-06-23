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
from typing import List

from app.models import UnsupportedClaim
from eval.cases import EvalCase, Sentence


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def _flag_matches_sentence(flag: UnsupportedClaim, sentence: Sentence) -> bool:
    """Does this Verify flag refer to this planted sentence?

    Match on shared distinctive tokens between the flagged claim text and the
    planted sentence. Numbers and proper nouns (the stuff that gets fabricated)
    are distinctive, so require overlap on the sentence's content words.
    """
    flag_tokens = set(_norm(flag.claim).split())
    sent_tokens = [t for t in _norm(sentence.text).split() if len(t) > 3]
    if not sent_tokens:
        return False
    overlap = sum(1 for t in sent_tokens if t in flag_tokens)
    # The flag must cover a meaningful share of the planted sentence's content.
    return overlap >= max(2, len(sent_tokens) // 3)


@dataclass
class CaseScore:
    name: str
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


def score_case(case: EvalCase, flags: List[UnsupportedClaim]) -> CaseScore:
    """Score one case given the Verify agent's flagged claims."""
    cs = CaseScore(name=case.name)
    matched_flag_idx: set[int] = set()

    for sent in case.all_sentences():
        hit = False
        for i, flag in enumerate(flags):
            if _flag_matches_sentence(flag, sent):
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
