"""FastAPI + Jinja app: one profile form, one results page (PRD section 3).

Deliberate states: loading is implicit (synchronous run), empty results, a
SANITIZED error state that never leaks keys/internals, and a "grants.gov
unreachable" banner. The pipeline runner is overridable via app.state so tests
inject a fake and never make a live call.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.models import Profile
from app.web.forms import parse_profile_form
from app.web.pipeline import FullResult, PipelineConfigError, run_full_pipeline

logger = logging.getLogger("solar_grant_navigator.web")

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

app = FastAPI(title="Solar Grant Navigator")

# Default runner is the real pipeline; tests override app.state.run_pipeline.
RunnerType = Callable[[Profile], FullResult]
app.state.run_pipeline = run_full_pipeline


def _runner(request: Request) -> RunnerType:
    runner = getattr(request.app.state, "run_pipeline", None)
    return runner or run_full_pipeline


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("form.html", {"request": request})


@app.post("/results", response_class=HTMLResponse)
async def results(request: Request) -> HTMLResponse:
    form = await request.form()

    # 1. Parse + validate the profile. Bad input -> friendly 400, no internals.
    try:
        profile = parse_profile_form(dict(form))
    except (ValidationError, ValueError, KeyError):
        return templates.TemplateResponse(
            "form.html",
            {
                "request": request,
                "error": "Please fill in the required fields with valid values.",
                "form_values": dict(form),
            },
            status_code=400,
        )

    # 2. Run the pipeline. Any failure renders a sanitized error page.
    try:
        result = _runner(request)(profile)
    except PipelineConfigError as exc:
        # Message is already sanitized (no key/secret).
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": str(exc)},
            status_code=503,
        )
    except Exception:  # noqa: BLE001 — last-resort guard
        # Never leak the exception text (could contain internals). Log server-side
        # only, with no secret material.
        logger.exception("Pipeline failed")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Something went wrong while finding matches. Please try again.",
            },
            status_code=500,
        )

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "profile": profile,
            "result": result,
            "matches": result.pipeline.results,
        },
    )
