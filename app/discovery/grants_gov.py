"""grants.gov Search2 client (PRD section 9).

POST /v1/api/search2 (no auth for basic search) returns a thin response; we then
fetch full details per candidate. Everything is wrapped with a timeout and
GRACEFUL FAILURE — a live demo that hangs or stack-traces is worse than no demo.
On any network/timeout/HTTP error we raise a typed, sanitized exception the
caller turns into "grants.gov unreachable" (curated sources still flow).

The httpx client is injectable so tests mock the transport with respx; no live
grants.gov calls happen in the test suite.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.models import Opportunity, OpportunitySource

BASE_URL = "https://api.grants.gov/v1/api"
SEARCH2_PATH = "/search2"
FETCH_PATH = "/fetchOpportunity"
DEFAULT_TIMEOUT_SECONDS = 8.0


class GrantsGovError(Exception):
    """Base class — message is always safe to show a user (no secrets/internals)."""


class GrantsGovTimeout(GrantsGovError):
    pass


class GrantsGovUnreachable(GrantsGovError):
    pass


class GrantsGovClient:
    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # Injectable transport: tests pass a respx-mocked client.
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "GrantsGovClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    def search(self, params: Dict[str, Any]) -> List[Opportunity]:
        """Run Search2 with the Stage-1 params; return normalized Opportunities.

        Raises GrantsGovTimeout / GrantsGovUnreachable on failure — the caller
        degrades gracefully to curated-only results.
        """
        data = self._post(SEARCH2_PATH, params)
        hits = (((data or {}).get("data") or {}).get("oppHits")) or []
        return [self._normalize_hit(h) for h in hits]

    def fetch_details(self, opportunity_id: str) -> Optional[Opportunity]:
        """Second call: full details for one candidate. None if it fails softly."""
        try:
            data = self._post(FETCH_PATH, {"opportunityId": opportunity_id})
        except GrantsGovError:
            # Detail enrichment is best-effort; never block the whole run on it.
            return None
        payload = (data or {}).get("data") or {}
        if not payload:
            return None
        return self._normalize_details(opportunity_id, payload)

    # ------------------------------------------------------------------ #
    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            resp = self._client.post(url, json=body, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise GrantsGovTimeout("grants.gov request timed out") from exc
        except httpx.HTTPError as exc:
            # Covers ConnectError, network errors, etc. Message is generic on
            # purpose — never echo the underlying exception text to users.
            raise GrantsGovUnreachable("grants.gov is unreachable") from exc

        if resp.status_code >= 500:
            raise GrantsGovUnreachable("grants.gov returned a server error")
        if resp.status_code >= 400:
            raise GrantsGovError("grants.gov rejected the request")

        try:
            return resp.json()
        except ValueError as exc:
            raise GrantsGovUnreachable("grants.gov returned an unparseable response") from exc

    # ------------------------------------------------------------------ #
    @staticmethod
    def _aln(value: Any) -> Optional[str]:
        # Search2 returns ALN/CFDA as a list (e.g. ['43.001']) or a str; normalize.
        if isinstance(value, list):
            return ", ".join(str(v) for v in value) or None
        return str(value) if value else None

    @staticmethod
    def _detail_url(hit: Dict[str, Any]) -> Optional[str]:
        # The grants.gov detail page is keyed on the NUMERIC opportunity id
        # (.../search-results-detail/354632). The alphanumeric "number"
        # (EPA-R9-...) 404s on that path, so only build a URL from a numeric id.
        numeric_id = hit.get("id") or hit.get("oppId")
        if numeric_id and str(numeric_id).isdigit():
            return f"https://www.grants.gov/search-results-detail/{numeric_id}"
        return None

    @staticmethod
    def _normalize_hit(hit: Dict[str, Any]) -> Opportunity:
        opp_id = str(hit.get("id") or hit.get("number") or hit.get("oppId") or "")
        return Opportunity(
            id=opp_id,
            source=OpportunitySource.GRANTS_GOV,
            title=str(hit.get("title") or "Untitled opportunity"),
            agency=hit.get("agencyName") or hit.get("agency"),
            url=GrantsGovClient._detail_url(hit),
            status=hit.get("oppStatus"),
            close_date=hit.get("closeDate"),
            aln=GrantsGovClient._aln(
                hit.get("alnist") or hit.get("aln") or hit.get("cfdaList")
            ),
        )

    @staticmethod
    def _normalize_details(opp_id: str, payload: Dict[str, Any]) -> Opportunity:
        synopsis = payload.get("synopsis") or {}
        return Opportunity(
            id=opp_id,
            source=OpportunitySource.GRANTS_GOV,
            title=str(payload.get("opportunityTitle") or synopsis.get("title") or "Untitled"),
            agency=payload.get("agencyName") or synopsis.get("agencyName"),
            url=(
                f"https://www.grants.gov/search-results-detail/{opp_id}"
                if opp_id and opp_id.isdigit() else None
            ),
            status=payload.get("opportunityStatus"),
            close_date=synopsis.get("responseDate"),
            aln=GrantsGovClient._aln(payload.get("cfdaList")),
            eligibility_notes=synopsis.get("applicantEligibilityDesc")
            or synopsis.get("applicantTypes"),
            description=synopsis.get("synopsisDesc") or synopsis.get("description"),
        )
