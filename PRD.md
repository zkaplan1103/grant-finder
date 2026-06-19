# Solar Grant Navigator — PRD

## 1. Problem & why it matters

Soft costs (permitting, customer acquisition, financing) make up roughly 65% of
residential solar installation cost. For the nonprofits that help low-income
households and community organizations go solar, the hardest soft cost is
**finding and winning funding** — and that landscape just got worse.

In August 2025 the EPA cancelled the **Solar for All** program, which had funded
low-cost solar for low-income residents in all 50 states. That left community
organizations scrambling to replace the money from a fragmented field of federal
grants, private foundations, and state programs — each with different
eligibility rules, deadlines, and application formats.

A nonprofit caseworker doing this today juggles grants.gov, a dozen foundation
websites, and a spreadsheet of state programs, then hand-writes eligibility
summaries and boilerplate for each application. It's slow, error-prone, and the
information goes stale constantly.

**Solar Grant Navigator** is a multi-agent system that takes a nonprofit's
profile and produces a ranked, cited set of funding matches with drafted
application boilerplate — with a verification step that refuses to let
unsupported claims into a draft, because a fabricated eligibility claim can get
an organization barred.

## 2. User

**Primary user:** a nonprofit caseworker, working one organization profile at a
time. They run the tool repeatedly across many client orgs, need consistent and
trustworthy output, and lose trust permanently the first time the tool states a
confident wrong fact.

Not built for: the general public, multi-tenant SaaS use, or fully autonomous
submission. A human reviews and submits.

## 3. Scope

### In scope (v1)
- Single-org profile in, ranked funding matches + drafted boilerplate out.
- Live federal grant discovery via the grants.gov Search2 API.
- Curated config of ~10–15 hand-verified high-value foundation/state sources
  (Solar Moonshot, Honnold Foundation, PACE programs, etc.).
- Three agents: Match (fit scoring), Drafter (boilerplate), Verify (claim check).
- A bounded Drafter⇄Verify revision loop with human escalation.
- A thin FastAPI + Jinja web UI: one profile form, one results page.
- SQLite persistence (profiles, opportunities, matches, drafts).

### Out of scope (v1) — named, not forgotten
- Automatic application submission.
- Scraping arbitrary jurisdictions / the full 20k-AHJ permitting problem.
- Multi-user auth, tenancy, audit trails (see §10 production notes).
- A rich SPA frontend.

## 4. The core design insight: search is wide & dumb, matching is narrow & smart

grants.gov's filters are coarse, code-based, and its search response is thin
(title, agency, dates, status, ALN — not full eligibility text). The nonprofit
ICP is rich and semantic. These cannot be reconciled in one query, so discovery
and matching are two stages:

- **Stage 1 — retrieval (deterministic code, high recall):** map structured ICP
  fields to grants.gov's coarse filters to pull a deliberately *wide* candidate
  set. No LLM. Reproducible.
- **Stage 2 — fit scoring (the Match agent, high precision):** fetch full
  details for each candidate, then reason about true fit (geography, mission,
  project specifics) against the rich ICP, and rank.

This mirrors how caseworkers actually work: filter broad on eligibility, then
*read* for fit.

## 5. The ICP / nonprofit profile

Modeled on how caseworkers actually search: start from who the org *is*
(eligibility gate), then judge fit by reading.

### Required (drives the Stage-1 search)
- **Org basics:** 501(c)(3) status, annual budget size, org age.
- **Funding anchor:** broad project type (solar/clean-energy) + grant-vs-loan
  preference. Without this there is no category to search.

### Optional (enriches Stage-2 Match scoring; blank is acceptable)
- **Geography:** state, service area, disadvantaged-community status.
- **Project specifics:** type (rooftop/community), size, cost, stage, amount needed.
- **Mission & populations served:** mission statement, populations (low-income,
  tribal, rural, …).

**Graceful degradation:** the Match agent uses whatever is filled in. Sparse
profile → wider, lower-confidence matches, and the output must *say so*
("ranked on limited info; add geography for better fit").

## 6. Architecture

```
Profile (required core + optional context)
   │
   ▼
ICP→params mapper ............... deterministic code, org-basics-driven, wide net
   │
   ▼
Discovery ....................... live grants.gov Search2  +  curated YAML sources
   │  (fetch full details for candidate opportunities)
   ▼
Match agent (Sonnet) ........... semantic fit scoring over rich ICP; ranks; degrades gracefully
   │
   ▼
Drafter (Sonnet)  ⇄  Verify (Opus)   bounded loop (max_revisions), escalate holdouts to human
   │
   ▼
Human review of flagged items → report
```

Three agents, each owning a distinct hard sub-problem. Discovery is a **tool**,
not an agent. Source trust is a **config list** (vetted at design time), not an
agent.

### Agent responsibilities
- **Match (Sonnet 4.6):** given the full ICP and a candidate opportunity's full
  details, score fit and explain why. Ranks the candidate set. Flags low
  confidence on sparse profiles.
- **Drafter (Sonnet 4.6):** given a strong match, draft the eligibility summary
  and application boilerplate (org description, need statement, etc.).
- **Verify (Opus 4.8):** check every factual claim in a draft against the
  profile + the grant's stated requirements. Return specific unsupported claims.
  This is the trust guarantee; it runs on the strongest model because a cheap
  model silently waves through hallucinations.

## 7. The Drafter ⇄ Verify loop

```
draft = Drafter(match, profile)
for i in range(MAX_REVISIONS):          # hard ceiling, non-negotiable
    failures = Verify(draft, profile, requirements)
    if not failures:
        return draft, status="verified"
    draft = Drafter.revise(draft, failures)   # specific failures fed back
# loop exhausted
return draft, status="needs_human", unresolved=failures
```

- **Bounded:** `MAX_REVISIONS` cap (default 2–3). Two LLMs revising each other
  can ping-pong forever; the cap is the upgrade path's known ceiling.
- **Specific feedback:** Verify returns *which* claims failed and why, not a
  thumbs-down. The Drafter revises against those specifics.
- **Escalation, not silent failure:** anything still unsupported after the cap
  is flagged to the human with the reason. Not "give up after one try."

## 8. Stack & key technical decisions

- **Python**, official `anthropic` SDK, **manual agentic loop** (own the
  Drafter⇄Verify loop and `MAX_REVISIONS` cap rather than hand it to a framework).
- **Models:** Sonnet 4.6 (`claude-sonnet-4-6`) for Match + Draft (volume work);
  Opus 4.8 (`claude-opus-4-8`) for Verify (the safety check). Cost/capability
  reasoned per-agent, not defaulted to the most expensive model everywhere.
- **Thinking:** `thinking={"type": "adaptive"}` on the reasoning-heavy agents
  (Match, Verify). No `budget_tokens` (400s on these models).
- **Prompt caching:** the shared profile + grant-requirements prefix is
  identical across agents and across every Drafter⇄Verify iteration. Cache it
  with `cache_control: {"type": "ephemeral"}`; reads are ~0.1× cost.
- **Persistence:** SQLite, stdlib `sqlite3`, single file. No ORM, no migrations
  framework, no Postgres. Real relational queries, zero setup, scales past any
  single-caseworker load.
- **Web:** FastAPI + Jinja server-rendered HTML. No SPA, no frontend build.
- **No agent framework** (LangGraph/CrewAI): 3 agents + 1 loop don't justify the
  dependency, and the loop is the part worth owning.

## 9. Discovery sources

- **Spine:** grants.gov **Search2** API (`POST /v1/api/search2`, no auth for
  basic search). Coarse filters: `keyword`, `eligibilities`, `fundingCategories`,
  `fundingInstruments`, `oppStatuses`, `agencies`, `aln`, `rows`, pagination.
  Thin response → second call (Get Full Opportunity Details) for candidates.
  **Wrap with timeout + graceful failure** — a live demo that hangs or
  stack-traces is worse than no demo.
- **Curated:** a YAML file of ~10–15 vetted foundation/state sources
  (name, eligibility notes, URL, typical award, deadline). This is what a real
  caseworker keeps in a spreadsheet — not the scrape-everything trap. The agents
  reason over grants.gov hits and curated entries identically.

Rationale: grants.gov alone covers only ~1/3 of real solar-nonprofit funding,
and not the most mission-relevant third. The curated list closes the gap
honestly without unbounded scraping.

## 10. Production notes (documented judgment calls for the README)

- **SQLite → Postgres:** v1 uses SQLite deliberately. For true production
  (multiple orgs, concurrent caseworkers, audit trail), move to Postgres +
  Alembic migrations, add row-level tenancy, put agent runs behind a job queue.
  Named here so the simplification reads as intent, not ignorance.
- **Curated sources → maintained pipeline:** v1 hand-curates ~10–15 sources.
  Production would add a scheduled agent to monitor known sources for changes and
  cross-check claims (the "Incentive Watchdog" direction).

## 11. Success criteria (v1)
- A caseworker enters a profile and gets a ranked, cited list of real funding
  matches (federal + curated) with per-match fit reasoning.
- Each strong match has drafted boilerplate that has passed the Verify loop, or
  is flagged with specific unsupported claims for human review.
- No draft reaches the human containing a fabricated eligibility claim that
  contradicts the profile or the grant's requirements.
- Runs end-to-end against the live grants.gov API; degrades gracefully when it's
  unreachable and when the profile is sparse.
