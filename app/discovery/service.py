"""Discovery service — combines the mapper, live grants.gov, and curated sources
into one candidate set, degrading gracefully when grants.gov is unreachable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.discovery.curated import load_curated_sources
from app.discovery.grants_gov import GrantsGovClient, GrantsGovError
from app.mapper import profile_to_search_params
from app.models import Opportunity, Profile


@dataclass
class DiscoveryResult:
    opportunities: List[Opportunity] = field(default_factory=list)
    grants_gov_ok: bool = True
    grants_gov_message: Optional[str] = None  # sanitized, safe to display


def discover(
    profile: Profile,
    *,
    grants_client: Optional[GrantsGovClient] = None,
    curated_path: Optional[str] = None,
    enrich_details: bool = False,
    max_enrich: int = 10,
) -> DiscoveryResult:
    """Pull curated + live federal candidates for a profile.

    Curated sources always load (local). grants.gov is best-effort: on timeout or
    unreachability we keep the curated set and flag the degradation with a
    sanitized message.
    """
    result = DiscoveryResult()
    result.opportunities.extend(load_curated_sources(curated_path))

    if grants_client is None:
        return result

    params = profile_to_search_params(profile)
    try:
        hits = grants_client.search(params)
    except GrantsGovError as exc:
        result.grants_gov_ok = False
        # exc messages are pre-sanitized in the client.
        result.grants_gov_message = str(exc)
        return result

    if enrich_details:
        enriched: List[Opportunity] = []
        for hit in hits[:max_enrich]:
            detail = grants_client.fetch_details(hit.id) if hit.id else None
            enriched.append(detail or hit)
        enriched.extend(hits[max_enrich:])
        hits = enriched

    result.opportunities.extend(hits)
    return result
