# Build Plan — Solar Grant Navigator (autonomous)

This is the ordered plan the background builder agent executes from `PRD.md`,
unsupervised. Each phase has a **done-condition** that must pass (with free
checks only — see `BUILDER_RULES.md`) before the next phase starts.

Source of truth for *what* to build is `PRD.md`. This file is the *order* and
the *done-conditions*.

---

## Phase 0 — Project skeleton & safety rails
- `.gitignore` first (`.env`, `*.db`, `__pycache__/`, `.venv/`, etc.).
- `.env.example` with empty placeholders: `ANTHROPIC_API_KEY=`, grants.gov key
  if any. **Never** a real key. No `.env` committed, ever.
- `pyproject.toml` / `requirements.txt`: `anthropic`, `pydantic`, `fastapi`,
  `uvicorn`, `jinja2`, `httpx`, `pytest`, `respx` (HTTP mocking).
- `README.md` skeleton with the PRD's story sections stubbed.
- **Done:** repo installs in a fresh venv; `python -c "import app"` works.

## Phase 1 — Data models (the contract)
- Pydantic models: `Profile` (required core + optional context per PRD §5),
  `Opportunity`, `Match`, `Draft`, `VerifyResult`.
- Profile models the required/optional split and validates required fields.
- **Done:** `pytest` round-trips each model (construct, serialize, parse); a
  sparse profile (only required fields) validates.

## Phase 2 — Product agents (Match / Draft / Verify)
- One module per agent under `app/agents/`. Each: system prompt, Anthropic SDK
  call, structured-output parsing into the Phase-1 models.
- Models per PRD §8: Sonnet 4.6 for Match + Draft, Opus 4.8 for Verify.
  `thinking={"type":"adaptive"}` on Match + Verify.
- Prompt caching (`cache_control: ephemeral`) on the shared profile+requirements
  prefix.
- **The agent call layer is injectable** so tests can substitute a fake client
  (no live calls). Real client only when an API key is present at runtime.
- **Done:** each agent unit-tested against a **mocked** Anthropic client
  asserting prompt assembly, model selection, and output parsing. No live calls.

## Phase 3 — Orchestrator & the bounded Drafter⇄Verify loop
- Implement the loop from PRD §7: `MAX_REVISIONS` cap, specific-failure
  feedback, escalate-to-human on holdouts.
- **Done:** loop unit-tested with a **fake** Drafter/Verify (no LLM):
  - verifies first try → returns `verified`;
  - fails then passes → returns `verified` after N<cap revisions;
  - never passes → returns `needs_human` with unresolved claims at the cap.

## Phase 4 — ICP→params mapper (deterministic)
- Map required profile fields → grants.gov Search2 coarse params (PRD §4, §9).
  Wide-net, high-recall. Pure function, no LLM.
- **Done:** `pytest` over example profiles → expected param dicts, incl. always-on
  `oppStatuses=posted|forecasted` and the org-basics eligibility mapping.

## Phase 5 — Discovery (grants.gov live + curated sources)
- grants.gov Search2 client (`httpx`), **timeout + graceful failure** (PRD §9).
  Second call for full opportunity details on candidates.
- Curated-sources loader: `sources.yaml` (~10–15 entries: name, eligibility
  notes, URL, typical award, deadline). Seed with the real ones from planning
  (Solar Moonshot, Honnold, PACE, etc.).
- **Done:** grants.gov client tested with **mocked HTTP** (`respx`) for success,
  timeout, and unreachable → graceful degradation. Curated loader tested against
  a fixture YAML. **No live grants.gov calls in tests.**

## Phase 6 — Persistence (SQLite, stdlib)
- `sqlite3`, single file, schema for profiles / opportunities / matches / drafts.
  No ORM, no migration framework.
- **Done:** `pytest` against an in-memory/temp SQLite db: insert + read back each
  entity; schema creates idempotently.

## Phase 7 — Web layer (FastAPI + Jinja) + design pass
- Design-system pass first: tokens (color/type/spacing), then build.
- Routes: profile form (required + optional sections), submit → pipeline →
  results page with ranked matches + drafts + flagged items.
- Deliberate states: loading, empty, **sanitized error** (never leak keys/
  internals), and "grants.gov unreachable."
- **Done:** app boots; `pytest` with FastAPI `TestClient` hits the form and a
  results route with the **whole pipeline mocked** (no live calls); error state
  renders without leaking internals.

## Phase 8 — Tests sweep, README, final report
- Ensure free test suite is green end-to-end; wire a GitHub Actions workflow that
  runs only the free suite.
- Fill in README: the PRD story, architecture, the SQLite/Postgres judgment call,
  and a **"Running tests that cost money"** section.
- **Done:** `pytest` green (free suite); `BUILD_REPORT.md` written listing exactly
  what was built, what's mocked, and the precise human steps to run the paid
  tests (set `ANTHROPIC_API_KEY`, which commands, est. cost).

## Phase 9 — Security sweep (subagent)
- Spawn one read-only subagent over the finished tree. Independent, returns a
  short verdict — the one place a subagent earns its cold start.
- Checks: no committed secret anywhere (`.env` absent from git, no hardcoded
  keys, no key in any file); keys never logged or rendered in error/UI paths;
  `.gitignore` covers `.env` and the db file; error output to users is sanitized.
- **Done:** verdict written to `BUILD_REPORT.md`. Any finding is a hard blocker —
  fix before declaring the global done-condition met.

---

## Global done-condition
Free `pytest` suite green, app boots, no secret committed, `BUILD_REPORT.md`
present. Then stop and report back.
