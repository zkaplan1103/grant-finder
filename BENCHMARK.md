# Verify Agent Benchmark — Hallucination Detection

The Verify agent is Grant Navigator's trust layer: it reads a drafted grant
application and flags every factual claim the nonprofit's profile and the
opportunity's stated requirements do **not** support. This document is the
evidence that it works — and the record of what building the evidence taught me.

> **TL;DR.** An 82-case, 4-domain, difficulty-tiered eval. Verify (Opus 4.8)
> scores **89% precision / 94% recall / 91% F1** overall (single run, N=1). The
> earlier version of this benchmark reported 100% across the board — that number
> was a symptom of an eval that was too easy, not a model that was perfect.
> Hardening the test set (cross-domain cases, high-density drafts, adversarial
> claims) pulled the score off the ceiling and surfaced three concrete,
> reproducible failure modes.

Run it yourself:

```bash
ANTHROPIC_API_KEY=sk-... python -m eval.run --json eval/reports/full-run-1.json
python -m eval.analysis eval/reports/full-run-1.json   # categorize the failures
python -m eval.run --judge                              # LLM judge instead of token overlap
```

---

## Why this exists

Wiring up agents that call each other is table stakes. The defensible question
for a trust-focused tool is: **does the safety check actually catch
hallucinations, and how do you know?** "It seems to work" is not an answer. So
Verify has a labeled benchmark with a confusion matrix, and the benchmark gates
CI (`--min-recall`).

A missed fabrication here is the worst-case failure: an invented eligibility
claim that gets a nonprofit barred. So **recall is the headline metric** —
precision matters too (crying wolf erodes trust), but a missed lie is the one
that does real-world harm.

---

## Method

Each case is a draft built from labeled sentences. Every sentence is either:

- **grounded** — supported by the profile/opportunity (Verify must leave it alone), or
- **planted** — an unsupported claim Verify *should* flag.

Every planted sentence also carries a **hallucination type** from a 14-type
taxonomy (`eval/taxonomy.py`) spanning five categories — fabrication,
distortion, logical error, attribution shift, and omission — so failures can be
attributed to a *kind* of error, not just a case name.

The scorer matches Verify's flags against the planted sentences into a confusion
matrix (`eval/scorer.py`):

| | Verify flagged | Verify didn't |
|---|---|---|
| **planted** | TP (caught) | FN (**hallucination slipped through**) |
| **grounded** | FP (cried wolf) | TN (correct silence) |

**Two matchers.** The default matches a flag to a planted claim by shared
content tokens — deterministic and free, so CI and unit tests cost nothing. But
token overlap scores *surface form*, not meaning, so `--judge` swaps in an LLM
judge that decides "does this flag refer to this claim?" semantically.

---

## Coverage

The set is 82 cases across **four domains** and three difficulty tiers:

| Domain | Cases | Notes |
|---|---|---|
| Solar / clean energy | 52 | Original domain: hand-written, generated, adversarial, hard |
| Legal aid | 10 | Legal-services nonprofit + LSC funding opportunity |
| Medical | 10 | Community health center + HRSA opportunity |
| Education | 10 | After-school STEM program + NSF opportunity |

Cross-domain cases are **variable-controlled**: each domain repeats the same
structural slots (invented credential, inflated count, scope inflation, negation
flip, attribution shift, arithmetic, high-density triple-planted, one clean
control) so a per-domain difference is attributable to *domain*, not to a
lopsided mix of easy vs hard cases.

The difficulty tiers escalate the *kind of reasoning* required:

- **`obvious` (28 cases)** — blatant fabrications: an award nowhere in the
  profile, a headquarters in the wrong state, an invented federal designation.
- **`adversarial` (39 cases)** — subtle single-claim traps: partial truths (one
  grounded clause + one fabricated clause in the same sentence), close-but-wrong
  numbers (245K vs 250K, "nearly a decade" vs 8 years), buried errors in dense
  boilerplate, negation flips ("has never failed an audit"), and precision-trap
  hard negatives (wordy-but-true claims Verify must *not* flag).
- **`hard` (15 cases)** — multi-step reasoning: arithmetic against a ceiling,
  multi-hop rule chaining (a *rural* set-aside claimed against an *urban* service
  area), unit confusion (kW vs MW), state/temporal contradictions, and
  high-density drafts packing three fabrications into one document.

---

## Results

Verify on Opus 4.8, single run (N=1), token matcher:

```
[obvious    ]  P 83%  R 96%  F1 89%   (TP 25 FP 5 FN 1 TN 47)
[adversarial]  P 92%  R 97%  F1 95%   (TP 36 FP 3 FN 1 TN 46)
[hard       ]  P 89%  R 84%  F1 86%   (TP 16 FP 2 FN 3 TN 14)
[OVERALL    ]  P 89%  R 94%  F1 91%   (TP 77 FP 10 FN 5 TN 107)
```

Failure analysis (`python -m eval.analysis`):

```
Miss rate by difficulty:  hard 20% | obvious 4% | adversarial 3%
Miss rate by domain:      education 30% | medical 10% | solar 2% | legal 0%
FP rate  by difficulty:   obvious 18% | hard 13% | adversarial 8%
```

---

## What the numbers reveal

Three findings survive the noise of a single run:

**1. Domain unfamiliarity degrades recall.** Education misses 30% of its planted
claims; solar misses 2%. Because the cross-domain cases are variable-controlled,
this isn't a "harder cases in education" artifact — the *same* structural traps
are caught in solar and missed in education. The verifier is measurably better on
the domain its context is saturated with.

**2. Density + unfamiliarity collapses together.** The single worst case is
`edu/high-density-three-planted`: three fabrications in one education draft,
**zero caught**. The identical structure in legal and medical caught all three.
So it isn't dense context alone that breaks Verify — it's dense context *in an
unfamiliar domain*, where the two stressors compound.

**3. Precision is the softer flank.** 10 false alarms, and the ones that matter
land on **clean control documents** (`legal/clean-no-planted`,
`med/clean-no-planted`) — drafts with zero planted errors where Verify invented
problems anyway. Crying wolf on a clean document is the trust-eroding failure
mode, and it too concentrates in the unfamiliar domains.

**One counterintuitive result.** The `adversarial` tier scored *higher* (F1 95%)
than `obvious` (89%) and `hard` (86%). Our hand-written "adversarial" cases,
despite the label, are clean single-claim signals the model handles well. The
genuinely hard axis is what lives in the `hard` tier — multi-hop reasoning,
arithmetic, and cross-domain density. That's a note that our difficulty
*labeling* is imperfect, and a direction for the next escalation.

---

## What hardening the eval actually taught me

The previous version of this benchmark scored 100% and I wrote a paragraph
celebrating it. That was the tell. **A clean 100% on an easy, single-domain set
measures the set, not the model.** The most valuable work here was making the
eval capable of failing:

- Added three new domains (legal, medical, education) — immediately exposed the
  domain-unfamiliarity gap that a solar-only set could never see.
- Added high-density drafts (three planted claims per document) — exposed the
  density-collapse failure that single-claim cases hid.
- Added a hallucination taxonomy so misses map to a *kind* of error, making the
  failure analysis actionable rather than a list of case names.
- Kept the clean-control cases honest — they're the only way to measure the
  false-alarm rate that the 100%-precision story had swept under the rug.

An earlier iteration also caught a labeling error in my own ground truth (a
"clean" case that was actually an unsupported claim about a funder's rules —
Verify was right, my label was wrong). That lesson stands: **a good eval
stress-tests the test set, not just the system.**

---

## Honest limitations

- **Single run (N=1).** These numbers have no error bars yet. The education miss
  rate in particular (30% off 10 cases) could shift on a re-run. `--runs 3`
  produces 95% confidence intervals (stdlib t-distribution, `eval/run.py`); it
  costs more API and hasn't been run. Treat the per-domain rates as directional,
  not precise.
- **Difficulty labels are imperfect.** The `adversarial` tier out-scoring `hard`
  shows the tiers don't cleanly rank by real difficulty. The taxonomy captures
  *type*; a principled difficulty ordering is future work.
- **The token matcher scores surface form, not meaning.** `--judge` exists for
  claims phrased with no shared vocabulary; it should become the default as cases
  get more ambiguous. The judge is itself an LLM and inherits LLM judgment error.
- **Ablation not yet run.** `eval/ablation.py` compares Opus/Sonnet/Haiku ×
  thinking on/off; it's built and structurally tested but not run live, so the
  "Opus is worth it" claim is asserted, not yet measured here.

These are the next moves, not excuses — an eval that never fails has stopped
measuring.
