# Grant Navigator

A multi-agent system that takes a nonprofit's profile and produces a ranked,
cited set of funding matches with drafted application boilerplate — with a
verification step that refuses to let unsupported claims into a draft.

The funding focus is free-text: a nonprofit enters whatever it's seeking money
for (solar, youth literacy, food security, …) and the live federal search runs
against that. The project started as a solar-specific tool (see below) and the
architecture generalizes to any nonprofit funding domain.

## 1. Problem & why it matters

For the nonprofits chasing grant money, the hardest part is **finding and
winning funding**. A caseworker doing this by hand juggles grants.gov, a dozen
foundation sites, and a spreadsheet, then hand-writes eligibility summaries. It
is slow and error-prone, and a single fabricated eligibility claim can get an
org barred.

The original motivating case: after the EPA cancelled **Solar for All** in
August 2025, solar nonprofits were scrambling to replace that money from a
fragmented field of federal grants, foundations, and state programs. Soft costs
(of which funding is the worst) make up ~65% of residential solar cost. Solar
remains the showcase domain — the curated source list below is solar-focused —
but the pipeline itself is domain-agnostic.

## 2. What it does

Single org profile in → ranked funding matches (live federal search + a curated
set of foundation/state sources) + drafted boilerplate out, each match cited and
fit-reasoned. Strong matches get boilerplate that has passed a Drafter⇄Verify
loop, or is flagged with the specific unsupported claims for human review.

**Curated-source coverage is deliberately solar-only (v1).** The live
grants.gov search works for any funding focus, but the hand-vetted
foundation/state sources in `app/sources.yaml` cover solar/clean-energy only.
A non-solar org gets full federal results and no curated hits — by design, not a
bug: hand-curating high-value sources for every nonprofit category is a
data-operations effort, out of scope for this v1, which exists to demonstrate
the multi-agent matching + verification architecture on one well-covered domain.
The Match agent scores any off-domain curated entry as a poor fit, so nothing
wrong leaks through. See §8.

## 3. Architecture

```
Profile (required core + optional context)
   -> ICP->params mapper      deterministic, wide-net, no LLM
   -> Discovery               live grants.gov Search2 + curated YAML
   -> Match agent (Sonnet)    semantic fit scoring; ranks; degrades gracefully
   -> Drafter (Sonnet) <-> Verify (Opus)   bounded loop, escalate holdouts
   -> Human review of flagged items
```

Three agents, one bounded loop. Discovery is a **tool**, not an agent. Source
trust is a **config list**, vetted at design time, not an agent.

See `PRD.md` for the full product spec and `BUILD_PLAN.md` for the build order.

## 4. Stack

Python, official `anthropic` SDK with a **manual** agentic loop (no
LangGraph/CrewAI), Pydantic models, SQLite via stdlib `sqlite3` (no ORM, no
migration framework). The backend is a FastAPI JSON API (`POST /api/match`);
the frontend is a React + TypeScript + Tailwind SPA (Vite) that FastAPI serves
as static files in production — a 3-step wizard with a glassmorphic design.

- **Match + Draft:** Sonnet 4.6 (`claude-sonnet-4-6`).
- **Verify:** Opus 4.8 (`claude-opus-4-8`) — the safety check runs on the
  strongest model because a cheap model silently waves through hallucinations.
- `thinking={"type": "adaptive"}` on Match + Verify.
- Prompt caching (`cache_control: {"type": "ephemeral"}`) on the shared
  profile + requirements prefix.

## 5. Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in ANTHROPIC_API_KEY for live runs

cd frontend && npm install && npm run build && cd ..   # builds the SPA to frontend/dist
```

Run the app (FastAPI serves the built SPA at `/` and the API at `/api`):

```bash
uvicorn app.web:app --reload
```

The app boots without an API key; running the live pipeline needs
`ANTHROPIC_API_KEY` in the environment.

**Frontend dev mode** (hot reload): run the API and the Vite dev server
together — Vite proxies `/api` to FastAPI.

```bash
uvicorn app.web:app --reload --port 8000     # terminal 1
cd frontend && npm run dev                    # terminal 2 → http://localhost:5173
```

## 6. Tests (free)

The whole suite runs offline — the Anthropic client is mocked and grants.gov
HTTP is mocked with `respx`. No money is spent.

```bash
pytest
```

## 7. Evaluating the Verify agent (the trust layer)

Anyone can wire up agents that *call each other*. The hard, interview-worthy
question is: **does the safety check actually catch hallucinations, and how do
you know?** So the Verify agent has its own evaluation harness.

`eval/` holds a labeled set of drafts (`eval/cases.py`) where every sentence is
tagged as either **grounded** (supported by the profile/opportunity) or
**planted** (a claim Verify *should* flag). The runner scores Verify's flags
against ground truth into a confusion matrix:

```bash
ANTHROPIC_API_KEY=sk-... python -m eval.run --json eval_report.json
```

- **Recall** — of planted hallucinations, how many were caught. This is the
  number that matters: a missed fabricated eligibility claim is the failure that
  gets a nonprofit barred.
- **Precision** — of flags raised, how many were real (vs. crying wolf on
  grounded text).
- `--min-recall 0.9` makes the eval a **gate** (non-zero exit below threshold),
  so a prompt change that regresses detection fails CI.

### Cases are split by difficulty — the split is the point

A single accuracy number is easy to game with soft test cases, so cases carry a
`difficulty` tier and the harness reports each separately:

- **`obvious`** (16 cases) — blatant fabrications: a $2M prize that's nowhere in
  the profile, a headquarters in the wrong state. The easy baseline.
- **`adversarial`** (7 cases) — the claims verifiers actually miss: an invented
  count on a *real* category ("installed solar for 5,000 households" when the
  profile names the population but no number), a near-miss eligibility ("501(c)(3)
  for over ten years" when the org is 8), an overstated geography ("western US"
  for a California org), an unstated technical inference ("includes battery
  storage" — never mentioned), and a **hard negative**: a wordy-but-true claim
  that Verify must *not* flag.

Latest run (Verify on Opus 4.8):

```
[obvious    ]  P 100%  R 100%  F1 100%   (TP 17 FP 0 FN 0 TN 34)
[adversarial]  P 100%  R 100%  F1 100%   (TP  6 FP 0 FN 0 TN  7)
[OVERALL    ]  P 100%  R 100%  F1 100%   (TP 23 FP 0 FN 0 TN 41)
```

This is the evidence behind a deliberate architecture choice: **Verify runs on
the strongest model (Opus 4.8), not a cheap one, because subtle unsupported
claims are exactly what a weaker model waves through.** The eval is what lets me
claim that rather than assert it.

**Honest limitation:** at 23 single-domain cases the set is *saturated* — 100%
means it isn't yet hard enough to find Verify's breaking point. An eval that
never fails has stopped measuring. The next step is a larger, harder, multi-domain
set (and an LLM-judge matcher for claims that don't share surface tokens) to
locate where detection actually degrades.

The harness is itself unit-tested offline (`tests/test_eval.py`) with a fake
client — the scorer's confusion-matrix logic is verified without spending a
cent.

## 8. Running tests that cost money

See `BUILD_REPORT.md` for the exact env vars, commands, and cost estimates for
the optional live end-to-end checks against the real Anthropic API and the live
grants.gov endpoint.

## 9. Why a deterministic CI gate, not a builder/checker agent loop

The build-and-fix workflow for this repo is a plain script — `./check.sh` runs
`ruff` + `pytest`, reports exactly what's red, and a human (or me, in an
editor session) fixes it and re-runs. I deliberately did **not** build the
popular "builder agent ↔ checker agent ↔ orchestrator" loop, where one LLM
writes code, another runs the checks, and an orchestrator loops them until
green. The reasoning is worth stating, because it's an engineering-judgment call,
not a capability gap:

1. **The checker has no reason to be an LLM.** `ruff` and `pytest` are
   deterministic oracles — same input, same verdict, in milliseconds, for free.
   Wrapping them in an agent adds a non-deterministic narrator over a
   deterministic truth. You'd be paying tokens and latency for a model to *read
   you* an exit code the shell already returns. The right tool for a decidable
   check is the decidable check.

2. **The loop body is the expensive part, and it's the same either way.** The
   only step that genuinely needs intelligence is *writing the fix*. Whether a
   human reads `check.sh` output and prompts the fix, or an "orchestrator" feeds
   it to a "builder," the model does identical work. The agent framing adds a
   second model call per turn (the checker), inter-agent plumbing, and a cold
   context re-derivation on every spawn — pure overhead around the one step that
   was already the bottleneck.

3. **Autonomous fix loops optimize for "tests pass," which is not "correct."**
   A loop told to iterate until green will, given enough retries, find the
   shortest path to green — which sometimes means weakening an assertion,
   `xfail`-ing a test, or special-casing the fixture. The thing keeping this
   project honest is the **no-regression rule** (a fix may not break a
   previously-passing test) and a *human reading the diff*. A 5-iteration
   auto-loop with a human-escalation fallback is just a CI gate with extra steps
   and a worse failure mode — it can burn four iterations gaming the check before
   it ever asks for help.

4. **It contradicts the architecture I already chose.** This codebase uses an
   LLM for exactly the two steps that are irreducibly semantic — *match scoring*
   and *hallucination detection* (§3: "Discovery is a tool, not an agent; source
   trust is a config list, not an agent"). Lint and test verdicts are no more
   semantic than an HTTP call. Promoting them to agents would be the same mistake
   as turning the source allowlist into an agent.

**When the agent loop *is* right:** the checker is fuzzy (e.g. "is this prose
on-brand," "does this UI look broken" — judgments with no deterministic oracle),
the iterations are cheap relative to a human's time, or the loop runs unattended
where there's no human to read the diff. None of those hold for *lint + unit
tests on a small repo*. The honest version of "agentic CI" for this project is:
deterministic gate runs the checks, a human (or a single coding-agent turn) reads
the report and writes the fix, the no-regression rule and the diff review are the
real guardrails. That's `check.sh`.

The general principle: **reach for an agent when the judgment is irreducible, not
when a deterministic tool already decides the question.** Spending a model call to
interpret a `pytest` exit code is the over-engineering tell.

## 10. Production notes (deliberate v1 simplifications)

- **SQLite -> Postgres:** v1 uses SQLite on purpose. True production (many orgs,
  concurrent caseworkers, audit trail) would move to Postgres + Alembic
  migrations, add row-level tenancy, and put agent runs behind a job queue.
  Named here so the simplification reads as intent, not ignorance.
- **Curated sources are solar-only, and don't scale by hand:** v1 hand-curates
  ~10–15 solar/clean-energy sources in `app/sources.yaml`. Covering every
  nonprofit category this way is a data-operations problem, not an engineering
  one — so it's out of scope. Production would replace hand-curation with a
  scheduled agent that discovers and monitors foundation/state sources per
  domain and cross-checks their claims. Until then, off-solar profiles rely on
  the live federal (grants.gov) search.
- **Out of scope (v1):** automatic submission, scraping arbitrary
  jurisdictions, multi-user auth/tenancy, a rich SPA frontend.
