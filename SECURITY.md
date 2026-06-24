# Security & Threat Model

Grant Navigator is a **public, unauthenticated portfolio demo** with one
expensive operation: `POST /api/match` (and its SSE twin `/api/match/stream`)
runs real Anthropic model calls. The threat model is scoped to that reality — it
defends the things a public LLM demo actually faces and deliberately skips
controls that would be theater for an app with no accounts and no user data.

## Assets worth protecting

1. **The Anthropic API key** — leaking it lets someone spend your money directly.
2. **Your Anthropic spend** — even without leaking the key, an attacker can run up
   a bill by hammering the expensive endpoint (cost-amplification).
3. **Availability** — the demo staying responsive (a distant third; it's a demo).

There is **no user data, no accounts, no database of secrets** — so the usual
web-app asset (a user table) doesn't exist here. That shapes everything below.

## Threats & mitigations

| # | Threat | Mitigation | Where |
|---|--------|-----------|-------|
| 1 | **Cost amplification** — scripting `/api/match` in a loop to run up the bill | Per-IP rate limit (default 3/min) + global rate limit (20/min) + **hard daily search cap (300/day) as a spend kill-switch** — past the cap the endpoint returns "daily limit reached" and runs no model calls | `app/web/guard.py` |
| 2 | **API key exfiltration** | Key read only from `ANTHROPIC_API_KEY` env at runtime; never hardcoded, logged, or put in a response. All error paths return fixed, sanitized strings; the catch-all logs server-side only. Audited: the only `str(exc)` reaching a client is `PipelineConfigError`'s single hardcoded message | `app/agents/client.py`, `app/web/app.py` |
| 3 | **Oversized / malformed payloads** — memory/parse abuse | Request body capped at 64KB (checked on both `Content-Length` and actual bytes); invalid JSON / schema → friendly 400 via Pydantic validation | `app/web/app.py` `_read_json_capped` |
| 4 | **Cross-origin browser abuse** — another site driving the endpoint from a victim's browser | SPA is served same-origin; no permissive CORS headers are sent (FastAPI default), so cross-origin browser calls are blocked by the same-origin policy. No CORS middleware is added because none is needed | `app/web/app.py` |
| 5 | **Clickjacking / content-sniffing** | Baseline security headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` | `app/web/app.py` `_security_headers` |
| 6 | **Spend overrun despite all the above** | Defense-in-depth backstop **outside the app**: a monthly usage limit set in the Anthropic Console, which the app cannot override | Anthropic Console (operator-set) |

## The cost math (why #1 + #6 actually bound the money)

The daily cap is the real ceiling. Worst case daily spend ≈
`DAILY_SEARCH_CAP × (cost per search)`. With the default cap of 300 and a
generous per-search estimate, that's a small, known daily maximum — and the
Anthropic Console monthly limit (#6) caps it again at the account level even if
the app misbehaves or is redeployed without the env limits. Two independent
ceilings: one in the app (fast, free, restartable), one at the provider
(authoritative, app can't bypass).

All limits are env-tunable (`GUARD_PER_IP_PER_MIN`, `GUARD_GLOBAL_PER_MIN`,
`GUARD_DAILY_SEARCH_CAP`) so the deploy can tighten them without a code change.

## Deliberately out of scope (and why)

Skipping these is a judgment call, not an oversight — adding them to an
unauthenticated demo with no user data would be complexity without a matching
threat:

- **Authentication / login** — there are no user accounts to protect. Auth would
  also defeat the point (a demo recruiters can click without signing up).
- **CSRF tokens** — no cookies, no sessions, no authenticated state to forge.
- **SQL-injection defenses** — no user-facing SQL; SQLite (if used) is fed
  internal values, not request strings.
- **A WAF / DDoS protection** — Railway's edge handles network-layer abuse; the
  app-layer cost guard is the relevant defense for *this* app's real risk.
- **Secrets-management infra (Vault, etc.)** — one secret, injected as an env var
  by the platform. A vault would be infrastructure for a problem we don't have.

## Known limitations

- **Guard state is in-memory and per-instance.** Counters reset on restart and
  don't share across replicas. Acceptable for a single-instance demo; documented
  in `guard.py`. Scaling past one instance means moving the counters to a shared
  store (Redis) — the `GuardState` interface is built to swap.
- **IP attribution relies on `X-Forwarded-For`** behind Railway's proxy. It's
  used only for rate-limiting buckets, never as an authentication signal, so
  spoofing it at worst lets an attacker spread requests across fake IPs — which
  the global rate limit and daily cap still bound.

## Reporting

This is a portfolio project, not a production service. If you find an issue,
open a GitHub issue (no sensitive data, please).
