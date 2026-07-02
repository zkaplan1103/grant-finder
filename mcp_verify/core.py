"""Domain-agnostic verify engine.

Checks a DRAFT string against a SOURCE string (the source of truth) and returns
the specific unsupported claims, each with an explainable verdict: the source
fact it was checked against, an error category, and a severity.

For now this imports the client seam and JSON parsing from `app.agents`; those
modules get copied into this package when the repo splits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.agents.client import LLMClient
from app.agents.parsing import extract_json_object
from mcp_verify.prompt import SYSTEM_PROMPT


@dataclass
class VerifiedClaim:
    claim: str
    reason: str
    source_fact_checked: str = ""
    category: str = ""
    severity: str = ""


@dataclass
class VerifyReport:
    passed: bool
    failures: List[VerifiedClaim]


def verify(
    client: LLMClient,
    source: str,
    draft: str,
    model: str = "claude-opus-4-8",
    max_tokens: int = 16000,
    thinking: Optional[Dict[str, Any]] = {"type": "adaptive"},  # noqa: B006 — never mutated
) -> VerifyReport:
    # The SOURCE block carries the cache_control breakpoint so the prompt +
    # source prefix cache together across repeated verify calls.
    system: List[Dict[str, Any]] = [
        {"type": "text", "text": SYSTEM_PROMPT},
        {"type": "text", "text": source, "cache_control": {"type": "ephemeral"}},
    ]
    messages = [
        {
            "role": "user",
            "content": (
                "Check this draft for unsupported claims.\n\n"
                f"{draft}\n\n"
                "Return the JSON object only."
            ),
        }
    ]
    resp = client.complete(
        model=model,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
        thinking=thinking,
    )
    data = extract_json_object(resp.text, resp.stop_reason)
    failures = [
        VerifiedClaim(
            claim=str(f["claim"]),
            reason=str(f["reason"]),
            source_fact_checked=str(f.get("source_fact_checked") or ""),
            category=str(f.get("category") or ""),
            severity=str(f.get("severity") or ""),
        )
        for f in (data.get("failures") or [])
    ]
    # Trust the failures list as the source of truth for pass/fail.
    passed = bool(data.get("passed", not failures)) and not failures
    return VerifyReport(passed=passed, failures=failures)
