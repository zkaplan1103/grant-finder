"""Injectable LLM client layer.

`LLMClient` is the seam the agents talk to. Tests pass a fake implementation, so
no live Anthropic calls happen during the build / free test suite. The real
`AnthropicLLMClient` is constructed only from `ANTHROPIC_API_KEY` in the
environment at runtime — the key is never hardcoded, logged, or surfaced.

Model ids (PRD section 8): Sonnet 4.6 = claude-sonnet-4-6, Opus 4.8 = claude-opus-4-8.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


class ServiceUnavailableError(Exception):
    """The upstream model API is temporarily unavailable (rate limit, quota, or
    overload). Carries a sanitized, user-facing message — never the raw SDK
    error (which could include account/key context). Distinct from a generic
    failure so the web layer can say 'at capacity, try again' vs. 'broke'."""


@dataclass
class LLMResponse:
    """Minimal normalized response: the assistant text plus the request echo.

    `request` captures exactly what was sent (model, system blocks, thinking,
    messages) so unit tests can assert prompt assembly, model selection, and
    cache_control placement without a live call.
    """

    text: str
    request: Dict[str, Any] = field(default_factory=dict)
    stop_reason: Optional[str] = None


class LLMClient(Protocol):
    """The seam. One method: send a message and get text back."""

    def complete(
        self,
        *,
        model: str,
        system: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        max_tokens: int,
        thinking: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        ...


class AnthropicLLMClient:
    """Real client wrapping the official `anthropic` SDK.

    Imports the SDK lazily so the package imports (and the free test suite runs)
    without `anthropic` installed or any key present.
    """

    def __init__(self, api_key: str) -> None:
        # ponytail: lazy import keeps `import app` free of the SDK dependency.
        import anthropic

        # The key comes from the caller (which reads it from the environment).
        # We do not store it on the instance beyond what the SDK holds, and we
        # never log it.
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(
        self,
        *,
        model: str,
        system: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        max_tokens: int,
        thinking: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        kwargs: Dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if thinking is not None:
            kwargs["thinking"] = thinking

        import anthropic

        try:
            resp = self._client.messages.create(**kwargs)
        except (anthropic.RateLimitError, anthropic.InternalServerError) as exc:
            # Rate limit / quota cap / overload — transient and not our bug.
            # Raise a sanitized type so the web layer shows "at capacity", never
            # the raw SDK message (which can carry account context).
            raise ServiceUnavailableError(
                "The matching service is at capacity right now. Please try again "
                "in a few minutes."
            ) from exc
        except anthropic.APIStatusError as exc:
            # Other 4xx/5xx. A 429 is already handled above; a billing/quota error
            # may surface here as 400 with type "billing_error" — treat capacity
            # and billing limits as "temporarily unavailable", re-raise the rest.
            if getattr(exc, "status_code", None) == 429 or getattr(exc, "type", "") in (
                "billing_error",
                "overloaded_error",
                "rate_limit_error",
            ):
                raise ServiceUnavailableError(
                    "The matching service is at capacity right now. Please try "
                    "again in a few minutes."
                ) from exc
            raise
        # Concatenate text blocks (skip thinking blocks).
        text = "".join(
            getattr(block, "text", "") for block in resp.content if getattr(block, "type", "") == "text"
        )
        return LLMResponse(text=text, request=kwargs, stop_reason=getattr(resp, "stop_reason", None))


def build_default_client() -> Optional[LLMClient]:
    """Build the real client from the environment, or return None if no key.

    Returning None (rather than raising) lets the web app boot without a key;
    the pipeline surfaces a clean, sanitized error when a live run is attempted.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return AnthropicLLMClient(api_key=api_key)
