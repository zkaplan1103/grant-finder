"""Wiring that turns a Profile into a rendered result, end to end.

Kept separate from the route handlers so the web tests can inject a fake runner
and never touch the network or an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.agents import DrafterAgent, MatchAgent, VerifyAgent
from app.agents.client import LLMClient, build_default_client
from app.discovery.grants_gov import GrantsGovClient
from app.discovery.service import discover
from app.orchestrator import PipelineResult, run_pipeline
from app.models import Profile


class PipelineConfigError(Exception):
    """Raised when a live run is requested without an API key. Sanitized message."""


@dataclass
class FullResult:
    pipeline: PipelineResult
    grants_gov_ok: bool
    grants_gov_message: Optional[str]


def run_full_pipeline(
    profile: Profile,
    *,
    llm_client: Optional[LLMClient] = None,
    grants_client: Optional[GrantsGovClient] = None,
    use_live_grants_gov: bool = True,
) -> FullResult:
    """Discover candidates, then score + draft + verify them.

    `llm_client` is injectable for tests. In production it comes from the
    environment key via build_default_client(); without a key we raise a
    sanitized PipelineConfigError (no secrets, no internals).
    """
    client = llm_client or build_default_client()
    if client is None:
        raise PipelineConfigError(
            "The matching service is not configured. An administrator must set the "
            "API credentials before running matches."
        )

    own_grants_client = False
    if grants_client is None and use_live_grants_gov:
        grants_client = GrantsGovClient()
        own_grants_client = True

    try:
        disco = discover(profile, grants_client=grants_client)
    finally:
        if own_grants_client and grants_client is not None:
            grants_client.close()

    pipeline = run_pipeline(
        profile,
        disco.opportunities,
        MatchAgent(client),
        DrafterAgent(client),
        VerifyAgent(client),
    )
    return FullResult(
        pipeline=pipeline,
        grants_gov_ok=disco.grants_gov_ok,
        grants_gov_message=disco.grants_gov_message,
    )
