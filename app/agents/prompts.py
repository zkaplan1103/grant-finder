"""Shared prompt assembly.

The profile + grant-requirements prefix is identical across Match, Drafter, and
Verify, and across every Drafter<->Verify iteration. We render it once as a
system block carrying `cache_control: {"type": "ephemeral"}` so reads are ~0.1x
cost (PRD section 8).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.models import Opportunity, Profile


def profile_to_prompt_dict(profile: Profile) -> Dict[str, Any]:
    """Stable, deterministic dict for the cached prefix (no volatile fields)."""
    return profile.model_dump(mode="json")


def opportunity_to_prompt_dict(opportunity: Opportunity) -> Dict[str, Any]:
    return opportunity.model_dump(mode="json")


def shared_prefix_text(
    profile: Profile, opportunity: Optional[Opportunity] = None
) -> str:
    """The text of the shared, cacheable prefix.

    Deterministic JSON (sorted keys) so the cached prefix is byte-stable across
    requests — a varying prefix would silently defeat prompt caching.
    """
    parts: List[str] = []
    parts.append("NONPROFIT PROFILE (the applicant org):")
    parts.append(json.dumps(profile_to_prompt_dict(profile), sort_keys=True, indent=2))
    if opportunity is not None:
        parts.append("")
        parts.append("FUNDING OPPORTUNITY (with its stated requirements):")
        parts.append(
            json.dumps(opportunity_to_prompt_dict(opportunity), sort_keys=True, indent=2)
        )
    return "\n".join(parts)


def cached_system_blocks(
    system_prompt: str, profile: Profile, opportunity: Optional[Opportunity] = None
) -> List[Dict[str, Any]]:
    """Build system blocks: a stable agent instruction + the cached shared prefix.

    The cache_control breakpoint sits on the last (shared-prefix) block so the
    agent instruction and the profile+requirements prefix cache together.
    """
    return [
        {"type": "text", "text": system_prompt},
        {
            "type": "text",
            "text": shared_prefix_text(profile, opportunity),
            "cache_control": {"type": "ephemeral"},
        },
    ]
