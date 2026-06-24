"""FastAPI JSON API + static SPA host (PRD section 3, React frontend).

`POST /api/match` runs the full pipeline synchronously and returns JSON. The
built React app (frontend/dist) is served as static files at `/`. Error states
are SANITIZED: a config error and any unexpected error never leak keys or
internals (this guarantee is security-critical and must not be relaxed). The
pipeline runner is overridable via app.state so tests inject a fake and never
make a live call.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.agents.client import ServiceUnavailableError
from app.models import Profile
from app.orchestrator import MatchedOpportunity, PipelineResult
from app.web.guard import GuardState, client_ip
from app.web.pipeline import FullResult, PipelineConfigError, run_full_pipeline

logger = logging.getLogger("grant_navigator.web")

app = FastAPI(title="Grant Navigator")

# Default runner is the real pipeline; tests override app.state.run_pipeline.
RunnerType = Callable[[Profile], FullResult]
app.state.run_pipeline = run_full_pipeline

# Abuse/cost guard: one in-memory tracker per process. Bounds the expensive
# /api/match endpoints (per-IP + global rate limit + daily spend kill-switch).
app.state.guard = GuardState()


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    """Baseline hardening headers. Cheap, no behavior change. No CORS middleware
    is needed — the SPA is served same-origin, and FastAPI sends no permissive
    CORS headers by default, so cross-origin browser calls are already blocked."""
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


# A valid profile is small (well under a KB). Cap the body so a giant payload
# can't waste memory/parse time. 64KB is generous headroom.
_MAX_BODY_BYTES = 64 * 1024


class _BodyTooLarge(ValueError):
    pass


async def _read_json_capped(request: Request):
    """Read + JSON-parse the body, rejecting anything over the size cap.

    Checks Content-Length when present, and also enforces the cap on the actual
    bytes (a lying/absent Content-Length can't sneak a huge body past us).
    """
    cl = request.headers.get("content-length")
    if cl is not None and cl.isdigit() and int(cl) > _MAX_BODY_BYTES:
        raise _BodyTooLarge()
    raw = await request.body()
    if len(raw) > _MAX_BODY_BYTES:
        raise _BodyTooLarge()
    return json.loads(raw)


def _guard_check(request: Request) -> Optional[JSONResponse]:
    """Run the rate/spend guard. Returns a 429 JSONResponse if blocked, else None.

    Tests don't set app.state.guard to a custom value, but the default above is
    permissive enough for the suite; a test can swap in its own GuardState.
    """
    guard: GuardState = request.app.state.guard
    decision = guard.check_and_consume(client_ip(request))
    if not decision.ok:
        return JSONResponse({"error": decision.reason}, status_code=429)
    return None


def _runner(request: Request) -> RunnerType:
    runner = getattr(request.app.state, "run_pipeline", None)
    return runner or run_full_pipeline


# --------------------------------------------------------------------------- #
# Serialization: dataclasses -> JSON. Pydantic models self-serialize.
# --------------------------------------------------------------------------- #
def _matched_to_dict(item: MatchedOpportunity) -> Dict[str, Any]:
    return {
        "opportunity": item.opportunity.model_dump(mode="json"),
        "match": item.match.model_dump(mode="json"),
        "draft": item.draft.model_dump(mode="json") if item.draft else None,
    }


def _result_to_dict(result: FullResult) -> Dict[str, Any]:
    pipeline: PipelineResult = result.pipeline
    return {
        "profile_sparse": pipeline.profile_sparse,
        "grants_gov_ok": result.grants_gov_ok,
        "grants_gov_message": result.grants_gov_message,
        "matches": [_matched_to_dict(m) for m in pipeline.results],
    }


# --------------------------------------------------------------------------- #
@app.post("/api/match")
async def match(request: Request) -> JSONResponse:
    # 0. Abuse/cost guard first — reject floods before doing any work.
    blocked = _guard_check(request)
    if blocked is not None:
        return blocked

    # 1. Parse + validate the profile from JSON. Bad input -> friendly 400.
    try:
        body = await _read_json_capped(request)
        profile = Profile.model_validate(body)
    except (ValidationError, ValueError):
        return JSONResponse(
            {"error": "Please fill in the required fields with valid values."},
            status_code=400,
        )

    # 2. Run the pipeline. Any failure returns a sanitized error.
    try:
        result = _runner(request)(profile)
    except (PipelineConfigError, ServiceUnavailableError) as exc:
        # Both carry sanitized, user-facing messages (no key/secret/internals).
        # 503 = temporarily unavailable (not configured, or upstream at capacity).
        return JSONResponse({"error": str(exc)}, status_code=503)
    except Exception:  # noqa: BLE001 — last-resort guard
        # Never leak the exception text (could contain internals). Log server-side
        # only, with no secret material.
        logger.exception("Pipeline failed")
        return JSONResponse(
            {"error": "Something went wrong while finding matches. Please try again."},
            status_code=500,
        )

    return JSONResponse(_result_to_dict(result))


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/match/stream")
async def match_stream(request: Request) -> StreamingResponse:
    """Same as /api/match but streams progress events (SSE) while it runs.

    The pipeline is blocking, so it runs in a worker thread and pushes
    (stage, done, total) progress onto a queue; the generator drains the queue
    to the client. Errors are sanitized exactly like /api/match.
    """
    blocked = _guard_check(request)
    if blocked is not None:
        return blocked

    try:
        body = await _read_json_capped(request)
        profile = Profile.model_validate(body)
    except (ValidationError, ValueError):
        return JSONResponse(
            {"error": "Please fill in the required fields with valid values."},
            status_code=400,
        )

    runner = _runner(request)
    events: "queue.Queue[tuple[str, Any]]" = queue.Queue()

    def on_progress(stage: str, done: int, total: int) -> None:
        events.put(("progress", {"stage": stage, "done": done, "total": total}))

    def work() -> None:
        try:
            # The fake runner in tests ignores extra kwargs; the real one accepts progress.
            try:
                result = runner(profile, progress=on_progress)  # type: ignore[call-arg]
            except TypeError:
                result = runner(profile)
            events.put(("done", _result_to_dict(result)))
        except (PipelineConfigError, ServiceUnavailableError) as exc:
            events.put(("error", {"error": str(exc)}))
        except Exception:  # noqa: BLE001
            logger.exception("Pipeline failed")
            events.put(("error", {"error": "Something went wrong while finding matches. Please try again."}))
        finally:
            events.put(("__end__", None))

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while True:
            kind, payload = events.get()
            if kind == "__end__":
                break
            yield _sse(kind, payload)

    return StreamingResponse(stream(), media_type="text/event-stream")


# --------------------------------------------------------------------------- #
# Serve the built SPA at `/` when it exists. Mounted last so /api wins.
# Absent in CI/tests (no frontend build) — skip cleanly.
# --------------------------------------------------------------------------- #
_DIST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_DIST_DIR):
    app.mount("/", StaticFiles(directory=_DIST_DIR, html=True), name="spa")
