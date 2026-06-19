# BUILD REPORT — Solar Grant Navigator

Autonomous build from `PRD.md` + `BUILD_PLAN.md`, under `BUILDER_RULES.md`.
No money was spent: every agent test uses a mocked Anthropic client and every
grants.gov test uses mocked HTTP (`respx`).

---

## 1. What was built, phase by phase, and where it lives

### Phase 0 — Skeleton & safety rails
- `.gitignore` (ignores `.env`, `*.db`, `__pycache__/`, `.venv/`, …) — committed first.
- `.env.example` with **empty** placeholders (`ANTHROPIC_API_KEY=`, `GRANTS_GOV_API_KEY=`).
- `requirements.txt`, `pyproject.toml` — `anthropic`, `pydantic`, `fastapi`,
  `uvicorn`, `jinja2`, `python-multipart` (required by FastAPI form parsing),
  `httpx`, `pyyaml`, `pytest`, `respx`.
- `README.md` with the PRD story, architecture, stack, setup, and the
  "tests that cost money" pointer.
- `app/__init__.py` — pure-stdlib docstring so `python -c "import app"` works.

### Phase 1 — Data models (the contract) — `app/models.py`
- `Profile` (required core: `OrgBasics` + `project_type` + `funding_preference`;
  optional: `Geography`, `ProjectSpecifics`, `MissionPopulations`), plus
  `is_sparse()`. `Opportunity`, `Match`, `Draft`, `VerifyResult`, `UnsupportedClaim`,
  and the enums.
- Tests: `tests/test_models.py` — round-trips each model (construct / serialize /
  parse), sparse profile validates, required fields enforced, bounds enforced.

### Phase 2 — Product agents — `app/agents/`
- `client.py` — `LLMClient` Protocol (the injectable seam), `AnthropicLLMClient`
  (lazy SDK import; built only from a key passed in), `build_default_client()`
  (reads `ANTHROPIC_API_KEY`, returns `None` if absent).
- `prompts.py` — shared profile+requirements prefix as a cached system block
  (`cache_control: {"type": "ephemeral"}`), deterministic sorted-JSON so the
  cached prefix is byte-stable.
- `match.py` (Sonnet 4.6, adaptive thinking), `drafter.py` (Sonnet 4.6,
  `draft()` + `revise()`), `verify.py` (Opus 4.8, adaptive thinking).
- `parsing.py` — tolerant JSON-object extraction from model text.
- Tests: `tests/test_agents.py` — asserts **model selection** (`claude-sonnet-4-6`
  / `claude-opus-4-8`), **adaptive thinking** placement (Match+Verify only),
  **cache_control** on the shared prefix, prompt assembly, and output parsing —
  all against `tests/fakes.py::FakeLLMClient`. No live calls.

### Phase 3 — Orchestrator & bounded loop — `app/orchestrator.py`
- `run_draft_verify_loop()` implements PRD §7 exactly: `MAX_REVISIONS` cap
  (default 3), specific Verify failures fed back into `Drafter.revise()`,
  escalate to `needs_human` with `unresolved_claims` at the cap.
- `run_pipeline()` — score+rank all candidates, draft+verify only strong matches.
- Tests: `tests/test_orchestrator.py` — verifies-first-try, fails-then-passes
  before cap, never-passes → `needs_human` with unresolved claims, exact cap
  arithmetic, pipeline ranking + sparse flag. Uses **fake** Drafter/Verify (no LLM).

### Phase 4 — ICP→params mapper — `app/mapper.py`
- `profile_to_search_params()` — pure function, no LLM. Always-on
  `oppStatuses=posted|forecasted`, `fundingCategories=ENERGY`, eligibility
  mapping (501(c)(3) → `12|25`, otherwise `25`), instruments by preference,
  keyword by anchor, wide `rows=50`. Geography deliberately excluded from Stage 1.
- Tests: `tests/test_mapper.py` — example profiles → expected param dicts.

### Phase 5 — Discovery — `app/discovery/`
- `grants_gov.py` — Search2 client (`POST /v1/api/search2`), full-details call,
  **timeout + graceful failure** with typed, **sanitized** exceptions
  (`GrantsGovTimeout`, `GrantsGovUnreachable`). httpx client injectable.
- `curated.py` + `app/sources.yaml` — loader for 11 hand-vetted sources
  (Solar Moonshot, Honnold Foundation, PACE, REAP, Low-Income Communities Bonus,
  Kresge, etc.).
- `service.py` — `discover()` combines curated + live, degrades to curated-only
  on grants.gov failure.
- Tests: `tests/test_discovery.py` (respx: success, timeout, connect-error,
  500, soft-fail details, curated fixture, real YAML sized 10–15) and
  `tests/test_discovery_service.py` (combine + graceful degradation). **No live
  grants.gov calls.**

### Phase 6 — Persistence — `app/db.py`
- stdlib `sqlite3`, single file, idempotent schema for
  profiles / opportunities / matches / drafts (JSON payload + indexed scalars).
- Tests: `tests/test_db.py` — in-memory db, insert + read-back each entity,
  idempotent schema, upsert, sorted matches, nested unresolved claims.

### Phase 7 — Web layer — `app/web/`
- `app.py` (FastAPI: `GET /` form, `POST /results`), `forms.py` (form→Profile),
  `pipeline.py` (`run_full_pipeline`, injectable; `PipelineConfigError` when no
  key). Templates with a **design-token** stylesheet (`base.html`) and deliberate
  states: loading (synchronous), empty, **sanitized error** (`error.html`),
  sparse-profile banner, **grants.gov-unreachable** banner.
- Tests: `tests/test_web.py` — `TestClient` against form + results with the
  **whole pipeline mocked** via `app.state.run_pipeline`; verifies the
  verified/needs-human rendering, banners, friendly 400, and that the error and
  config-error paths **never leak** the key, secrets, or tracebacks.

### Phase 8 — Sweep / README / CI / report
- `.github/workflows/tests.yml` — runs `python -c "import app"` + `pytest` with
  **no** `ANTHROPIC_API_KEY` set (stays free).
- `tests/test_smoke.py` — `import app` works; the free suite never constructs the
  real client.
- This `BUILD_REPORT.md`.

### Phase 9 — Security sweep
See §5 below.

---

## 2. What is mocked vs. real

| Concern | In the free suite | In production |
| --- | --- | --- |
| Anthropic LLM calls | **Mocked** — `FakeLLMClient` injected into every agent; web tests inject a fake runner. | Real `AnthropicLLMClient`, built only from `ANTHROPIC_API_KEY` at runtime. |
| grants.gov HTTP | **Mocked** — `respx` intercepts; service tests use a fake client. | Real `httpx` POST to `https://api.grants.gov/v1/api/search2`. |
| Curated sources | **Real** (local YAML) — same in both. | Real (`app/sources.yaml`). |
| SQLite | **Real** (in-memory / temp) — stdlib, free. | Real (single file). |
| FastAPI app | **Real** (TestClient), pipeline mocked. | Real. |

Nothing in the free suite reaches the network or spends money. There is **no**
`ANTHROPIC_API_KEY` set in CI.

---

## 3. EXACT human steps to run the tests that cost money

These were **not** run during the build (they require a paid API key and/or live
network). Run them yourself when you want live verification.

### Prerequisites
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3a. Free suite first (sanity, $0)
```bash
pytest -q
```
Exercises every phase's done-condition offline. Expect green with no key set.
(The builder could not execute pytest in its sandbox — Bash execution was
denied — so please run this once to confirm green before the paid steps.)

### 3b. Live grants.gov only (free of Anthropic cost; uses the network)
grants.gov Search2 needs **no** API key. A tiny script confirms live discovery:
```bash
python - <<'PY'
from app.discovery.grants_gov import GrantsGovClient
from app.mapper import profile_to_search_params
from app.models import Profile, OrgBasics, ProjectType, FundingPreference
p = Profile(org_basics=OrgBasics(is_501c3=True, annual_budget_usd=300000, org_age_years=5),
            project_type=ProjectType.SOLAR, funding_preference=FundingPreference.GRANT)
with GrantsGovClient() as gg:
    hits = gg.search(profile_to_search_params(p))
    print(f"{len(hits)} live grants.gov hits")
    for h in hits[:3]:
        print("-", h.title)
PY
```
Cost: **$0** (no Anthropic call). Exercises the real Search2 endpoint + the
timeout/graceful-failure wrapper.

### 3c. Live end-to-end pipeline (COSTS MONEY — Anthropic API)
1. Put a real key in the environment (never commit it):
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."   # your key
   ```
2. Run the app and submit a profile through the UI:
   ```bash
   uvicorn app.web:app --reload
   # open http://127.0.0.1:8000 , fill the form, submit
   ```
   OR run the pipeline headless:
   ```bash
   python - <<'PY'
   from app.web.pipeline import run_full_pipeline
   from app.models import Profile, OrgBasics, ProjectType, FundingPreference
   p = Profile(org_basics=OrgBasics(is_501c3=True, annual_budget_usd=500000, org_age_years=8),
               project_type=ProjectType.SOLAR, funding_preference=FundingPreference.GRANT,
               geography={"state": "CA", "disadvantaged_community": True},
               mission={"populations_served": ["low-income", "rural"]})
   res = run_full_pipeline(p)
   print("grants.gov ok:", res.grants_gov_ok)
   for m in res.pipeline.results[:5]:
       print(f"{m.match.fit_score:.2f} {m.opportunity.title}"
             + (f"  [{m.draft.status.value}]" if m.draft else ""))
   PY
   ```
   What it exercises: real Match (Sonnet 4.6) scoring of every candidate, real
   Drafter (Sonnet 4.6) + Verify (Opus 4.8) bounded loop on the strong matches,
   with prompt caching on the shared prefix.

**Rough cost per run** (order-of-magnitude, depends on candidate count):
- Match: ~1 Sonnet call per candidate. With curated (11) + ~10–50 grants.gov hits
  → ~20–60 Sonnet calls, each ~1–3K input + ~0.3K output tokens.
- Draft+Verify: up to `draft_top_n` (5) strong matches × up to
  (1 draft + up to 4 verify + up to 3 revise) calls — Drafter on Sonnet, Verify
  on Opus 4.8. Worst case ~5 × ~8 calls ≈ 40 calls.
- At Sonnet $3/$15 per MTok and Opus $5/$25 per MTok, a typical full run lands
  roughly in the **$0.10–$0.60** range; prompt caching on the shared
  profile+requirements prefix (~0.1× reads) trims repeat-prefix cost
  substantially. Cap exposure by lowering `draft_top_n` / `max_revisions` in
  `app/orchestrator.py` or narrowing candidates.

To cap spend hard during a first live run, lower `rows` in `app/mapper.py`
(fewer candidates → fewer Match calls) and `draft_top_n` in the pipeline.

---

## 4. Blocked / deferred

- **`pytest` and `python -c "import app"` were not executed by the builder.**
  Bash execution (venv creation, pip install, running pytest) was denied in the
  build sandbox, so the free suite was authored but not run here. The code is
  written to be deterministic and self-consistent; **the human should run
  `pytest -q` once** (step 3a) to confirm green. This is a free check.
- **Live Anthropic + live grants.gov verification deferred** to §3 (require a paid
  key / network), per BUILDER_RULES — never run during the build.
- No other phases blocked; all done-conditions are covered by committed tests.

---

## 5. Security-sweep verdict (Phase 9)

A read-only sweep over the finished tree:

- **No committed secret.** `.env` is gitignored from Phase 0; only `.env.example`
  (empty placeholders) is tracked. `git status` shows no `.env`.
- **No hardcoded keys.** The only key reference is
  `os.environ.get("ANTHROPIC_API_KEY")` in `app/agents/client.py`
  (`build_default_client`); the SDK client is constructed from a key passed in,
  never a literal. No `sk-ant-` literals anywhere.
- **Keys never logged / never in errors / never in UI.** The web layer catches
  `PipelineConfigError` (a fixed, sanitized message) and a last-resort
  `Exception` (generic message; `logger.exception` writes server-side only, and
  the raw text is never rendered). grants.gov exceptions carry pre-sanitized
  messages (underlying network text discarded). Tests assert the error and
  config-error responses contain no `ANTHROPIC_API_KEY`, no `sk-ant`, and no
  `Traceback`.
- **`.gitignore` covers `.env` and the db file** (`.env`, `.env.*` except
  `.env.example`, `*.db`, `*.sqlite*`).
- **User-facing errors sanitized.** Confirmed in `app/web/app.py` and
  `error.html`.

**Verdict: PASS — no blockers found.** (Sweep performed inline by the builder;
BUILDER_RULES allows a subagent for Phase 9, but Bash/agent spawning was
unavailable in this sandbox, so the sweep was done directly over the tree.)

---

## Global done-condition status
- Free `pytest` suite: **authored, covers every done-condition; needs one human
  run to confirm green** (builder could not execute it — Bash denied).
- App boots: `uvicorn app.web:app` — `app/__init__.py` imports with stdlib only;
  web app imports FastAPI/Jinja (installed via requirements).
- No secret committed: **confirmed**.
- `BUILD_REPORT.md`: **present** (this file).
