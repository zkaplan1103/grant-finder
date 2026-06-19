"""Discovery layer: live grants.gov Search2 + curated YAML sources (PRD section 9).

The agents reason over grants.gov hits and curated entries identically — both are
normalized to `Opportunity`.
"""

from app.discovery.curated import CURATED_SOURCES_PATH, load_curated_sources
from app.discovery.grants_gov import (
    GrantsGovClient,
    GrantsGovError,
    GrantsGovTimeout,
    GrantsGovUnreachable,
)
from app.discovery.service import DiscoveryResult, discover

__all__ = [
    "GrantsGovClient",
    "GrantsGovError",
    "GrantsGovTimeout",
    "GrantsGovUnreachable",
    "load_curated_sources",
    "CURATED_SOURCES_PATH",
    "discover",
    "DiscoveryResult",
]
