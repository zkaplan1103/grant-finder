# Grant Navigator — Project Context (for UI work)

## What it is
A multi-agent web app: a nonprofit enters its profile, and the app returns
**ranked federal/foundation funding matches** with **drafted application
boilerplate**, each match scored for fit and run through a **hallucination-check
("Verify") step** before any draft is shown. The trust layer (catching
fabricated claims) is the project's headline feature.

## Stack the UI lives in
- **Frontend:** React + TypeScript + Tailwind, built with **Vite**, in
  `frontend/`. Currently a **3-step wizard** with a glassmorphic design.
- **Backend:** FastAPI. The built SPA (`frontend/dist`) is served at `/`; the
  API is at `/api`.
- **Dev mode:** `uvicorn app.web:app --reload --port 8000` (terminal 1) +
  `npm run dev` in `frontend/` (terminal 2, port 5173, proxies `/api` → 8000).
- API types the UI consumes live in `frontend/src/lib/api.ts`.

## The data contract (what the UI renders)
- **Input:** a `Profile` — required core (`is_501c3`, `annual_budget_usd`,
  `org_age_years`, free-text `project_type`, `funding_preference`) + optional
  context (geography, project specifics, mission/populations). Sparse profiles
  are valid.
- **Endpoint:** `POST /api/match` → returns a ranked list of matched
  opportunities.
- **Each result has:** `fit_score` (0–1), `reasoning`, `low_confidence` flag,
  `caveats[]`, and (for strong matches) a `draft` with `eligibility_summary` +
  `boilerplate`, a `status` (`draft` / `verified` / `needs_human`), and
  `unresolved_claims[]` when escalated.

## What just changed (relevant to UI)
- **Match threshold:** the backend now hides matches below **0.5 fit** by
  default. There's a `min_display_score` knob (0 = show everything). **UI need:**
  a toggle/slider to "show weaker matches (<50%)" — not built yet, open frontend
  work.
- Backend reliability + linting cleanup happened, but no UI-visible changes
  there.

## Where it's going (so UI decisions age well)
- **Phase 1 (now):** polish into a defensible portfolio piece — an **eval
  harness** measuring the Verify agent's hallucination-catching
  (precision/recall), a **live deploy** (Railway), and a README rewrite. UI-wise
  this means the **trust/verification story should be visually prominent** —
  surfacing *why* a draft is trustworthy (verified status, flagged claims,
  confidence/caveats) is the differentiator, not just the match list.
- **Phase 2 (background):** evolve toward a **"nonprofit ops dashboard"** — run
  history, the verification/eval metrics, traces. So the UI should be able to
  grow from "one-shot wizard → results" into a dashboard shell with persistent
  runs. Design the results view as something that could live inside a dashboard
  later, not a dead-end page.

## UI priorities to consider
1. **Surface trust:** make `status` (verified / needs_human), `low_confidence`,
   `caveats`, and `unresolved_claims` first-class in the results UI — this is the
   product's whole point.
2. **The <50% toggle** for weak matches.
3. **Results view that scales** toward a dashboard (Phase 2), not just a wizard
   endpoint.
