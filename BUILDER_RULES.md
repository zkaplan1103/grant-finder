# Builder Rules — operating constraints for the autonomous build

The background builder agent follows these rules while executing `BUILD_PLAN.md`
from `PRD.md`, unsupervised. These are hard constraints, not suggestions.

## Money & API keys (non-negotiable)
- **Run NO test or check that spends money.** No live calls to the Anthropic API
  or any paid endpoint during the build. Every agent/LLM test uses a **mocked
  client**; every grants.gov test uses **mocked HTTP** (`respx`).
- The real Anthropic client is constructed only from `ANTHROPIC_API_KEY` in the
  environment, at runtime — never hardcoded, never in a committed file.
- **Never commit a secret.** `.env` is gitignored from Phase 0. If a key is
  needed to *verify* something, do NOT verify it — defer it to `BUILD_REPORT.md`
  as a human step.
- Keys must never be logged, echoed in errors, or rendered in UI error states.
  Error output shown to users is sanitized.

## Autonomy & stopping
- Full auto: execute phases in order; do not pause for approval between phases.
- Each phase's **done-condition must pass (free checks only)** before starting
  the next.
- Stop and report only when: the global done-condition is met, OR genuinely
  blocked (a phase's done-condition can't be met without a paid call or a
  human decision). On block, record it in `BUILD_REPORT.md` and continue with
  any phases that don't depend on the blocker.

## Loop hygiene (keep the builder's context clean over a long run)
- **3-strikes-clear:** if a single problem (a phase's done-condition, a failing
  test, a stubborn bug) resists **3 attempts**, the attempt context is poisoned
  by the failures. Stop grinding: clear/compact the context, restate the phase
  contract from `BUILD_PLAN.md` + `PRD.md` fresh, and retry **once** clean. Still
  stuck → log it to `BUILD_REPORT.md` and move on to the next phase that doesn't
  depend on the blocker.
- **40% compaction:** when context usage passes ~40% of the window, compact
  proactively (SDK server-side compaction) rather than letting it grow. Late-run
  context bloat degrades output quality; a long autonomous build should run lean.
- Architecture is fixed (one orchestrator + the phases as contracts). Spawn a
  subagent **only** for the final security sweep (Phase 9) — it is independent,
  read-only, and returns a short verdict. Do not spawn per-phase subagents for
  coupled, sequential work; the main builder does those inline.

## Scope discipline (ponytail)
- Build exactly what `PRD.md` and `BUILD_PLAN.md` specify. No speculative
  abstractions, no extra agents, no framework where stdlib/SDK suffices.
- Stack is fixed by PRD §8: `anthropic` SDK + manual loop, Pydantic, SQLite
  (stdlib), FastAPI + Jinja (no SPA). Do not add LangGraph/CrewAI, an ORM, or
  Postgres.
- Mark deliberate simplifications with `# ponytail:` comments naming the ceiling.

## Testing
- Non-trivial logic leaves a runnable check behind: the bounded loop, the
  ICP→params mapper, discovery's graceful-failure paths, model validation.
- All tests must run **free** (mocked LLM + mocked HTTP). The free suite is the
  gate between phases.
- Name edge cases explicitly: loop hits the cap, grants.gov times out / is
  unreachable, sparse profile, Verify finds nothing vs. finds holdouts.

## Git
- Work in the assigned worktree. Commit per phase with a clear message.
- Do **not** push to the remote — leave pushing to the human.

## Final report (`BUILD_REPORT.md`)
At the end, write a report containing:
1. What was built, phase by phase, and where each piece lives.
2. What is mocked vs. real.
3. **Exact human steps to run the paid tests**: which env vars to set
   (`ANTHROPIC_API_KEY`), which commands, what they exercise, and a rough cost
   estimate per run.
4. Anything blocked or deferred, and why.
