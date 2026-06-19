# Solar Grant Navigator

A multi-agent system that takes a nonprofit's profile and produces a ranked,
cited set of funding matches with drafted application boilerplate — with a
verification step that refuses to let unsupported claims into a draft.

## 1. Problem & why it matters

Soft costs make up ~65% of residential solar installation cost; for the
nonprofits helping low-income households go solar, the hardest soft cost is
**finding and winning funding**. After the EPA cancelled **Solar for All** in
August 2025, community organizations are scrambling to replace the money from a
fragmented field of federal grants, foundations, and state programs. A
caseworker doing this by hand juggles grants.gov, a dozen foundation sites, and
a spreadsheet, then hand-writes eligibility summaries. It is slow and
error-prone, and a single fabricated eligibility claim can get an org barred.

## 2. What it does

Single org profile in → ranked funding matches (live federal + curated
foundation/state sources) + drafted boilerplate out, each match cited and
fit-reasoned. Strong matches get boilerplate that has passed a Drafter⇄Verify
loop, or is flagged with the specific unsupported claims for human review.

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
migration framework), FastAPI + Jinja server-rendered HTML (no SPA).

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
```

Run the web app:

```bash
uvicorn app.web:app --reload
```

The app boots without an API key; running the live pipeline needs
`ANTHROPIC_API_KEY` in the environment.

## 6. Tests (free)

The whole suite runs offline — the Anthropic client is mocked and grants.gov
HTTP is mocked with `respx`. No money is spent.

```bash
pytest
```

## 7. Running tests that cost money

See `BUILD_REPORT.md` for the exact env vars, commands, and cost estimates for
the optional live end-to-end checks against the real Anthropic API and the live
grants.gov endpoint.

## 8. Production notes (deliberate v1 simplifications)

- **SQLite -> Postgres:** v1 uses SQLite on purpose. True production (many orgs,
  concurrent caseworkers, audit trail) would move to Postgres + Alembic
  migrations, add row-level tenancy, and put agent runs behind a job queue.
  Named here so the simplification reads as intent, not ignorance.
- **Curated sources -> maintained pipeline:** v1 hand-curates ~10–15 sources in
  `app/sources.yaml`. Production would add a scheduled agent to monitor known
  sources for changes and cross-check claims.
- **Out of scope (v1):** automatic submission, scraping arbitrary
  jurisdictions, multi-user auth/tenancy, a rich SPA frontend.
