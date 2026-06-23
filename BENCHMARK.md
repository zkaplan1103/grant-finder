# Verify Agent Benchmark — Hallucination Detection

The Verify agent is Grant Navigator's trust layer: it reads a drafted grant
application and flags every factual claim the nonprofit's profile and the
opportunity's stated requirements do **not** support. This document is the
evidence that it works — and the record of what building the evidence taught me.

> **TL;DR.** A 31-case, difficulty-tiered eval. Verify (Opus 4.8) scores
> **100% precision / 100% recall** across all tiers. The number is less
> interesting than how it got there: the eval's most valuable run was the one
> that *failed*, and the failure turned out to be in my test set, not the model.

Run it yourself:

```bash
ANTHROPIC_API_KEY=sk-... python -m eval.run --json eval_report.json
python -m eval.run --judge   # score with an LLM judge instead of token overlap
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

The scorer matches Verify's flags against the planted sentences into a confusion
matrix (`eval/scorer.py`):

| | Verify flagged | Verify didn't |
|---|---|---|
| **planted** | TP (caught) | FN (**hallucination slipped through**) |
| **grounded** | FP (cried wolf) | TN (correct silence) |

**Two matchers.** The default matches a flag to a planted claim by shared
content tokens — deterministic and free, so CI and unit tests cost nothing. But
token overlap scores *surface form*, not meaning, so `--judge` swaps in an LLM
judge that decides "does this flag refer to this claim?" semantically. Running
both is a check on the scorer itself: **on this set they agree cell-for-cell**,
which is how I know the headline number isn't an artifact of a lenient matcher.

---

## Difficulty tiers — the split is the point

A single accuracy number is easy to inflate with soft cases. So cases carry a
`difficulty` tier and each is scored separately. The tiers escalate the *kind of
reasoning* required, not just the surface trickiness:

- **`obvious` (16 cases)** — blatant fabrications: a $2M prize that's nowhere in
  the profile, a headquarters in the wrong state. The easy baseline.
- **`adversarial` (7 cases)** — claims verifiers actually miss: an invented count
  on a real category, a near-miss tenure ("501(c)(3) for over ten years" when the
  org is 8), an overstated geography, an unstated technical inference, plus a
  hard negative (a wordy-but-true claim Verify must *not* flag).
- **`hard` (9 cases)** — engineered to make Verify miss, requiring a reasoning
  step beyond "is this fact stated?":
  - **Arithmetic** — a $300K ask against a stated $250K award ceiling; "a quarter
    of our budget" when $300K of $800K is 37.5%.
  - **Multi-hop** — claiming a *rural* set-aside when the set-aside rule is in the
    opportunity and the org's *urban* service area is in the profile (neither fact
    alone is a violation; the claim is only false when you chain them).
  - **Unit confusion** — a 120 kW system inflated to 120 MW (1000×).
  - **State/temporal contradiction** — "currently operating" against a profile
    stage of "planning".
  - **Cost mismatch** — "fully funds the project" when the ask covers half the cost.
  - **Precision traps** — strong-sounding but fully-supported claims, to test
    over-flagging under pressure.

---

## Results

Verify on Opus 4.8 (the strongest model — deliberately, because subtle
unsupported claims are exactly what a cheaper model waves through):

```
[obvious    ]  P 100%  R 100%  F1 100%   (TP 17 FP 0 FN 0 TN 34)
[adversarial]  P 100%  R 100%  F1 100%   (TP  6 FP 0 FN 0 TN  7)
[hard       ]  P 100%  R 100%  F1 100%   (TP  7 FP 0 FN 0 TN 10)
[OVERALL    ]  P 100%  R 100%  F1 100%   (TP 30 FP 0 FN 0 TN 51)
```

Verify caught every planted hallucination including the arithmetic and multi-hop
cases, and left all 51 grounded claims alone. This is the evidence behind the
architectural choice to run Verify on Opus 4.8 rather than a cheap model.

---

## What the eval actually taught me (the useful part)

A clean 100% on an easy set is a victory lap, not a measurement. The hard tier
existed specifically to break that — and the run that mattered most is the one
where it *did*:

**The hard tier first scored P 88% — one false positive.** Verify had flagged a
claim I'd labeled "clean": *"The organization serves a disadvantaged community,
**as the funder requires**."* My first instinct was a Verify precision bug, and I
softened the Verify prompt to flag less aggressively. **It didn't change the
result** — same FP, same case.

That ruled out the easy explanation and forced me to read the case itself. The
profile *does* say the org serves a disadvantaged community — but the
opportunity text says nothing about that being **required** (its only conditional
rule is a rural set-aside). The "as the funder requires" clause was an
unsupported claim about the funder's rules. **Verify was right. My ground truth
was wrong.**

The fix was to the *test set*, not the model: I corrected the mislabeled case to
a genuinely-supported claim and added a second, unambiguous precision trap. The
re-run went to 100% — because the system had been correct all along.

**The lesson I'd put in front of an interviewer:** a good eval stress-tests the
test set, not just the system. The most valuable output of this benchmark wasn't
the 100% — it was catching that one of my own "ground truth" labels was wrong,
which is the exact error mode that makes most hand-rolled evals quietly
meaningless. I also kept the prompt guardrail (flag only what you can show is
unsupported, not what merely sounds strong) — it's a correct improvement on its
own merits, even though it wasn't what resolved this case. Reporting that
honestly matters more than claiming a tidy fix.

---

## Honest limitations

- **31 single-domain cases.** All solar/clean-energy nonprofits. A real benchmark
  would span domains (the pipeline is domain-agnostic; the eval isn't yet).
- **100% means the set still isn't hard enough to find Verify's ceiling.** The
  hard tier drew blood once (via a labeling error, then fixed); it hasn't yet
  produced a *genuine* model miss. The next escalation is cross-document
  reasoning and longer drafts where claims interact.
- **The token matcher can't score claims phrased with no shared vocabulary** —
  that's why `--judge` exists; it should become the default once cases get
  ambiguous enough that surface overlap is unreliable.
- **The judge is itself an LLM** and inherits LLM judgment error; it's a
  cross-check on the token matcher, not an oracle.

These are the next moves, not excuses — an eval that never fails has stopped
measuring.
