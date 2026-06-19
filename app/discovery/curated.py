"""Curated-sources loader (PRD section 9).

Loads the hand-vetted ~10-15 foundation/state sources from sources.yaml and
normalizes them to `Opportunity` so the agents reason over them identically to
grants.gov hits. This is the spreadsheet a real caseworker keeps — not the
scrape-everything trap.
"""

from __future__ import annotations

import os
from typing import List, Optional

import yaml

from app.models import Opportunity, OpportunitySource

# Default location: app/sources.yaml (one dir up from this file).
CURATED_SOURCES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sources.yaml")


def load_curated_sources(path: Optional[str] = None) -> List[Opportunity]:
    path = path or CURATED_SOURCES_PATH
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or []

    sources: List[Opportunity] = []
    for entry in raw:
        sources.append(
            Opportunity(
                id=str(entry["id"]),
                source=OpportunitySource.CURATED,
                title=str(entry["name"]),
                agency=entry.get("agency") or entry.get("funder"),
                url=entry.get("url"),
                close_date=entry.get("deadline"),
                typical_award=entry.get("typical_award"),
                eligibility_notes=entry.get("eligibility_notes"),
                description=entry.get("description"),
            )
        )
    return sources
